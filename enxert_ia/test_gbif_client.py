"""
Testes do cliente GBIF (app/clients/gbif.py) com a chamada HTTP mockada --
nao depende de rede. As respostas mockadas abaixo sao copias literais do
que a API real devolveu quando testei manualmente antes de escrever o
cliente (ver docstring de app/clients/gbif.py).
"""

from unittest.mock import patch, Mock

from app.clients.gbif import GBIFClient


def _mock_response(json_data, status_code=200):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = Mock()
    return resp


def test_parse_exact_match():
    resposta_real = {
        "usageKey": 8149923, "scientificName": "Prunus persica (L.) Stokes",
        "canonicalName": "Prunus persica", "rank": "SPECIES", "status": "ACCEPTED",
        "confidence": 99, "matchType": "EXACT", "kingdom": "Plantae",
        "family": "Rosaceae", "genus": "Prunus",
    }
    with patch("app.clients.gbif.requests.get", return_value=_mock_response(resposta_real)):
        resultado = GBIFClient().get_taxonomy("Prunus persica")
    assert resultado["family"] == "Rosaceae"
    assert resultado["genus"] == "Prunus"
    assert resultado["match_type"] == "EXACT"


def test_parse_no_match_returns_none():
    resposta_real = {"confidence": 100, "matchType": "NONE", "synonym": False}
    with patch("app.clients.gbif.requests.get", return_value=_mock_response(resposta_real)):
        resultado = GBIFClient().get_taxonomy("Especie Inexistente Totalmente")
    assert resultado is None


def test_higherrank_match_is_rejected():
    # matchType HIGHERRANK = so achou o genero, nao a especie -- confianca
    # baixa demais pra alimentar o motor de compatibilidade.
    resposta = {"matchType": "HIGHERRANK", "family": "Rosaceae", "genus": "Prunus", "confidence": 50}
    with patch("app.clients.gbif.requests.get", return_value=_mock_response(resposta)):
        resultado = GBIFClient().get_taxonomy("Prunus coisa_inventada")
    assert resultado is None


def test_network_error_returns_none_not_exception():
    import requests
    with patch("app.clients.gbif.requests.get", side_effect=requests.RequestException("sem rede")):
        resultado = GBIFClient().get_taxonomy("Prunus persica")
    assert resultado is None


def test_diagnosticar_ok():
    resposta = {"matchType": "EXACT", "family": "Rutaceae", "genus": "Citrus", "confidence": 99}
    with patch("app.clients.gbif.requests.get", return_value=_mock_response(resposta)):
        assert GBIFClient().diagnosticar() == {"ok": True, "erro": None}


def test_diagnosticar_explica_o_motivo_da_falha():
    import requests
    casos = {
        "certificado SSL": requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED"),
        "proxy": requests.exceptions.ProxyError("proxy recusou"),
        "tempo esgotado": requests.exceptions.ConnectTimeout("lento"),
        "sem conexao": requests.exceptions.ConnectionError("dns"),
    }
    for trecho, excecao in casos.items():
        with patch("app.clients.gbif.requests.get", side_effect=excecao):
            r = GBIFClient().diagnosticar()
        assert r["ok"] is False
        assert trecho in r["erro"]
