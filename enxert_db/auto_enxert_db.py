#!/usr/bin/env python3
"""
Enxert.DB - Automacao do cruzamento de culturas (v2)
====================================================

Dado um par copa x porta-enxerto, mostra o que o catalogo ja sabe e, se o par
ainda nao tem registro, calcula uma ESTIMATIVA pelo parentesco taxonomico.

O que mudou em relacao a versao anterior (cada item foi reproduzido no
enxert_2.db antes de corrigir):
- A versao anterior SOBRESCREVIA registros reais: rodar o lote trocou o
  registro Melancia x Abobora (98%, "Excelente resistencia a Fusarium...",
  dado da equipe) por "85%, Afinidade moderada", que e saida da regra.
  Agora a automacao nunca altera a tabela Compatibilidade.
- A versao anterior gravava 95%, 85% ou 0% em taxa_pegamento_pct como se
  fosse medicao. Taxa de pegamento e um dado de ensaio; a estimativa por
  parentesco vai para a tabela Estimativas, separada, marcada como regra.
- A regra antiga dava 95% "Compativel" para qualquer par do mesmo genero, mas
  a propria literatura do catalogo mostra laranjeira 'Pera' incompativel com
  citrumelo 'Swingle' (mesmo genero no catalogo). A escala agora e a mesma do
  Enxert.IA (0,95 / 0,75 / 0,40 / 0,05) e vem como indice, nao como %.
- A versao anterior cadastrava plantas novas com TaxID digitado no codigo
  (tomate 3649, que e do mamao; ameixeira Marianna 3760, que e do pessegueiro).
  Agora plantas desconhecidas nao sao cadastradas: cadastre pelo menu
  (opcao 4) e confira o TaxID pela opcao 7.

Uso:
    python auto_enxert_db.py "Citrus sinensis (Pera D6)" "Citrus limonia"
    python auto_enxert_db.py --batch
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import banco_enxert_db as banco

DB_FILE = os.path.join(banco.PASTA, "enxert.db")

SCHEMA_ESTIMATIVAS = """
CREATE TABLE IF NOT EXISTS Estimativas (
    id_estimativa INTEGER PRIMARY KEY AUTOINCREMENT,
    id_copa INTEGER NOT NULL REFERENCES Plantas(id_planta),
    id_porta_enxerto INTEGER NOT NULL REFERENCES Plantas(id_planta),
    indice REAL NOT NULL CHECK (indice >= 0 AND indice <= 1),
    nivel TEXT NOT NULL,
    regra TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (id_copa, id_porta_enxerto)
);
"""

# Mesmos valores do motor de regras do Enxert.IA (app/compatibility.py).
ESCALA = [("mesma especie", 0.95, "alta"), ("mesmo genero", 0.75, "provável"),
          ("mesma familia", 0.40, "incerta"), ("familias diferentes", 0.05, "improvável")]


def _especie(nome_cientifico):
    """'Citrus sinensis (Pera D6)' -> 'citrus sinensis'."""
    base = nome_cientifico.split("(")[0].strip().lower()
    return " ".join(base.split()[:2])


def estimar(copa, porta):
    """copa/porta: dict com nome_cientifico, familia, genero. Devolve (indice, nivel, regra) ou None."""
    desconhecido = {"", "não informado", "nao informado", "desconhecida", "desconhecido"}
    if copa["familia"].lower() in desconhecido or porta["familia"].lower() in desconhecido:
        return None
    if _especie(copa["nome_cientifico"]) == _especie(porta["nome_cientifico"]) and " x " not in porta["nome_cientifico"]:
        regra = ESCALA[0]
    elif copa["genero"].lower() not in desconhecido and copa["genero"].lower() == porta["genero"].lower():
        regra = ESCALA[1]
    elif copa["familia"].lower() == porta["familia"].lower():
        regra = ESCALA[2]
    else:
        regra = ESCALA[3]
    return regra[1], regra[2], f"estimativa por parentesco: {regra[0]}"


def _planta(con, nome):
    linha = con.execute(
        "SELECT id_planta, nome_comum, nome_cientifico, familia, genero FROM Plantas "
        "WHERE LOWER(nome_cientifico) = LOWER(?)", (nome.strip(),)).fetchone()
    if not linha:
        return None
    return dict(zip(("id", "nome_comum", "nome_cientifico", "familia", "genero"), linha))


def automatizar_relacao(nome_copa, nome_pe, db_file=DB_FILE):
    banco.preparar(db_file)
    con = banco.conectar(db_file)
    try:
        con.executescript(SCHEMA_ESTIMATIVAS)
        copa, pe = _planta(con, nome_copa), _planta(con, nome_pe)
        faltando = [n for n, p in ((nome_copa, copa), (nome_pe, pe)) if p is None]
        if faltando:
            print(f"⚠️ Não está no catálogo: {', '.join(faltando)}. "
                  "Cadastre pelo menu (opção 4) antes; esta automação não cadastra plantas.")
            return None
        print(f"→ {copa['nome_comum']} ({copa['nome_cientifico']}) sobre {pe['nome_comum']} ({pe['nome_cientifico']})")

        registros = con.execute("""
            SELECT c.status_compatibilidade, c.taxa_pegamento_pct, m.nome_metodo, f.referencia, c.conferido
            FROM Compatibilidade c
            LEFT JOIN Metodos_Enxertia m ON c.id_metodo = m.id_metodo
            LEFT JOIN Fontes f ON c.id_fonte = f.id_fonte
            WHERE c.id_copa = ? AND c.id_porta_enxerto = ?""", (copa["id"], pe["id"])).fetchall()
        if registros:
            print(f"✅ Já há {len(registros)} registro(s) no catálogo para esse par; nada foi alterado:")
            for status, taxa, metodo, ref, conferido in registros:
                origem = ("fonte: " + ref[:70] + ("…" if len(ref) > 70 else "") +
                          (" (conferido)" if conferido else " (a conferir)")) if ref else "registro da equipe"
                print(f"   • {status or 'não classificado pela fonte'} | pegamento: "
                      f"{'—' if taxa is None else str(taxa) + '%'} | método: {metodo or '—'} | {origem}")
            return {"tipo": "registro", "registros": len(registros)}

        est = estimar(copa, pe)
        if est is None:
            print("⚠️ Família de uma das plantas não informada: não dá para estimar.")
            return None
        indice, nivel, regra = est
        con.execute("""
            INSERT INTO Estimativas (id_copa, id_porta_enxerto, indice, nivel, regra) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id_copa, id_porta_enxerto) DO UPDATE SET
                indice = excluded.indice, nivel = excluded.nivel, regra = excluded.regra,
                criado_em = datetime('now')""", (copa["id"], pe["id"], indice, nivel, regra))
        con.commit()
        print(f"ℹ️ Sem registro no catálogo. Estimativa: índice {indice:.2f} ({nivel}), {regra}.")
        print("   Isto é uma regra, não uma medição: não entra como taxa de pegamento.")
        return {"tipo": "estimativa", "indice": indice, "nivel": nivel}
    finally:
        con.close()


def processar_lote_automatico(db_file=DB_FILE):
    pares = [
        ("Solanum lycopersicum", "Solanum paniculatum"),          # tomateiro sobre jurubeba
        ("Solanum melongena", "Solanum paniculatum"),             # berinjela sobre jurubeba
        ("Citrullus lanatus", "Cucurbita maxima"),                # melancia sobre abobora
        ("Citrus sinensis (Pera D6)", "Citrus limonia"),          # laranjeira Pera sobre limoeiro Cravo
        ("Citrus sinensis (Pera B)", "Citrus paradisi x Poncirus trifoliata (Swingle)"),
    ]
    print("🔄 Processando lote de cruzamentos...")
    for copa, pe in pares:
        automatizar_relacao(copa, pe, db_file)
        print("-" * 75)


if __name__ == "__main__":
    print("=" * 75)
    print("      ENXERT.DB - AUTOMAÇÃO DE CRUZAMENTO DE CULTURAS")
    print("=" * 75)
    if len(sys.argv) >= 3:
        automatizar_relacao(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "--batch":
        processar_lote_automatico()
    else:
        print("Modo interativo:")
        c = input("Nome científico da COPA (ex: Citrus sinensis (Pera D6)): ").strip()
        p = input("Nome científico do PORTA-ENXERTO (ex: Citrus limonia): ").strip()
        if c and p:
            automatizar_relacao(c, p)
