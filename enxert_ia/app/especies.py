"""
Fontes locais de especies (modulares).

O sistema conhece especies por duas fontes locais, consultadas nesta ordem
quando a GBIF e o Reflora nao respondem:

1. `FonteArquivo`: a lista que vem com o projeto (app/taxonomy_fallback.json).
   So leitura.
2. `FonteUsuario`: plantas cadastradas por quem usa o sistema (tabela
   `especies_usuario` no banco data/enxertia.db). Pode adicionar e remover.

Para acrescentar outra fonte (por exemplo, um CSV de uma cooperativa), basta
criar uma classe com `listar()` e `buscar(nome)` e coloca-la em
`TaxonomyService(fontes_locais=[...])`.

Validacoes do cadastro: o nome cientifico precisa ter genero e especie
("Genero especie", cultivar opcional entre parenteses); o genero informado
precisa ser a primeira palavra do nome; a familia precisa terminar em
"-aceae" (ou ser um dos oito nomes alternativos aceitos pelo codigo de
nomenclatura botanica). Isso evita que um erro de digitacao vire uma familia
nova e mude o resultado das regras taxonomicas.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import List, Optional

from app import db

ARQUIVO_PADRAO = Path(__file__).parent / "taxonomy_fallback.json"

FAMILIAS_ALTERNATIVAS = {"compositae", "cruciferae", "gramineae", "guttiferae", "labiatae",
                         "leguminosae", "palmae", "umbelliferae"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS especies_usuario (
    scientific_name TEXT PRIMARY KEY COLLATE NOCASE,
    common_name TEXT,
    family TEXT NOT NULL,
    genus TEXT NOT NULL,
    observacoes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class EspecieInvalida(ValueError):
    pass


class EspecieDuplicada(ValueError):
    pass


class FonteArquivo:
    """Lista de especies que vem com o projeto (somente leitura)."""
    origem = "base"

    def __init__(self, caminho: Path = ARQUIVO_PADRAO):
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        self._por_nome = {e["scientific_name"].lower(): {**e, "origem": self.origem} for e in dados["species"]}

    def listar(self) -> List[dict]:
        return list(self._por_nome.values())

    def buscar(self, nome: str) -> Optional[dict]:
        return self._por_nome.get(nome.strip().lower())


class FonteUsuario:
    """Plantas cadastradas pelo usuario, guardadas no banco SQLite do Enxert.IA."""
    origem = "usuario"

    def _con(self):
        con = sqlite3.connect(db.db_path())
        con.row_factory = sqlite3.Row
        con.executescript(SCHEMA)
        return con

    def _dict(self, linha) -> dict:
        d = {k: linha[k] for k in ("scientific_name", "common_name", "family", "genus", "observacoes", "criado_em")}
        if not d["common_name"]:
            d.pop("common_name")
        return {**d, "origem": self.origem}

    def listar(self) -> List[dict]:
        try:
            con = self._con()
        except sqlite3.Error:
            return []
        try:
            return [self._dict(l) for l in con.execute("SELECT * FROM especies_usuario ORDER BY scientific_name")]
        finally:
            con.close()

    def buscar(self, nome: str) -> Optional[dict]:
        try:
            con = self._con()
        except sqlite3.Error:
            return None
        try:
            linha = con.execute("SELECT * FROM especies_usuario WHERE scientific_name = ?", (nome.strip(),)).fetchone()
            return self._dict(linha) if linha else None
        finally:
            con.close()

    def adicionar(self, scientific_name: str, family: str, genus: str,
                  common_name: Optional[str] = None, observacoes: Optional[str] = None) -> dict:
        nome = normalizar_nome(scientific_name)
        familia = (family or "").strip().capitalize()
        genero = (genus or "").strip().capitalize()
        validar(nome, familia, genero)
        con = self._con()
        try:
            con.execute(
                "INSERT INTO especies_usuario (scientific_name, common_name, family, genus, observacoes) "
                "VALUES (?, ?, ?, ?, ?)",
                (nome, (common_name or "").strip() or None, familia, genero, (observacoes or "").strip() or None))
            con.commit()
        except sqlite3.IntegrityError:
            raise EspecieDuplicada(f"'{nome}' ja esta cadastrada.")
        finally:
            con.close()
        return self.buscar(nome)

    def remover(self, nome: str) -> bool:
        con = self._con()
        try:
            n = con.execute("DELETE FROM especies_usuario WHERE scientific_name = ?", (nome.strip(),)).rowcount
            con.commit()
            return n > 0
        finally:
            con.close()


def normalizar_nome(nome: str) -> str:
    """'citrus  SINENSIS (Pera)' -> 'Citrus sinensis (Pera)'."""
    nome = re.sub(r"\s+", " ", (nome or "").strip())
    base, sep, resto = nome.partition("(")
    palavras = base.split()
    if not palavras:
        return nome
    base = " ".join([palavras[0].capitalize()] + [p.lower() for p in palavras[1:]])
    return base + (" (" + resto.strip() if sep else "")


def validar(nome: str, familia: str, genero: str) -> None:
    if not re.match(r"^[A-Z][a-z]+ (x )?[a-z][a-z\-]+( var\. [a-z\-]+)?( \(.+\))?$", nome):
        raise EspecieInvalida("Use o nome cientifico no formato 'Genero especie' (ex: Annona cherimola), "
                              "com a cultivar opcional entre parenteses.")
    if not genero or not familia:
        raise EspecieInvalida("Informe a familia e o genero (ou use 'preencher pela GBIF').")
    if genero.lower() != nome.split()[0].lower():
        raise EspecieInvalida(f"O genero precisa ser a primeira palavra do nome cientifico ('{nome.split()[0]}').")
    if not (familia.lower().endswith("aceae") or familia.lower() in FAMILIAS_ALTERNATIVAS):
        raise EspecieInvalida("A familia botanica termina em '-aceae' (ex: Rosaceae, Solanaceae). Confira a grafia.")
