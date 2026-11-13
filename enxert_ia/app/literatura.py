"""
Evidencias da literatura (artigos e boletins tecnicos abertos).

De onde vem: data/literatura_enxertia.csv (um registro por afirmacao de uma
fonte) e data/literatura_fontes.csv (referencia completa e link de cada fonte).
Os registros foram extraidos de forma automatica a partir do texto das fontes
e NINGUEM conferiu ainda o trecho contra o PDF. Por isso:

- todo registro entra com `conferido = 0`; so vira 1 quando alguem da equipe
  coloca "sim" na coluna `conferido` do CSV (depois de abrir o PDF e achar o
  trecho) e reinicia o servidor ou roda `python data/importar_literatura.py`;
- a interface mostra "a conferir" ou "conferido" em cada registro.

Duas formas de uso, de proposito separadas:

1. Tabela `evidencias_literatura`: guarda TODOS os registros, em qualquer
   resolucao (cultivar, hibrido, genero). Aparece como contexto no resultado de
   /compatibilidade e em /literatura. Nao altera nenhum score.
2. Tabela `combinacoes` (o banco que responde primeiro): so recebe os poucos
   registros de nivel ESPECIE em que a fonte afirma compatibilidade ou
   incompatibilidade em palavras (coluna `indice_proposto`). O indice numerico
   e uma convencao do projeto (0,9 compativel / 0,1 incompativel, os mesmos
   valores do formulario do banco), nao um numero medido. O tipo de evidencia
   e 'relato_nao_verificado' ate o registro ser conferido; depois vira 'citada'.
"""

import csv
import sqlite3
from pathlib import Path
from typing import List, Optional

from app import db

DATA_DIR = Path(__file__).parent.parent / "data"
CSV_REGISTROS = DATA_DIR / "literatura_enxertia.csv"
CSV_FONTES = DATA_DIR / "literatura_fontes.csv"

MAX_RELACIONADAS = 8


def _ler_csv(caminho: Path) -> List[dict]:
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _tag(id_registro: str) -> str:
    return f"[lit:{id_registro}]"


def importar(registros: Optional[Path] = None, fontes: Optional[Path] = None) -> dict:
    """Carrega os CSVs no banco. Pode rodar quantas vezes quiser: atualiza o que
    mudou (por exemplo a coluna `conferido`) e nao duplica nada. Devolve um
    resumo com as contagens."""
    linhas = _ler_csv(registros or CSV_REGISTROS)
    mapa_fontes = {f["fonte_id"]: f for f in _ler_csv(fontes or CSV_FONTES)}
    resumo = {"registros": 0, "novos": 0, "promovidos_ao_banco": 0, "atualizados_no_banco": 0,
              "pares_ja_existentes": 0}

    with db.conectar() as con:
        for l in linhas:
            fonte = mapa_fontes.get(l["fonte_id"])
            if not fonte:
                raise ValueError(f"Registro {l['id_registro']}: fonte '{l['fonte_id']}' nao esta em {CSV_FONTES.name}.")
            conferido = 1 if (l.get("conferido") or "").strip().lower() in ("sim", "s", "1") else 0
            existente = con.execute(
                "SELECT combinacao_id FROM evidencias_literatura WHERE id_registro = ?", (l["id_registro"],)
            ).fetchone()
            valores = (
                l["cultura"], l["copa"], l["porta_enxerto"], l["afirmacao"], l["medida"], l["tipo_dado"],
                l["trecho"], l["fonte_id"], fonte["referencia"], fonte["url"], l["ressalva"],
                l["copa_taxon"], l["porta_taxon"], conferido,
            )
            if existente is None:
                con.execute(
                    "INSERT INTO evidencias_literatura (cultura, copa, porta_enxerto, afirmacao, medida, "
                    "tipo_dado, trecho, fonte_id, fonte_referencia, fonte_url, ressalva, copa_taxon, "
                    "porta_taxon, conferido, id_registro) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    valores + (l["id_registro"],),
                )
                resumo["novos"] += 1
                combinacao_id = None
            else:
                con.execute(
                    "UPDATE evidencias_literatura SET cultura=?, copa=?, porta_enxerto=?, afirmacao=?, medida=?, "
                    "tipo_dado=?, trecho=?, fonte_id=?, fonte_referencia=?, fonte_url=?, ressalva=?, "
                    "copa_taxon=?, porta_taxon=?, conferido=? WHERE id_registro=?",
                    valores + (l["id_registro"],),
                )
                combinacao_id = existente["combinacao_id"]
            resumo["registros"] += 1

            indice = (l.get("indice_proposto") or "").strip()
            if not indice:
                continue
            tipo = "citada" if conferido else "relato_nao_verificado"
            referencia = f"{fonte['referencia']} {fonte['url']}".strip()
            if l["tipo_dado"].startswith("Citado"):
                referencia = "Citado em: " + referencia
            obs = (f"{_tag(l['id_registro'])} {l['afirmacao']}. Indice {indice} por convencao do projeto "
                   f"(a fonte descreve em palavras, nao em numero). "
                   + ("Trecho conferido no PDF." if conferido else "Trecho ainda a conferir no PDF."))

            if combinacao_id is not None and con.execute(
                    "SELECT 1 FROM combinacoes WHERE id = ?", (combinacao_id,)).fetchone():
                con.execute("UPDATE combinacoes SET tipo_evidencia=?, fonte=?, observacoes=? WHERE id=?",
                            (tipo, referencia, obs, combinacao_id))
                resumo["atualizados_no_banco"] += 1
            elif existente is None:
                # so promove uma vez: se alguem apagar o registro depois, ele nao volta sozinho
                par_existente = con.execute(
                    "SELECT 1 FROM combinacoes WHERE (porta_enxerto = ? AND enxerto = ?) "
                    "OR (porta_enxerto = ? AND enxerto = ? AND vale_nos_dois_sentidos = 1)",
                    (l["porta_enxerto"], l["copa_taxon"], l["copa_taxon"], l["porta_enxerto"]),
                ).fetchone()
                if par_existente:
                    resumo["pares_ja_existentes"] += 1
                    continue
                cur = con.execute(
                    "INSERT INTO combinacoes (porta_enxerto, enxerto, compatibilidade, tipo_evidencia, fonte, "
                    "observacoes, vale_nos_dois_sentidos) VALUES (?,?,?,?,?,?,0)",
                    (l["porta_taxon"], l["copa_taxon"], float(indice), tipo, referencia, obs),
                )
                con.execute("UPDATE evidencias_literatura SET combinacao_id=? WHERE id_registro=?",
                            (cur.lastrowid, l["id_registro"]))
                resumo["promovidos_ao_banco"] += 1
    return resumo


def importar_se_possivel() -> Optional[dict]:
    """Usado na subida do servidor: nunca derruba o sistema se o CSV faltar."""
    try:
        if CSV_REGISTROS.exists() and CSV_FONTES.exists():
            return importar()
    except (OSError, ValueError, sqlite3.Error, KeyError):
        return None
    return None


def contar() -> int:
    try:
        with db.conectar() as con:
            return con.execute("SELECT COUNT(*) FROM evidencias_literatura").fetchone()[0]
    except sqlite3.Error:
        return 0


def listar(busca: Optional[str] = None, cultura: Optional[str] = None, limite: int = 500) -> List[dict]:
    consulta = "SELECT * FROM evidencias_literatura"
    cond, args = [], []
    if busca:
        termo = f"%{busca.strip()}%"
        cond.append("(copa LIKE ? OR porta_enxerto LIKE ? OR afirmacao LIKE ? OR fonte_referencia LIKE ? "
                    "OR copa_taxon LIKE ? OR porta_taxon LIKE ?)")
        args += [termo] * 6
    if cultura:
        cond.append("cultura = ? COLLATE NOCASE")
        args.append(cultura.strip())
    if cond:
        consulta += " WHERE " + " AND ".join(cond)
    consulta += " ORDER BY cultura, id_registro LIMIT ?"
    args.append(limite)
    with db.conectar() as con:
        return [dict(l) for l in con.execute(consulta, args).fetchall()]


def _tokens(texto: Optional[str]) -> List[str]:
    return [t.strip().lower() for t in (texto or "").split(";") if t.strip()]


def _casa(tokens: List[str], especie: str, genero: str) -> Optional[str]:
    """'especie' se um token e o nome da especie; 'genero' se e o genero."""
    if especie and especie in tokens:
        return "especie"
    if genero and genero in tokens:
        return "genero"
    return None


def _nomes(tax) -> tuple:
    if tax is None:
        return "", ""
    nome = (tax.scientific_name or "").strip().lower()
    partes = nome.split()
    especie = " ".join(partes[:2]) if len(partes) >= 2 else nome
    genero = (tax.genus or (partes[0] if partes else "")).strip().lower()
    return especie, genero


def relacionadas(tax_porta, tax_enxerto, limite: int = MAX_RELACIONADAS) -> dict:
    """Registros da literatura que tocam o par consultado, respeitando a
    orientacao (porta-enxerto com porta-enxerto, copa com copa).

    `correspondencia`:
      - "especie": as duas pontas casam pelo nome da especie;
      - "genero": ao menos uma ponta casa so pelo genero (a fonte falou de outra
        cultivar, hibrido ou especie do mesmo genero). E pista, nao resposta.
    Devolve {"total": n, "registros": [...]} com os mais especificos primeiro."""
    if tax_porta is None or tax_enxerto is None:
        return {"total": 0, "registros": []}
    p_esp, p_gen = _nomes(tax_porta)
    e_esp, e_gen = _nomes(tax_enxerto)
    achados = []
    for r in listar(limite=10000):
        lado_porta = _casa(_tokens(r["porta_taxon"]), p_esp, p_gen)
        lado_copa = _casa(_tokens(r["copa_taxon"]), e_esp, e_gen)
        if not lado_porta or not lado_copa:
            continue
        r["correspondencia"] = "especie" if lado_porta == lado_copa == "especie" else "genero"
        achados.append(r)
    achados.sort(key=lambda r: (r["correspondencia"] != "especie", r["tipo_dado"] != "Resultado do estudo",
                                r["id_registro"]))
    return {"total": len(achados), "registros": achados[:limite]}
