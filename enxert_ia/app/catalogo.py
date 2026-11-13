"""
Leitura do catalogo Enxert.DB (banco da Brenda) para a pagina Catalogo.

O arquivo do banco fica em ../enxert_db/enxert.db (ou onde ENXERT_DB_FILE
apontar). O preparo (criar, migrar e carregar a literatura) e feito pelo mesmo
modulo que o menu em Python usa: enxert_db/banco_enxert_db.py. Esta camada so
le; cadastros continuam pelo menu.
"""

import importlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

RAIZ = Path(__file__).resolve().parent.parent
PASTA_ENXERT_DB = Path(os.getenv("ENXERT_DB_DIR", str(RAIZ.parent / "enxert_db")))


class CatalogoIndisponivel(RuntimeError):
    pass


def _banco():
    if not (PASTA_ENXERT_DB / "banco_enxert_db.py").exists():
        raise CatalogoIndisponivel(
            f"Nao encontrei a pasta do Enxert.DB em {PASTA_ENXERT_DB}. "
            "Ela deve ficar ao lado da pasta enxert_ia (ou defina ENXERT_DB_DIR).")
    if str(PASTA_ENXERT_DB) not in sys.path:
        sys.path.insert(0, str(PASTA_ENXERT_DB))
    return importlib.import_module("banco_enxert_db")


def caminho_db() -> str:
    return os.getenv("ENXERT_DB_FILE", str(PASTA_ENXERT_DB / "enxert.db"))


_preparados = set()


def _conectar():
    banco = _banco()
    caminho = caminho_db()
    if caminho not in _preparados or not os.path.exists(caminho):
        try:
            banco.preparar(caminho, avisar=lambda m: None)
        except banco.ErroBanco as e:
            raise CatalogoIndisponivel(str(e))
        _preparados.add(caminho)
    con = sqlite3.connect(caminho_db())
    con.row_factory = sqlite3.Row
    return con


def resumo() -> dict:
    con = _conectar()
    try:
        n = lambda sql: con.execute(sql).fetchone()[0]
        return {
            "plantas": n("SELECT COUNT(*) FROM Plantas"),
            "combinacoes": n("SELECT COUNT(*) FROM Compatibilidade"),
            "da_equipe": n("SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NULL"),
            "da_literatura": n("SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL"),
            "conferidas": n("SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL AND conferido = 1"),
            "com_taxa": n("SELECT COUNT(*) FROM Compatibilidade WHERE taxa_pegamento_pct IS NOT NULL"),
            "fontes": n("SELECT COUNT(*) FROM Fontes"),
        }
    finally:
        con.close()


CONSULTA = """
SELECT c.id_compatibilidade AS id,
       copa.nome_comum AS copa, copa.nome_cientifico AS copa_cientifico, copa.familia AS copa_familia,
       pe.nome_comum AS porta_enxerto, pe.nome_cientifico AS porta_cientifico, pe.familia AS porta_familia,
       c.status_compatibilidade AS status, c.taxa_pegamento_pct AS taxa_pegamento,
       m.nome_metodo AS metodo, c.observacoes,
       c.id_fonte, f.referencia AS fonte_referencia, f.url AS fonte_url, c.trecho, c.conferido,
       r.resistencia_patogenos_solo AS resistencia_solo, r.tolerancia_estresse_abiotico AS tolerancia,
       r.efeito_porte_vigor AS vigor
FROM Compatibilidade c
JOIN Plantas copa ON copa.id_planta = c.id_copa
JOIN Plantas pe ON pe.id_planta = c.id_porta_enxerto
LEFT JOIN Metodos_Enxertia m ON m.id_metodo = c.id_metodo
LEFT JOIN Fontes f ON f.id_fonte = c.id_fonte
LEFT JOIN Atributos_Resistencia r ON r.id_porta_enxerto = c.id_porta_enxerto
"""


def combinacoes(busca: Optional[str] = None, status: Optional[str] = None,
                origem: Optional[str] = None, limite: int = 500) -> List[dict]:
    cond, args = [], []
    if busca:
        termo = f"%{busca.strip()}%"
        cond.append("(copa.nome_comum LIKE ? OR copa.nome_cientifico LIKE ? OR pe.nome_comum LIKE ? "
                    "OR pe.nome_cientifico LIKE ? OR c.observacoes LIKE ? OR f.referencia LIKE ?)")
        args += [termo] * 6
    if status == "sem_status":
        cond.append("c.status_compatibilidade IS NULL")
    elif status:
        cond.append("c.status_compatibilidade = ?")
        args.append(status)
    if origem == "equipe":
        cond.append("c.id_fonte IS NULL")
    elif origem == "literatura":
        cond.append("c.id_fonte IS NOT NULL")
    elif origem == "a_conferir":
        cond.append("c.id_fonte IS NOT NULL AND c.conferido = 0")
    sql = CONSULTA + (" WHERE " + " AND ".join(cond) if cond else "")
    sql += (" ORDER BY copa.nome_comum, c.taxa_pegamento_pct IS NULL, c.taxa_pegamento_pct DESC, "
            "pe.nome_comum LIMIT ?")
    args.append(limite)
    con = _conectar()
    try:
        return [dict(l) for l in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def plantas() -> List[dict]:
    con = _conectar()
    try:
        return [dict(l) for l in con.execute(
            "SELECT id_planta, nome_comum, nome_cientifico, ncbi_taxid, familia, genero, papel_agronomico "
            "FROM Plantas ORDER BY nome_comum").fetchall()]
    finally:
        con.close()
