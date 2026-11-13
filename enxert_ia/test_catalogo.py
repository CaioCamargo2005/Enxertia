"""Pagina Catalogo: leitura do banco Enxert.DB (pasta ../enxert_db)."""
import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

import pytest
from fastapi.testclient import TestClient

from app import catalogo
from app.main import app

client = TestClient(app)
pytestmark = pytest.mark.skipif(not (catalogo.PASTA_ENXERT_DB / "banco_enxert_db.py").exists(),
                                reason="pasta enxert_db nao esta ao lado de enxert_ia")


@pytest.fixture(autouse=True)
def banco_temp(tmp_path, monkeypatch):
    monkeypatch.setenv("ENXERT_DB_FILE", str(tmp_path / "enxert.db"))


def test_resumo():
    r = client.get("/catalogo/resumo").json()
    assert r["da_literatura"] == 45 and r["da_equipe"] == 10 and r["conferidas"] == 0 and r["fontes"] == 5


def test_filtros():
    todos = client.get("/catalogo/combinacoes").json()
    equipe = client.get("/catalogo/combinacoes", params={"origem": "equipe"}).json()
    sem = client.get("/catalogo/combinacoes", params={"status": "sem_status"}).json()
    swingle = client.get("/catalogo/combinacoes", params={"q": "Swingle"}).json()
    assert len(todos) == 55 and len(equipe) == 10
    assert sem and all(c["status"] is None for c in sem)
    assert swingle and all("Swingle" in c["porta_enxerto"] for c in swingle)
    assert all(c["fonte_url"].startswith("https://") for c in todos if c["id_fonte"])


def test_pasta_ausente_responde_503(monkeypatch, tmp_path):
    monkeypatch.setattr(catalogo, "PASTA_ENXERT_DB", tmp_path / "nao_existe")
    assert client.get("/catalogo/resumo").status_code == 503
