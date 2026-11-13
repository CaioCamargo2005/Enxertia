"""
Banco de dados de combinacoes de enxertia (SQLite, so biblioteca padrao).

Objetivo do grupo: ter um banco que se consulta automaticamente pra saber se
um par porta-enxerto/enxerto e compativel. Cada registro e uma AFIRMACAO
sobre um par especifico, com o tipo de evidencia por tras dela:

- "citada": tem fonte (artigo, manual, livro) no campo `fonte` -- obrigatoria.
- "conhecimento_geral": pratica conhecida de horticultura, mas SEM citacao
  formal. E o caso dos registros iniciais (seed) -- precisam ser verificados.
- "relato_nao_verificado": ouvido/lido em algum lugar, sem confirmacao.

Pares que NAO estao no banco continuam sendo estimados (modelo de ML ou
regras taxonomicas) -- e o resultado diz isso (`source` != "banco").

O arquivo do banco fica em data/enxertia.db (ou onde ENXERTIA_DB apontar).
"""

import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from app.score_bands import nivel_para_score

DEFAULT_DB = Path(__file__).parent.parent / "data" / "enxertia.db"

TIPOS_EVIDENCIA = ("citada", "conhecimento_geral", "relato_nao_verificado")

SCHEMA = """
CREATE TABLE IF NOT EXISTS combinacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    porta_enxerto TEXT NOT NULL COLLATE NOCASE,
    enxerto TEXT NOT NULL COLLATE NOCASE,
    compatibilidade REAL NOT NULL CHECK (compatibilidade >= 0 AND compatibilidade <= 1),
    tipo_evidencia TEXT NOT NULL CHECK (tipo_evidencia IN ('citada', 'conhecimento_geral', 'relato_nao_verificado')),
    fonte TEXT,
    observacoes TEXT,
    vale_nos_dois_sentidos INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE (porta_enxerto, enxerto)
);

CREATE TABLE IF NOT EXISTS evidencias_literatura (
    id_registro TEXT PRIMARY KEY,
    cultura TEXT,
    copa TEXT NOT NULL,
    porta_enxerto TEXT NOT NULL,
    afirmacao TEXT NOT NULL,
    medida TEXT,
    tipo_dado TEXT,
    trecho TEXT,
    fonte_id TEXT NOT NULL,
    fonte_referencia TEXT NOT NULL,
    fonte_url TEXT,
    ressalva TEXT,
    copa_taxon TEXT,
    porta_taxon TEXT,
    conferido INTEGER NOT NULL DEFAULT 0,
    combinacao_id INTEGER
);
"""


def db_path() -> Path:
    return Path(os.getenv("ENXERTIA_DB", str(DEFAULT_DB)))


@contextmanager
def conectar():
    caminho = db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _linha_para_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    d["nivel"] = nivel_para_score(d["compatibilidade"])
    return d


def contar() -> int:
    try:
        with conectar() as con:
            return con.execute("SELECT COUNT(*) FROM combinacoes").fetchone()[0]
    except sqlite3.Error:
        return 0


def buscar_combinacao(porta_enxerto: str, enxerto: str) -> Optional[dict]:
    """Procura o par no banco. Tenta primeiro a ordem exata; se o registro
    vale nos dois sentidos, tenta tambem a ordem inversa (`inverso`=True).
    Nunca levanta excecao: se o banco estiver indisponivel, devolve None e o
    sistema segue com a estimativa."""
    a, b = porta_enxerto.strip(), enxerto.strip()
    try:
        with conectar() as con:
            linha = con.execute(
                "SELECT * FROM combinacoes WHERE porta_enxerto = ? AND enxerto = ?", (a, b)
            ).fetchone()
            if linha:
                return {**_linha_para_dict(linha), "inverso": False}
            linha = con.execute(
                "SELECT * FROM combinacoes WHERE porta_enxerto = ? AND enxerto = ? "
                "AND vale_nos_dois_sentidos = 1", (b, a)
            ).fetchone()
            if linha:
                return {**_linha_para_dict(linha), "inverso": True}
    except sqlite3.Error:
        return None
    return None


def listar(busca: Optional[str] = None, limite: int = 500) -> List[dict]:
    with conectar() as con:
        if busca:
            termo = f"%{busca.strip()}%"
            linhas = con.execute(
                "SELECT * FROM combinacoes WHERE porta_enxerto LIKE ? OR enxerto LIKE ? "
                "OR fonte LIKE ? OR observacoes LIKE ? ORDER BY porta_enxerto, enxerto LIMIT ?",
                (termo, termo, termo, termo, limite),
            ).fetchall()
        else:
            linhas = con.execute(
                "SELECT * FROM combinacoes ORDER BY porta_enxerto, enxerto LIMIT ?", (limite,)
            ).fetchall()
    return [_linha_para_dict(l) for l in linhas]


class RegistroInvalido(ValueError):
    pass


class RegistroDuplicado(ValueError):
    pass


def inserir(porta_enxerto: str, enxerto: str, compatibilidade: float, tipo_evidencia: str,
            fonte: Optional[str] = None, observacoes: Optional[str] = None,
            vale_nos_dois_sentidos: bool = True) -> dict:
    porta_enxerto, enxerto = (porta_enxerto or "").strip(), (enxerto or "").strip()
    fonte = (fonte or "").strip() or None
    if not porta_enxerto or not enxerto:
        raise RegistroInvalido("Informe o porta-enxerto e o enxerto.")
    if tipo_evidencia not in TIPOS_EVIDENCIA:
        raise RegistroInvalido(f"tipo_evidencia deve ser um de: {', '.join(TIPOS_EVIDENCIA)}.")
    if not (0.0 <= compatibilidade <= 1.0):
        raise RegistroInvalido("compatibilidade deve estar entre 0 e 1.")
    if tipo_evidencia == "citada" and not fonte:
        raise RegistroInvalido("Evidencia 'citada' exige o campo fonte (artigo, manual, livro...).")

    try:
        with conectar() as con:
            cur = con.execute(
                "INSERT INTO combinacoes (porta_enxerto, enxerto, compatibilidade, tipo_evidencia, "
                "fonte, observacoes, vale_nos_dois_sentidos) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (porta_enxerto, enxerto, compatibilidade, tipo_evidencia, fonte, observacoes,
                 1 if vale_nos_dois_sentidos else 0),
            )
            linha = con.execute("SELECT * FROM combinacoes WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise RegistroDuplicado(f"Ja existe um registro para {porta_enxerto} x {enxerto}.")
    return _linha_para_dict(linha)


def remover(registro_id: int) -> bool:
    with conectar() as con:
        return con.execute("DELETE FROM combinacoes WHERE id = ?", (registro_id,)).rowcount > 0


def _carregar_excecoes() -> dict:
    """Reaproveita a lista de excecoes curada em data/build_seed_dataset.py
    (fonte unica -- o mesmo conhecimento alimenta o treino do ML e o seed do
    banco)."""
    raiz = str(Path(__file__).parent.parent)
    if raiz not in sys.path:
        sys.path.insert(0, raiz)
    from data.build_seed_dataset import EXCECOES
    return EXCECOES


def semear_se_vazio() -> int:
    """Se o banco estiver vazio, cadastra as excecoes curadas como registros
    de evidencia 'conhecimento_geral' (SEM citacao formal -- ver docstring do
    modulo). Devolve quantos registros inseriu."""
    if contar() > 0:
        return 0
    inseridos = 0
    for par, (score, nota) in _carregar_excecoes().items():
        a, b = sorted(par)
        inserir(a, b, score, "conhecimento_geral", fonte=None, observacoes=nota)
        inseridos += 1
    return inseridos


def init_db(seed: bool = True) -> int:
    with conectar():
        pass
    return semear_se_vazio() if seed else 0
