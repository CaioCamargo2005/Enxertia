import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ranking_order_same_genus_beats_same_family():
    resp = client.get("/recomendacoes", params={"especie": "Citrus sinensis", "limite": 50})
    assert resp.status_code == 200
    data = resp.json()
    scores = [r["score"] for r in data["recomendacoes"]]
    assert scores == sorted(scores, reverse=True)


def test_top1_is_close_relative():
    resp = client.get("/recomendacoes", params={"especie": "Citrus sinensis", "limite": 50})
    data = resp.json()
    top1 = data["recomendacoes"][0]
    outra = top1["scion"] if top1["rootstock"] == "Citrus sinensis" else top1["rootstock"]
    assert "Citrus" in outra or "Poncirus" in outra or "Fortunella" in outra


def test_specific_candidates_mode():
    resp = client.get("/recomendacoes", params={
        "especie": "Citrus sinensis",
        "candidatos": "Citrus limon,Coffea arabica",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recomendacoes"]) == 2
    assert not data["candidatas_nao_encontradas"]


def test_target_not_found_404():
    resp = client.get("/recomendacoes", params={"especie": "Especie que nao existe no banco"})
    assert resp.status_code == 404


def test_candidate_not_found_is_listed_separately():
    resp = client.get("/recomendacoes", params={
        "especie": "Citrus sinensis",
        "candidatos": "Citrus limon,Especie Inexistente",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recomendacoes"]) == 1
    assert "Especie Inexistente" in data["candidatas_nao_encontradas"]
