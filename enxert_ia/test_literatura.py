"""Evidencias da literatura (app/literatura.py): importacao, promocao ao banco,
correspondencia por especie/genero e integracao com /compatibilidade."""

import csv
import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

import pytest
from fastapi.testclient import TestClient

from app import db, literatura
from app.main import app
from app.models import TaxonomyInfo

client = TestClient(app)


def _tax(nome, familia, genero):
    return TaxonomyInfo(scientific_name=nome, family=familia, genus=genero, source="fallback_local")


def _linhas():
    with open(literatura.CSV_REGISTROS, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _csv_com_conferido(tmp_path, ids):
    """Copia o CSV marcando `conferido = sim` nos ids pedidos."""
    linhas = _linhas()
    for l in linhas:
        if l["id_registro"] in ids:
            l["conferido"] = "sim"
    destino = tmp_path / "reg.csv"
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    return destino


# ---------- integridade dos dados ----------

def test_todo_registro_tem_fonte_com_link_https():
    fontes = {f["fonte_id"]: f for f in csv.DictReader(open(literatura.CSV_FONTES, encoding="utf-8-sig"))}
    for l in _linhas():
        assert l["fonte_id"] in fontes, l["id_registro"]
        assert fontes[l["fonte_id"]]["url"].startswith("https://")
        assert l["trecho"].strip(), f"{l['id_registro']} sem trecho"


def test_nenhum_registro_vem_conferido_de_fabrica():
    # Quem confere e uma pessoa, abrindo o PDF. O CSV entregue nao finge isso.
    assert all((l["conferido"] or "").strip() == "" for l in _linhas())


def test_indice_so_em_registros_de_nivel_especie():
    for l in _linhas():
        if l["indice_proposto"]:
            assert " " in l["copa_taxon"] and " " in l["porta_taxon"] and ";" not in l["porta_taxon"], l["id_registro"]
            assert float(l["indice_proposto"]) in (0.1, 0.9)


# ---------- importacao ----------

def test_importacao_e_idempotente(banco_temporario):
    primeira = literatura.importar()
    segunda = literatura.importar()
    assert primeira["novos"] == literatura.contar() == len(_linhas())
    assert segunda["novos"] == 0 and segunda["promovidos_ao_banco"] == 0
    assert db.contar() == primeira["promovidos_ao_banco"]


def test_promovidos_entram_como_relato_nao_verificado_e_direcionais(banco_temporario):
    literatura.importar()
    registros = db.listar()
    assert registros, "esperava ao menos um par de nivel especie promovido"
    for r in registros:
        assert r["tipo_evidencia"] == "relato_nao_verificado"
        assert r["fonte"] and "http" in r["fonte"]
        assert r["vale_nos_dois_sentidos"] == 0  # copa e porta-enxerto nao sao intercambiaveis
        assert "[lit:" in r["observacoes"]


def test_conferir_promove_para_citada_sem_duplicar(banco_temporario, tmp_path):
    literatura.importar()
    antes = db.contar()
    conferido = _csv_com_conferido(tmp_path, {"R47"})
    resumo = literatura.importar(registros=conferido)
    assert db.contar() == antes and resumo["atualizados_no_banco"] >= 1
    luffa = db.buscar_combinacao("Luffa cylindrica", "Citrullus lanatus")
    assert luffa["tipo_evidencia"] == "citada" and "conferido" in luffa["observacoes"].lower()
    outro = db.buscar_combinacao("Benincasa hispida", "Citrullus lanatus")
    assert outro["tipo_evidencia"] == "relato_nao_verificado"


def test_registro_apagado_do_banco_nao_volta_sozinho(banco_temporario):
    literatura.importar()
    r = db.buscar_combinacao("Luffa cylindrica", "Citrullus lanatus")
    db.remover(r["id"])
    literatura.importar()
    assert db.buscar_combinacao("Luffa cylindrica", "Citrullus lanatus") is None


def test_nao_sobrescreve_par_cadastrado_a_mao(banco_temporario):
    db.inserir("Luffa cylindrica", "Citrullus lanatus", 0.3, "conhecimento_geral")
    resumo = literatura.importar()
    assert resumo["pares_ja_existentes"] == 1
    assert db.buscar_combinacao("Luffa cylindrica", "Citrullus lanatus")["compatibilidade"] == 0.3


def test_fonte_desconhecida_e_erro_claro(banco_temporario, tmp_path):
    ruim = tmp_path / "fontes.csv"
    ruim.write_text("fonte_id,referencia,url\nZZ,x,https://x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fonte"):
        literatura.importar(fontes=ruim)


# ---------- correspondencia ----------

def test_correspondencia_por_especie_vem_antes_da_de_genero(banco_temporario):
    literatura.importar()
    r = literatura.relacionadas(_tax("Cucurbita moschata", "Cucurbitaceae", "Cucurbita"),
                                _tax("Citrullus lanatus", "Cucurbitaceae", "Citrullus"))
    assert r["total"] >= 2
    assert r["registros"][0]["correspondencia"] == "especie"
    assert r["registros"][0]["id_registro"] == "R43"


def test_orientacao_importa(banco_temporario):
    literatura.importar()
    # melancia como PORTA-enxerto nao casa com registros de melancia como copa
    r = literatura.relacionadas(_tax("Citrullus lanatus", "Cucurbitaceae", "Citrullus"),
                                _tax("Cucurbita moschata", "Cucurbitaceae", "Cucurbita"))
    assert r["total"] == 0


def test_registros_sem_taxon_nunca_casam(banco_temporario):
    literatura.importar()
    r = literatura.relacionadas(_tax("Citrus sinensis", "Rutaceae", "Citrus"),
                                _tax("Citrus sinensis", "Rutaceae", "Citrus"))
    assert all(x["porta_taxon"] for x in r["registros"])


def test_limite_de_relacionadas_mas_total_completo(banco_temporario):
    literatura.importar()
    r = literatura.relacionadas(_tax("Poncirus trifoliata", "Rutaceae", "Poncirus"),
                                _tax("Citrus sinensis", "Rutaceae", "Citrus"))
    assert len(r["registros"]) <= literatura.MAX_RELACIONADAS < r["total"]


def test_taxonomia_ausente_nao_quebra():
    assert literatura.relacionadas(None, _tax("A b", "F", "A")) == {"total": 0, "registros": []}


# ---------- API ----------

def test_compatibilidade_traz_literatura_sem_mudar_o_score(banco_temporario):
    antes = client.get("/compatibilidade", params={"porta_enxerto": "Cucurbita moschata",
                                                  "enxerto": "Citrullus lanatus"}).json()
    literatura.importar()
    depois = client.get("/compatibilidade", params={"porta_enxerto": "Cucurbita moschata",
                                                   "enxerto": "Citrullus lanatus"}).json()
    assert antes["literatura_total"] == 0
    assert depois["literatura_total"] >= 1 and depois["literatura"][0]["fonte_url"].startswith("https://")
    assert (antes["score"], antes["source"]) == (depois["score"], depois["source"])


def test_endpoint_literatura_filtra(banco_temporario):
    literatura.importar()
    todos = client.get("/literatura").json()
    citros = client.get("/literatura", params={"cultura": "Citros"}).json()
    swingle = client.get("/literatura", params={"q": "Swingle"}).json()
    assert len(todos) == len(_linhas()) and 0 < len(citros) < len(todos)
    assert swingle and all("Swingle" in r["porta_enxerto"] for r in swingle)
    assert all(r["conferido"] == 0 for r in todos)
