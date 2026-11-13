"""
Preparo do banco Enxert.DB (SQLite), usado pelo menu (interface_enxert_db.py),
pela automacao (auto_enxert_db.py) e pela pagina Catalogo do Enxert.IA.

O que `preparar(caminho)` faz, nesta ordem:
1. Se o arquivo existe mas tem estrutura incompativel, RENOMEIA para
   enxert.db.bak-AAAAMMDD-HHMMSS (nunca apaga) e cria um banco novo.
2. Aplica enxert_db.sql: estrutura sempre; dados iniciais so se o catalogo
   estiver vazio.
3. Migra bancos antigos: acrescenta as colunas id_fonte, trecho e conferido
   em Compatibilidade, se faltarem.
4. Aplica literatura_enxert_db.sql (registros das 5 fontes abertas). E
   idempotente: plantas e combinacoes que ja existem nao sao duplicadas nem
   sobrescritas.
Cada script roda dentro de uma transacao: ou entra tudo, ou nada.
"""

import os
import sqlite3
from datetime import datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
SQL_BASE = os.path.join(PASTA, "enxert_db.sql")
SQL_LITERATURA = os.path.join(PASTA, "literatura_enxert_db.sql")
DB_PADRAO = os.path.join(PASTA, "enxert.db")

# Colunas que cada tabela precisa ter (as novas colunas de fonte sao migradas, nao exigidas).
ESTRUTURA_ESPERADA = {
    "Plantas": {"id_planta", "nome_comum", "nome_cientifico", "ncbi_taxid", "familia", "genero", "papel_agronomico"},
    "Metodos_Enxertia": {"id_metodo", "nome_metodo", "descricao", "tempo_cicatrizacao_dias"},
    "Compatibilidade": {"id_compatibilidade", "id_copa", "id_porta_enxerto", "status_compatibilidade",
                        "taxa_pegamento_pct", "id_metodo", "observacoes"},
    "Biomarcadores": {"id_biomarcador", "id_planta", "atividade_peroxidase", "concentracao_fenois",
                      "presenca_prunasina", "acoplamento_plasmodesmal"},
    "Atributos_Resistencia": {"id_atributo", "id_porta_enxerto", "resistencia_patogenos_solo",
                              "resistencia_doencas_parte_aerea", "tolerancia_estresse_abiotico",
                              "efeito_porte_vigor"},
}

COLUNAS_NOVAS = [
    ("id_fonte", "INTEGER REFERENCES Fontes(id_fonte)"),
    ("trecho", "TEXT"),
    ("conferido", "INTEGER NOT NULL DEFAULT 0"),
]


class ErroBanco(RuntimeError):
    pass


def estrutura_compativel(caminho):
    """True se todas as tabelas EXISTENTES tem as colunas esperadas.
    Tabelas ausentes nao contam como incompativeis: serao criadas."""
    con = sqlite3.connect(caminho)
    try:
        for tabela, colunas in ESTRUTURA_ESPERADA.items():
            existentes = {l[1] for l in con.execute(f"PRAGMA table_info({tabela})")}
            if existentes and not colunas.issubset(existentes):
                return False
        return True
    except sqlite3.DatabaseError:
        return False  # arquivo corrompido / nao e um SQLite
    finally:
        con.close()


def guardar_backup(caminho):
    destino = f"{caminho}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    os.replace(caminho, destino)
    return destino


def executar_sql(con, sql_texto):
    """Executa um script SQL de forma atomica."""
    try:
        con.executescript("BEGIN;\n" + sql_texto + "\nCOMMIT;")
    except Exception:
        if con.in_transaction:
            con.rollback()
        raise


def dividir_comandos(sql_texto):
    comandos, atual = [], []
    for linha in sql_texto.splitlines():
        if linha.strip().startswith("--"):
            continue
        atual.append(linha)
        if sqlite3.complete_statement("\n".join(atual)):
            comandos.append("\n".join(atual))
            atual = []
    return comandos


def so_estrutura(sql_texto):
    """Mantem CREATE TABLE/INDEX e descarta os INSERTs."""
    comandos = [c.strip() for c in dividir_comandos(sql_texto)]
    return ";\n".join(c for c in comandos if c.upper().startswith("CREATE")) + ";"


def catalogo_vazio(con):
    try:
        return con.execute("SELECT COUNT(*) FROM Plantas").fetchone()[0] == 0
    except sqlite3.OperationalError:
        return True


def migrar(con):
    """Acrescenta as colunas de fonte em bancos criados antes delas existirem."""
    existentes = {l[1] for l in con.execute("PRAGMA table_info(Compatibilidade)")}
    for nome, tipo in COLUNAS_NOVAS:
        if nome not in existentes:
            con.execute(f"ALTER TABLE Compatibilidade ADD COLUMN {nome} {tipo}")
    con.commit()


def _ler(caminho):
    if not os.path.exists(caminho):
        raise ErroBanco(f"Arquivo '{os.path.basename(caminho)}' nao encontrado na pasta {PASTA}.")
    with open(caminho, "r", encoding="utf-8-sig") as f:
        return f.read()


def preparar(caminho=DB_PADRAO, com_literatura=True, avisar=print):
    """Deixa o banco pronto para uso. Devolve um dicionario com o que aconteceu."""
    resumo = {"backup": None, "criado": False, "literatura": False}
    if os.path.exists(caminho) and not estrutura_compativel(caminho):
        try:
            resumo["backup"] = guardar_backup(caminho)
        except OSError as e:
            raise ErroBanco(f"Nao consegui preservar o banco antigo ({e}). Feche outros programas que o usem.")
        avisar(f"⚠️ O arquivo '{os.path.basename(caminho)}' tinha estrutura incompatível. "
               f"Foi preservado como '{os.path.basename(resumo['backup'])}' e um banco novo será criado.")

    base = _ler(SQL_BASE)
    con = sqlite3.connect(caminho)
    try:
        vazio = catalogo_vazio(con)
        try:
            executar_sql(con, base if vazio else so_estrutura(base))
        except sqlite3.Error as e:
            raise ErroBanco(f"Erro ao aplicar enxert_db.sql: {e}"
                            " (se for 'UNIQUE', o banco ja tem combinacoes duplicadas: remova as repetidas)")
        resumo["criado"] = vazio
        migrar(con)
        if com_literatura and os.path.exists(SQL_LITERATURA):
            try:
                executar_sql(con, _ler(SQL_LITERATURA))
                resumo["literatura"] = True
            except sqlite3.Error as e:
                raise ErroBanco(f"Erro ao aplicar literatura_enxert_db.sql: {e}")
    finally:
        con.close()
    return resumo


def conectar(caminho=DB_PADRAO):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    return con
