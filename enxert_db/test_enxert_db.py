"""Banco Enxert.DB: preparo, migracao, registros da literatura e automacao."""
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

import banco_enxert_db as banco  # noqa: E402
import auto_enxert_db as auto  # noqa: E402


def _n(db, sql, *args):
    return sqlite3.connect(db).execute(sql, args).fetchone()[0]


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "enxert.db")


def test_banco_novo_tem_base_e_literatura(db):
    r = banco.preparar(db, avisar=lambda m: None)
    assert r["criado"] and r["literatura"]
    assert _n(db, "SELECT COUNT(*) FROM Fontes") == 5
    assert _n(db, "SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NULL") == 10   # registros da equipe
    assert _n(db, "SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL") == 45


def test_preparar_de_novo_nao_duplica(db):
    banco.preparar(db)
    antes = (_n(db, "SELECT COUNT(*) FROM Plantas"), _n(db, "SELECT COUNT(*) FROM Compatibilidade"))
    banco.preparar(db)
    assert antes == (_n(db, "SELECT COUNT(*) FROM Plantas"), _n(db, "SELECT COUNT(*) FROM Compatibilidade"))


def test_literatura_nada_conferido_e_nenhum_taxid_inventado(db):
    banco.preparar(db)
    assert _n(db, "SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL AND conferido = 1") == 0
    assert _n(db, "SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL AND (trecho IS NULL OR trecho = '')") == 0
    novas = _n(db, "SELECT COUNT(*) FROM Plantas WHERE id_planta > 16 AND ncbi_taxid IS NOT NULL")
    assert novas == 0


def test_taxa_de_pegamento_so_onde_a_fonte_mede(db):
    banco.preparar(db)
    com_taxa = sqlite3.connect(db).execute(
        "SELECT DISTINCT id_fonte FROM Compatibilidade WHERE id_fonte IS NOT NULL AND taxa_pegamento_pct IS NOT NULL").fetchall()
    assert com_taxa == [(5,)]          # so o estudo de melancia mede sobrevivencia


def test_registro_da_equipe_nao_e_sobrescrito(db):
    banco.preparar(db)
    assert _n(db, "SELECT taxa_pegamento_pct FROM Compatibilidade WHERE id_compatibilidade = 10") == 98.0


def test_migra_banco_sem_colunas_de_fonte(tmp_path):
    antigo = tmp_path / "enxert.db"
    con = sqlite3.connect(antigo)
    sql = (AQUI / "enxert_db.sql").read_text(encoding="utf-8")
    sql = sql.replace("    id_fonte INTEGER,\n    trecho TEXT,\n    conferido INTEGER NOT NULL DEFAULT 0,\n", "")
    sql = sql.replace(",\n    FOREIGN KEY(id_fonte) REFERENCES Fontes(id_fonte)", "")
    sql = sql.replace(' (id_compatibilidade, id_copa, id_porta_enxerto, status_compatibilidade, taxa_pegamento_pct, id_metodo, observacoes)', '')
    con.executescript(sql)
    con.execute("INSERT INTO Plantas (nome_comum, nome_cientifico, familia, genero, papel_agronomico) "
                "VALUES ('Minha planta', 'Planta minha', 'X', 'Y', 'Ambos')")
    con.commit(); con.close()
    banco.preparar(str(antigo))
    assert _n(antigo, "SELECT COUNT(*) FROM Plantas WHERE nome_cientifico = 'Planta minha'") == 1   # nada se perdeu
    assert _n(antigo, "SELECT COUNT(*) FROM Compatibilidade WHERE id_fonte IS NOT NULL") == 45


def test_estrutura_incompativel_vira_backup(tmp_path):
    velho = tmp_path / "enxert.db"
    sqlite3.connect(velho).executescript("CREATE TABLE Compatibilidade (id INTEGER, grau_pegamento_pct REAL);")
    r = banco.preparar(str(velho), avisar=lambda m: None)
    assert r["backup"] and os.path.exists(r["backup"])


# ---------- automacao ----------

def test_automacao_nunca_altera_compatibilidade(db):
    banco.preparar(db)
    antes = sqlite3.connect(db).execute("SELECT * FROM Compatibilidade ORDER BY 1").fetchall()
    auto.processar_lote_automatico(db)
    depois = sqlite3.connect(db).execute("SELECT * FROM Compatibilidade ORDER BY 1").fetchall()
    assert antes == depois


def test_automacao_estima_par_sem_registro_sem_gravar_taxa(db):
    r = auto.automatizar_relacao("Citrus sinensis (Westin)", "Citrus limonia", db)
    assert r == {"tipo": "estimativa", "indice": 0.75, "nivel": "provável"}
    assert _n(db, "SELECT COUNT(*) FROM Estimativas") == 1
    auto.automatizar_relacao("Citrus sinensis (Westin)", "Citrus limonia", db)
    assert _n(db, "SELECT COUNT(*) FROM Estimativas") == 1


def test_automacao_nao_cadastra_planta_desconhecida(db):
    banco.preparar(db)
    antes = _n(db, "SELECT COUNT(*) FROM Plantas")
    assert auto.automatizar_relacao("Mangifera indica", "Citrus limonia", db) is None
    assert _n(db, "SELECT COUNT(*) FROM Plantas") == antes


def test_estimativa_por_parentesco():
    p = lambda n, f, g: {"nome_cientifico": n, "familia": f, "genero": g}
    assert auto.estimar(p("Citrus sinensis (Pera)", "Rutaceae", "Citrus"), p("Citrus sinensis (Okinawa)", "Rutaceae", "Citrus"))[0] == 0.95
    assert auto.estimar(p("Prunus persica", "Rosaceae", "Prunus"), p("Cucurbita maxima", "Cucurbitaceae", "Cucurbita"))[0] == 0.05
    assert auto.estimar(p("A b", "não informado", "A"), p("C d", "F", "C")) is None
