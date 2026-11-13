"""Banco de combinacoes (app/db.py) + integracao com hybrid_score e a API."""

import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

from fastapi.testclient import TestClient

from app import db
from app.compatibility import hybrid_score
from app.main import app
from app.models import TaxonomyInfo

client = TestClient(app)


def _tax(nome, familia, genero):
    return TaxonomyInfo(scientific_name=nome, family=familia, genus=genero, source="fallback_local")


def test_seed_cadastra_so_as_excecoes_como_conhecimento_geral(banco_temporario):
    assert db.init_db(seed=True) == 15
    registros = db.listar()
    assert len(registros) == 15
    assert {r["tipo_evidencia"] for r in registros} == {"conhecimento_geral"}
    assert all(r["fonte"] is None for r in registros)  # seed nao finge ter citacao


def test_seed_nao_duplica_se_rodar_de_novo(banco_temporario):
    db.init_db(seed=True)
    assert db.init_db(seed=True) == 0
    assert db.contar() == 15


def test_busca_nos_dois_sentidos_e_ignora_maiusculas(banco_temporario):
    db.inserir("Solanum lycopersicum", "Solanum melongena", 0.8, "citada", fonte="Autor, 2020")
    direto = db.buscar_combinacao("solanum LYCOPERSICUM", "Solanum melongena")
    inverso = db.buscar_combinacao("Solanum melongena", "Solanum lycopersicum")
    assert direto["inverso"] is False
    assert inverso["inverso"] is True


def test_registro_direcional_nao_vale_no_sentido_inverso(banco_temporario):
    db.inserir("A a", "B b", 0.9, "conhecimento_geral", vale_nos_dois_sentidos=False)
    assert db.buscar_combinacao("A a", "B b") is not None
    assert db.buscar_combinacao("B b", "A a") is None


def test_validacoes(banco_temporario):
    import pytest
    with pytest.raises(db.RegistroInvalido):
        db.inserir("A a", "B b", 0.5, "citada")  # citada sem fonte
    with pytest.raises(db.RegistroInvalido):
        db.inserir("A a", "B b", 1.5, "conhecimento_geral")
    with pytest.raises(db.RegistroInvalido):
        db.inserir("A a", "B b", 0.5, "inventado")
    with pytest.raises(db.RegistroInvalido):
        db.inserir("", "B b", 0.5, "conhecimento_geral")
    db.inserir("A a", "B b", 0.5, "conhecimento_geral")
    with pytest.raises(db.RegistroDuplicado):
        db.inserir("a A", "b B", 0.5, "conhecimento_geral")  # mesma chave, outra caixa


def test_banco_tem_prioridade_sobre_estimativa_e_expoe_a_evidencia(banco_temporario):
    # Capsicum x Solanum: pela regra seria "mesma familia" = 0.40
    db.inserir("Capsicum annuum", "Solanum lycopersicum", 0.1, "citada", fonte="Manual X, 2019",
               observacoes="Incompatibilidade tardia.")
    porta = _tax("Capsicum annuum", "Solanaceae", "Capsicum")
    enxerto = _tax("Solanum lycopersicum", "Solanaceae", "Solanum")

    r = hybrid_score("Capsicum annuum", "Solanum lycopersicum", porta, enxerto, motor="auto")
    assert r.source == "banco"
    assert r.score == 0.1 and r.level == "improvavel"
    assert r.evidencia == "citada" and r.fonte == "Manual X, 2019"
    assert "Manual X, 2019" in r.justification

    # motor="regras" ignora o banco
    assert hybrid_score("Capsicum annuum", "Solanum lycopersicum", porta, enxerto, motor="regras").source == "regras"


def test_par_fora_do_banco_continua_estimado(banco_temporario):
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Citrus limon", "Rutaceae", "Citrus")
    assert hybrid_score("Citrus sinensis", "Citrus limon", porta, enxerto, motor="auto").source in ("ml", "regras")


def test_api_crud_e_consulta(banco_temporario):
    r = client.post("/banco/combinacoes", json={
        "porta_enxerto": "Solanum melongena", "enxerto": "Solanum lycopersicum",
        "compatibilidade": 0.85, "tipo_evidencia": "citada", "fonte": "Fulano et al., 2021"})
    assert r.status_code == 201
    novo_id = r.json()["id"]

    assert client.post("/banco/combinacoes", json={
        "porta_enxerto": "solanum melongena", "enxerto": "Solanum lycopersicum",
        "compatibilidade": 0.5, "tipo_evidencia": "conhecimento_geral"}).status_code == 409
    assert client.post("/banco/combinacoes", json={
        "porta_enxerto": "X y", "enxerto": "Z w", "compatibilidade": 0.5,
        "tipo_evidencia": "citada"}).status_code == 422

    lista = client.get("/banco/combinacoes", params={"q": "melongena"}).json()
    assert [x["id"] for x in lista] == [novo_id]

    c = client.get("/compatibilidade", params={
        "porta_enxerto": "Solanum melongena", "enxerto": "Solanum lycopersicum"}).json()
    assert c["source"] == "banco" and c["score"] == 0.85

    assert client.delete(f"/banco/combinacoes/{novo_id}").status_code == 200
    assert client.delete(f"/banco/combinacoes/{novo_id}").status_code == 404
