"""Plantas cadastradas pelo usuario (app/especies.py) e endpoints /especies."""
import os

os.environ["ENXERTIA_NO_AUTOOPEN"] = "1"

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import especies, main
from app.main import app
from app.taxonomy_service import TaxonomyService

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolado(banco_temporario, monkeypatch):
    # GBIF "fora do ar" nos testes: nada de rede
    monkeypatch.setattr(main._gbif_status_client, "get_taxonomy", lambda nome: None)


def _nova(**extra):
    corpo = {"nome_cientifico": "Annona cherimola", "nome_popular": "cherimólia",
             "familia": "Annonaceae", "genero": "Annona"}
    corpo.update(extra)
    return client.post("/especies", json=corpo)


def test_cadastra_e_aparece_nos_seletores():
    r = _nova()
    assert r.status_code == 201 and r.json()["origem"] == "usuario"
    lista = client.get("/especies").json()
    minha = [e for e in lista if e["scientific_name"] == "Annona cherimola"]
    assert minha and minha[0]["origem"] == "usuario"
    assert sum(e["origem"] == "base" for e in lista) == 77


def test_planta_do_usuario_e_resolvida_sem_internet():
    _nova()
    servico = TaxonomyService(gbif_client=Mock(get_taxonomy=Mock(return_value=None)),
                              reflora_client=Mock(get_taxonomy=Mock(return_value=None)))
    t = servico.resolve("annona CHERIMOLA")
    assert t.source == "usuario" and t.family == "Annonaceae"


def test_planta_do_usuario_entra_na_consulta():
    _nova()
    r = client.get("/compatibilidade", params={"porta_enxerto": "Annona squamosa", "enxerto": "Annona cherimola"}).json()
    assert r["level"] != "desconhecida" and r["scion_taxonomy"]["source"] == "usuario"


def test_normaliza_o_nome():
    r = _nova(nome_cientifico="  annona   CHERIMOLA  (Fino de Jete) ")
    assert r.json()["scientific_name"] == "Annona cherimola (Fino de Jete)"


@pytest.mark.parametrize("campos, trecho", [
    ({"nome_cientifico": "cherimolia"}, "Genero especie"),
    ({"genero": "Rollinia"}, "primeira palavra"),
    ({"familia": "Anonas"}, "-aceae"),
    ({"familia": "", "genero": ""}, "familia e o genero"),
])
def test_validacoes(campos, trecho):
    r = _nova(**campos)
    assert r.status_code == 422 and trecho in r.json()["detail"]


def test_familia_alternativa_aceita():
    assert _nova(nome_cientifico="Inga edulis", familia="Leguminosae", genero="Inga").status_code == 201


def test_nao_duplica_nem_repete_especie_do_projeto():
    assert _nova().status_code == 201
    assert _nova().status_code == 409
    r = _nova(nome_cientifico="Citrus sinensis", familia="Rutaceae", genero="Citrus")
    assert r.status_code == 409 and "lista do projeto" in r.json()["detail"]


def test_gbif_preenche_familia_e_genero(monkeypatch):
    monkeypatch.setattr(main._gbif_status_client, "get_taxonomy",
                        lambda nome: {"family": "Annonaceae", "genus": "Annona"})
    r = _nova(familia="", genero="")
    assert r.status_code == 201 and r.json()["preenchido_pela_gbif"] is True


def test_remove_so_planta_do_usuario():
    _nova()
    assert client.delete("/especies/Annona cherimola").status_code == 200
    assert client.delete("/especies/Citrus sinensis").status_code == 404
    assert all(e["scientific_name"] != "Annona cherimola" for e in client.get("/especies").json())


def test_fonte_local_e_plugavel():
    class FonteFixa:
        def listar(self):
            return [{"scientific_name": "Teste exemplo", "family": "Testaceae", "genus": "Teste", "origem": "csv"}]

        def buscar(self, nome):
            return self.listar()[0] if nome.lower() == "teste exemplo" else None

    servico = TaxonomyService(gbif_client=Mock(get_taxonomy=Mock(return_value=None)),
                              reflora_client=Mock(get_taxonomy=Mock(return_value=None)),
                              fontes_locais=[FonteFixa()])
    assert servico.resolve("Teste exemplo").family == "Testaceae"
    assert [e["scientific_name"] for e in servico.list_fallback_species()] == ["Teste exemplo"]
