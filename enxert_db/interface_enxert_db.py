#!/usr/bin/env python3
"""
Enxert.DB - Interface Python v7
===============================
Gerencia o banco Enxert.DB (SQLite).

O que mudou em relacao a v4 (todos os itens foram reproduzidos antes de corrigir):
- Nunca apaga o banco do usuario. Se o arquivo existente tiver estrutura
  incompativel, ele e RENOMEADO (enxert.db.bak-AAAAMMDD-HHMMSS) e um banco novo
  e criado. (v4 fazia os.remove e perdia os cadastros.)
- Tabelas que faltam sao criadas (v4 so olhava a coluna papel_agronomico e
  quebrava com "no such table" em bancos parciais).
- Chaves estrangeiras passam a ser validadas (PRAGMA foreign_keys=ON). Antes o
  menu 5 aceitava IDs de planta que nao existem.
- Mesmo par copa x porta-enxerto x metodo nao pode ser cadastrado duas vezes.
- Entradas invalidas pedem de novo, em vez de virar "Compativel / 0%" em silencio.
- Copa e porta-enxerto nao podem ser a mesma planta.
- O enxert_db.sql agora pode ser executado varias vezes (INSERT OR IGNORE) e nao
  tem BEGIN/COMMIT, que dao "cannot start a transaction within a transaction"
  quando o .sql e executado dentro de uma transacao ja aberta.
- TaxID do tomate corrigido: 3649 e Carica papaya; Solanum lycopersicum = 4081.
- v6: opcao 7 confere TaxID/familia/genero de cada planta contra o NCBI Taxonomy
  (o cadastro de especies do GenBank). Precisa do arquivo ncbi_taxonomia.py ao lado.

- v7: o preparo do banco foi para banco_enxert_db.py (usado tambem pela pagina
  Catalogo do Enxert.IA). Entram 45 combinacoes de 5 fontes abertas
  (literatura_enxert_db.sql), cada uma com a fonte, o trecho e a marca
  "conferido". As buscas (opcoes 2 e 3) mostram de onde veio cada registro.
  Bancos antigos ganham as colunas novas sem perder nada.

Precisa, na mesma pasta: banco_enxert_db.py, enxert_db.sql e
literatura_enxert_db.sql (e ncbi_taxonomia.py para a opcao 7).
"""

import os
import sqlite3
import sys

# Evita UnicodeEncodeError com emojis em terminais Windows antigos / saida redirecionada.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "enxert.db")

STATUS_VALIDOS = [
    "Compatível",
    "Incompatibilidade Localizada",
    "Incompatibilidade Translocada",
    "Incompatível",
]

import banco_enxert_db as banco  # noqa: E402

_banco_pronto = False


# ---------------------------------------------------------------------------
# Banco: preparo e conexao
# ---------------------------------------------------------------------------

def _preparar_banco():
    global _banco_pronto
    if _banco_pronto:
        return
    try:
        resumo = banco.preparar(DB_FILE)
    except banco.ErroBanco as e:
        sys.exit(f"❌ Não foi possível preparar o banco: {e}")
    if resumo["criado"]:
        print("✅ Banco Enxert.DB inicializado com os dados iniciais e os registros da literatura.")
    _banco_pronto = True


def get_connection():
    _preparar_banco()
    return banco.conectar(DB_FILE)  # PRAGMA foreign_keys = ON


# ---------------------------------------------------------------------------
# Entrada de dados
# ---------------------------------------------------------------------------

def ler_int(prompt):
    try:
        return int(input(prompt).strip())
    except ValueError:
        print("❌ Digite um número inteiro.")
        return None


def ler_opcao(prompt, validas):
    """Repete ate o usuario digitar uma opcao valida (ou deixar vazio p/ cancelar)."""
    while True:
        v = input(prompt).strip()
        if v == "":
            return None
        if v in validas:
            return v
        print(f"❌ Opção inválida. Escolha entre: {', '.join(validas)} (ou Enter para cancelar).")


def ler_taxa():
    while True:
        v = input("Taxa de pegamento esperada % (0 a 100, ex: 95.0): ").strip().replace(",", ".")
        try:
            taxa = float(v)
        except ValueError:
            print("❌ Digite um número (ex: 95.0).")
            continue
        if 0 <= taxa <= 100:
            return taxa
        print("❌ A taxa precisa estar entre 0 e 100.")


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _fmt_taxa(valor):
    return "não informada" if valor is None else f"{valor}%"


def listar_plantas():
    conn = get_connection()
    try:
        plantas = conn.execute("""
            SELECT id_planta, nome_comum, nome_cientifico, familia, papel_agronomico
            FROM Plantas ORDER BY id_planta
        """).fetchall()
    finally:
        conn.close()

    print("\n" + "=" * 92)
    print("CATÁLOGO DE PLANTAS CADASTRADAS NO ENXERT.DB")
    print("=" * 92)
    print(f"{'ID':<4} | {'Nome Comum':<32} | {'Nome Científico':<50} | Papel")
    print("-" * 92)
    for p in plantas:
        print(f"{p[0]:<4} | {p[1]:<32} | {p[2]:<50} | {p[4]}")
    print("=" * 92 + "\n")


def _planta(conn, id_planta):
    return conn.execute(
        "SELECT nome_comum, nome_cientifico FROM Plantas WHERE id_planta = ?", (id_planta,)
    ).fetchone()


def _imprimir_resultados(resultados, icone, vazio):
    if not resultados:
        print(vazio)
        return
    for r in resultados:
        print(f"{icone} {r[0]} ({r[1]})")
        print(f"   • Status: {r[2] or 'não classificado pela fonte'}")
        print(f"   • Taxa de Pegamento: {_fmt_taxa(r[3])}")
        print(f"   • Método: {r[4] or 'Não especificado'}")
        print(f"   • Observações: {r[5] or '—'}")
        if r[6]:
            marca = "conferido no PDF" if r[7] else "a conferir no PDF"
            print(f"   • Fonte ({marca}): {r[6]}")
            if r[8]:
                print(f"     {r[8]}")
        else:
            print("   • Fonte: registro da equipe")
        print("-" * 80)


def buscar_porta_enxertos_para_copa(id_copa):
    conn = get_connection()
    try:
        copa = _planta(conn, id_copa)
        if not copa:
            print("❌ Planta não encontrada!")
            return
        print("\n" + "=" * 80)
        print(f"RECOMENDAÇÕES DE PORTA-ENXERTO PARA A COPA: {copa[0]} ({copa[1]})")
        print("=" * 80)
        resultados = conn.execute("""
            SELECT p.nome_comum, p.nome_cientifico, c.status_compatibilidade,
                   c.taxa_pegamento_pct, m.nome_metodo, c.observacoes,
                   f.referencia, c.conferido, f.url
            FROM Compatibilidade c
            JOIN Plantas p ON c.id_porta_enxerto = p.id_planta
            LEFT JOIN Metodos_Enxertia m ON c.id_metodo = m.id_metodo
            LEFT JOIN Fontes f ON c.id_fonte = f.id_fonte
            WHERE c.id_copa = ?
            ORDER BY c.taxa_pegamento_pct IS NULL, c.taxa_pegamento_pct DESC
        """, (id_copa,)).fetchall()
    finally:
        conn.close()
    _imprimir_resultados(resultados, "🌱 Porta-Enxerto:",
                         "⚠️ Nenhuma combinação registrada ainda para esta planta como enxerto (copa).")


def buscar_copas_para_porta_enxerto(id_pe):
    conn = get_connection()
    try:
        pe = _planta(conn, id_pe)
        if not pe:
            print("❌ Planta não encontrada!")
            return
        print("\n" + "=" * 80)
        print(f"COPAS (ENXERTOS) COMPATÍVEIS PARA O PORTA-ENXERTO: {pe[0]} ({pe[1]})")
        print("=" * 80)
        resultados = conn.execute("""
            SELECT p.nome_comum, p.nome_cientifico, c.status_compatibilidade,
                   c.taxa_pegamento_pct, m.nome_metodo, c.observacoes,
                   f.referencia, c.conferido, f.url
            FROM Compatibilidade c
            JOIN Plantas p ON c.id_copa = p.id_planta
            LEFT JOIN Metodos_Enxertia m ON c.id_metodo = m.id_metodo
            LEFT JOIN Fontes f ON c.id_fonte = f.id_fonte
            WHERE c.id_porta_enxerto = ?
            ORDER BY c.taxa_pegamento_pct IS NULL, c.taxa_pegamento_pct DESC
        """, (id_pe,)).fetchall()
    finally:
        conn.close()
    _imprimir_resultados(resultados, "🍎 Enxerto/Copa:",
                         "⚠️ Nenhuma copa registrada ainda para este porta-enxerto.")


# ---------------------------------------------------------------------------
# Cadastros
# ---------------------------------------------------------------------------

def cadastrar_planta():
    print("\n--- CADASTRO DE NOVA PLANTA NO CATÁLOGO ---")
    nome_comum = input("Nome Comum (ex: Maracujá Doce): ").strip()
    nome_cientifico = input("Nome Científico (ex: Passiflora alata): ").strip()
    taxid = input("NCBI TaxID (opcional, Enter se não tiver): ").strip()
    familia = input("Família Botânica (ex: Passifloraceae): ").strip()
    genero = input("Gênero Botânico (ex: Passiflora): ").strip()

    faltando = [n for n, v in [("Nome Comum", nome_comum), ("Nome Científico", nome_cientifico),
                               ("Família", familia), ("Gênero", genero)] if not v]
    if faltando:
        print(f"❌ Campos obrigatórios em branco: {', '.join(faltando)}. Nada foi cadastrado.")
        return
    if taxid and not taxid.isdigit():
        print("❌ O TaxID precisa ser um número (ou deixe em branco). Nada foi cadastrado.")
        return
    taxid_val = int(taxid) if taxid else None

    print("Selecione o papel agronômico habitual:")
    print("1. Enxerto (Copa)\n2. Porta-Enxerto\n3. Ambos")
    op = ler_opcao("Opção (1-3) [Enter = Ambos]: ", ["1", "2", "3"])
    papel = {"1": "Enxerto", "2": "Porta-Enxerto", "3": "Ambos", None: "Ambos"}[op]

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO Plantas (nome_comum, nome_cientifico, ncbi_taxid, familia, genero, papel_agronomico)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome_comum, nome_cientifico, taxid_val, familia, genero, papel))
        conn.commit()
        print(f"✅ Planta '{nome_comum}' cadastrada com sucesso! (ID: {cur.lastrowid})")
    except sqlite3.IntegrityError:
        print(f"❌ Já existe uma planta com o nome científico '{nome_cientifico}'.")
    finally:
        conn.close()


def _listar_metodos():
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id_metodo, nome_metodo, tempo_cicatrizacao_dias FROM Metodos_Enxertia ORDER BY id_metodo"
        ).fetchall()
    finally:
        conn.close()


def cadastrar_compatibilidade():
    listar_plantas()
    print("--- VINCULAR ENXERTO E PORTA-ENXERTO ---")
    id_copa = ler_int("ID da planta que atuará como ENXERTO (Copa): ")
    if id_copa is None:
        return
    id_pe = ler_int("ID da planta que atuará como PORTA-ENXERTO: ")
    if id_pe is None:
        return
    if id_copa == id_pe:
        print("❌ Copa e porta-enxerto não podem ser a mesma planta.")
        return

    conn = get_connection()
    try:
        copa, pe = _planta(conn, id_copa), _planta(conn, id_pe)
    finally:
        conn.close()
    if not copa or not pe:
        print(f"❌ ID inexistente no catálogo ({'copa' if not copa else 'porta-enxerto'}). Nada foi gravado.")
        return
    print(f"→ {copa[0]} ({copa[1]})  sobre  {pe[0]} ({pe[1]})")

    print("\nStatus de Compatibilidade:")
    for i, s in enumerate(STATUS_VALIDOS, 1):
        print(f"{i}. {s}")
    op = ler_opcao("Escolha (1-4, Enter cancela): ", [str(i) for i in range(1, 5)])
    if op is None:
        print("Cancelado.")
        return
    status = STATUS_VALIDOS[int(op) - 1]

    taxa = ler_taxa()

    print("\nMétodo de enxertia:")
    metodos = _listar_metodos()
    for m in metodos:
        print(f"{m[0]}. {m[1]} ({m[2]} dias)")
    ids_metodo = [str(m[0]) for m in metodos]
    op_m = ler_opcao("Escolha o método (Enter = não especificado): ", ids_metodo)
    id_metodo = int(op_m) if op_m else None

    obs = input("Observações técnicas: ").strip() or None

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO Compatibilidade
                (id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id_copa, id_pe, status, taxa, id_metodo, obs))
        conn.commit()
        print("✅ Relação de compatibilidade gravada com sucesso!")
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            print("❌ Esse par (copa × porta-enxerto × método) já está cadastrado.")
        else:
            print(f"❌ Não foi possível gravar: {e}")
    finally:
        conn.close()



# ---------------------------------------------------------------------------
# NCBI Taxonomy (GenBank)
# ---------------------------------------------------------------------------

_ROTULO_STATUS = {
    "ok": "✅ ok",
    "sem_taxid": "➕ sem TaxID no banco",
    "diverge": "❗ TaxID diverge",
    "nao_encontrado": "❓ não encontrado no NCBI",
    "ambiguo": "❓ ambíguo",
    "hibrido": "– híbrido (não consultado)",
}


def verificar_taxonomia_ncbi():
    """Opcao 7: confere cada planta contra o NCBI Taxonomy e, se o usuario
    confirmar, corrige/preenche SOMENTE a coluna ncbi_taxid."""
    try:
        import ncbi_taxonomia as ncbi
    except ImportError:
        print("❌ Não encontrei 'ncbi_taxonomia.py' na mesma pasta deste script.")
        return

    conn = get_connection()
    try:
        linhas = conn.execute("""
            SELECT id_planta, nome_comum, nome_cientifico, ncbi_taxid, familia, genero
            FROM Plantas ORDER BY id_planta
        """).fetchall()
    finally:
        conn.close()

    print(f"\nConsultando o NCBI Taxonomy para {len(linhas)} plantas (cerca de 1 s por planta)...")

    def progresso(i, total, nome):
        print(f"  [{i}/{total}] {nome}", flush=True)

    try:
        resultados = ncbi.verificar_plantas(linhas, progresso)
    except ncbi.NCBIErro as e:
        print(f"\n❌ Não consegui falar com o NCBI: {e}")
        print("   Nada foi alterado no banco.")
        return

    print("\n" + "=" * 100)
    print(f"{'ID':<3} | {'Nome no banco':<42} | {'TaxID banco':<11} | {'TaxID NCBI':<10} | Situação")
    print("-" * 100)
    for r in resultados:
        print(f"{r['id_planta']:<3} | {r['nome_cientifico'][:42]:<42} | {str(r['taxid_db'] or '—'):<11} | "
              f"{str(r['taxid_ncbi'] or '—'):<10} | {_ROTULO_STATUS[r['status']]}")
        if r["status"] == "diverge":
            print(f"      ↳ NCBI {r['taxid_ncbi']} = {r['nome_ncbi']} ({r['rank']})")
        for aviso in r["avisos"]:
            print(f"      ↳ ⚠️ {aviso}")
    print("=" * 100)

    corrigiveis = [r for r in resultados if r["status"] in ("diverge", "sem_taxid")]
    if not corrigiveis:
        print("Nada a corrigir.")
        return
    print(f"\n{len(corrigiveis)} planta(s) com TaxID para corrigir/preencher "
          f"(só a coluna ncbi_taxid será alterada).")
    if input("Aplicar? (s/N): ").strip().lower() not in ("s", "sim", "y"):
        print("Nada foi alterado.")
        return

    conn = get_connection()
    try:
        conn.executemany("UPDATE Plantas SET ncbi_taxid = ? WHERE id_planta = ?",
                         [(r["taxid_ncbi"], r["id_planta"]) for r in corrigiveis])
        conn.commit()
        print(f"✅ {len(corrigiveis)} TaxID(s) atualizado(s).")
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def menu_principal():
    while True:
        print("\n" + "=" * 50)
        print("     SISTEMA ENXERT.DB - GERENCIADOR DE ENXERTIA")
        print("=" * 50)
        print("1. Listar todas as plantas cadastradas")
        print("2. Buscar Porta-Enxertos para um Enxerto (Copa)")
        print("3. Buscar Enxertos (Copas) para um Porta-Enxerto")
        print("4. Cadastrar nova Planta no Catálogo")
        print("5. Cadastrar relação de Compatibilidade (Copa x Porta-Enxerto)")
        print("6. Sair")
        print("7. Conferir/corrigir TaxID e taxonomia pelo NCBI (GenBank)")
        print("=" * 50)
        try:
            opcao = input("Escolha uma opção (1-7): ").strip()
        except EOFError:
            break

        if opcao == "1":
            listar_plantas()
        elif opcao == "2":
            listar_plantas()
            id_c = ler_int("Digite o ID da planta Enxerto/Copa: ")
            if id_c is not None:
                buscar_porta_enxertos_para_copa(id_c)
        elif opcao == "3":
            listar_plantas()
            id_p = ler_int("Digite o ID do Porta-Enxerto: ")
            if id_p is not None:
                buscar_copas_para_porta_enxerto(id_p)
        elif opcao == "4":
            cadastrar_planta()
        elif opcao == "5":
            cadastrar_compatibilidade()
        elif opcao == "6":
            print("Encerrando o Enxert.DB. Até logo!")
            break
        elif opcao == "7":
            verificar_taxonomia_ncbi()
        else:
            print("❌ Opção inválida, tente novamente.")




if __name__ == "__main__":
    menu_principal()
