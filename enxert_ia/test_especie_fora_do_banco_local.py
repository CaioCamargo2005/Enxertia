"""
Uma especie que NAO esta no banco local (taxonomy_fallback.json) deve ser
resolvida via GBIF e funcionar em /compatibilidade e /recomendacoes.
A GBIF e mockada -- o teste nao depende de rede.
"""

import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app, taxonomy_service

client = TestClient(app)

BLUEBERRY = {"family": "Ericaceae", "genus": "Vaccinium", "match_type": "EXACT", "confidence": 98}


def _gbif_so_para_blueberry(nome):
    return BLUEBERRY if nome == "Vaccinium corymbosum" else None


def test_taxonomia_de_especie_fora_do_banco_vem_da_gbif():
    with patch.object(taxonomy_service.gbif_client, "get_taxonomy", side_effect=_gbif_so_para_blueberry):
        r = client.get("/taxonomia/Vaccinium corymbosum")
    assert r.status_code == 200
    assert r.json()["source"] == "gbif"
    assert r.json()["family"] == "Ericaceae"


def test_compatibilidade_com_especie_fora_do_banco():
    with patch.object(taxonomy_service.gbif_client, "get_taxonomy", side_effect=_gbif_so_para_blueberry):
        r = client.get("/compatibilidade", params={
            "porta_enxerto": "Vaccinium corymbosum", "enxerto": "Citrus sinensis", "motor": "regras"})
    d = r.json()
    assert d["rootstock_taxonomy"]["source"] == "gbif"
    assert d["level"] == "improvavel"  # Ericaceae x Rutaceae


def test_recomendacoes_para_especie_fora_do_banco():
    with patch.object(taxonomy_service.gbif_client, "get_taxonomy", side_effect=_gbif_so_para_blueberry):
        r = client.get("/recomendacoes", params={"especie": "Vaccinium corymbosum", "limite": 3})
    assert r.status_code == 200
    assert r.json()["taxonomia"]["source"] == "gbif"
    assert len(r.json()["recomendacoes"]) == 3


def test_status_expoe_o_motivo_quando_gbif_falha():
    import requests
    with patch("app.clients.gbif.requests.get", side_effect=requests.exceptions.ConnectionError("dns")):
        d = client.get("/status").json()
    assert d["gbif_respondendo_agora"] is False
    assert "sem conexao" in d["gbif_erro"]
