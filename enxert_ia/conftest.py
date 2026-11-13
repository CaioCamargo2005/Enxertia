"""
Isola os testes do banco real (data/enxertia.db): todo o suite roda contra
um banco temporario VAZIO (o seed so acontece no lifespan do servidor, que
o TestClient sem `with` nao executa). Testes do banco usam o fixture
`banco_temporario` pra ter um banco proprio.
"""
import os
import tempfile

os.environ["ENXERTIA_DB"] = os.path.join(tempfile.mkdtemp(), "suite.db")
os.environ.setdefault("ENXERT_DB_FILE", os.path.join(tempfile.mkdtemp(), "enxert_suite.db"))

import pytest


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("ENXERTIA_DB", str(tmp_path / "teste.db"))
    return tmp_path / "teste.db"
