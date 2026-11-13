"""
Testes do modulo ncbi_taxonomia e da opcao 7 do menu, com o NCBI SIMULADO
(nenhuma chamada de rede de verdade). Rodar: pytest -q

Os TaxIDs usados aqui sao inventados -- servem para testar a logica, nao para
afirmar nada sobre o NCBI real.
"""
import importlib
import json
import shutil
import socket
import sqlite3
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

AQUI = Path(__file__).parent

# "NCBI" falso: nome -> (taxid, rank, familia, genero)
MUNDO = {
    "Solanum lycopersicum": (4081, "species", "Solanaceae", "Solanum"),
    "Solanum paniculatum": (9999, "species", "Solanaceae", "Solanum"),
    "Citrus sinensis": (2711, "species", "Rutaceae", "Citrus"),
    "Prunus persica": (3760, "species", "Rosaceae", "Prunus"),
    "Citrullus lanatus": (3654, "species", "Cucurbitaceae", "Citrullus"),
    "Cucurbita maxima": (3661, "species", "Cucurbitaceae", "Cucurbita"),
}
POR_ID = {v[0]: (k,) + v[1:] for k, v in MUNDO.items()}
POR_ID[3649] = ("Carica papaya", "species", "Caricaceae", "Carica")


def _xml(taxid):
    nome, rank, fam, gen = POR_ID[taxid]
    return (f"<TaxaSet><Taxon><TaxId>{taxid}</TaxId><ScientificName>{nome}</ScientificName>"
            f"<Rank>{rank}</Rank><Lineage>cellular organisms; Eukaryota</Lineage><LineageEx>"
            f"<Taxon><TaxId>1</TaxId><ScientificName>Eukaryota</ScientificName><Rank>domain</Rank></Taxon>"
            f"<Taxon><TaxId>2</TaxId><ScientificName>{fam}</ScientificName><Rank>family</Rank></Taxon>"
            f"<Taxon><TaxId>3</TaxId><ScientificName>{gen}</ScientificName><Rank>genus</Rank></Taxon>"
            f"</LineageEx></Taxon></TaxaSet>").encode()


class NCBIFalso:
    def __init__(self, ids_extra=None):
        self.chamadas = []
        self.ids_extra = ids_extra or {}   # nome -> lista de ids (p/ ambiguidade)

    def __call__(self, url, timeout):
        self.chamadas.append(url)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "esearch" in url:
            nome = q["term"][0].split('"')[1]
            ids = self.ids_extra.get(nome) or ([MUNDO[nome][0]] if nome in MUNDO else [])
            return json.dumps({"esearchresult": {"count": str(len(ids)), "idlist": [str(i) for i in ids]}}).encode()
        return _xml(int(q["id"][0]))


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    script = sorted(AQUI.glob("interface_enxert_db*.py"))[0]       # aceita interface_enxert_db-v6.py etc.
    shutil.copy(script, tmp_path / "interface_enxert_db.py")
    # sem literatura_enxert_db.sql: estes testes usam so as 16 plantas iniciais
    for f in ("ncbi_taxonomia.py", "enxert_db.sql", "banco_enxert_db.py"):
        shutil.copy(AQUI / f, tmp_path / f)
    monkeypatch.syspath_prepend(str(tmp_path))
    for m in ("interface_enxert_db", "ncbi_taxonomia", "banco_enxert_db"):
        sys.modules.pop(m, None)
    ncbi = importlib.import_module("ncbi_taxonomia")
    app = importlib.import_module("interface_enxert_db")
    monkeypatch.setattr(ncbi.time, "sleep", lambda s: None)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    falso = NCBIFalso()
    monkeypatch.setattr(ncbi, "_abrir", falso)
    return app, ncbi, falso, tmp_path


def _taxids(tmp_path):
    return dict(sqlite3.connect(tmp_path / "enxert.db").execute("SELECT id_planta, ncbi_taxid FROM Plantas"))


def _responder(monkeypatch, resp):
    monkeypatch.setattr("builtins.input", lambda *_: resp)


def test_binomio():
    from ncbi_taxonomia import binomio
    assert binomio("Citrus sinensis (Pera D6)") == "Citrus sinensis"
    assert binomio("Solanum lycopersicum (15PEX00056)") == "Solanum lycopersicum"
    assert binomio("Solanum lycopersicum x S. habrochaites (Castelpro)") is None
    assert binomio("Citrus sunki x Poncirus trifoliata") is None
    assert binomio("Citrus") is None
    assert binomio("") is None and binomio(None) is None


def test_corrige_taxid_errado_do_tomate(ambiente, monkeypatch, capsys):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    c = sqlite3.connect(tmp / "enxert.db"); c.execute("UPDATE Plantas SET ncbi_taxid=3649 WHERE id_planta=1"); c.commit(); c.close()
    _responder(monkeypatch, "s")
    app.verificar_taxonomia_ncbi()
    out = capsys.readouterr().out
    assert "TaxID diverge" in out and "Carica papaya" not in out.split("NCBI 3649")[0]
    assert _taxids(tmp)[1] == 4081


def test_so_altera_ncbi_taxid_e_so_onde_diverge(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    antes = sqlite3.connect(tmp / "enxert.db").execute("SELECT * FROM Plantas").fetchall()
    _responder(monkeypatch, "s")
    app.verificar_taxonomia_ncbi()
    depois = sqlite3.connect(tmp / "enxert.db").execute("SELECT * FROM Plantas").fetchall()
    mudou = [(a, d) for a, d in zip(antes, depois) if a != d]
    # no mundo falso, so Solanum paniculatum (id 2: 4102 no banco, 9999 no "NCBI") diverge
    assert len(mudou) == 1 and mudou[0][0][0] == 2 and mudou[0][1][3] == 9999
    assert mudou[0][0][1:3] == mudou[0][1][1:3] and mudou[0][0][4:] == mudou[0][1][4:]


def test_recusar_nao_altera_nada(ambiente, monkeypatch, capsys):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    antes = _taxids(tmp)
    _responder(monkeypatch, "n")
    app.verificar_taxonomia_ncbi()
    assert _taxids(tmp) == antes
    assert "Nada foi alterado" in capsys.readouterr().out


def test_preenche_taxid_vazio(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    c = sqlite3.connect(tmp / "enxert.db"); c.execute("UPDATE Plantas SET ncbi_taxid=NULL WHERE id_planta=15"); c.commit(); c.close()
    _responder(monkeypatch, "s")
    app.verificar_taxonomia_ncbi()
    assert _taxids(tmp)[15] == 3654


def test_hibrido_e_nao_encontrado_nao_viram_correcao(ambiente, monkeypatch, capsys):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    _responder(monkeypatch, "n")
    app.verificar_taxonomia_ncbi()
    out = capsys.readouterr().out
    assert out.count("híbrido (não consultado)") == 2        # linhas 4 e 8 (nome com ' x ')
    # no mundo falso, estas 5 nao existem: Solanum aculeatissimum, Citrus sunki, C. limonia,
    # Prunus marianna, P. cerasifera
    assert out.count("não encontrado no NCBI") == 5


def test_rede_fora_aborta_na_primeira_chamada_sem_tocar_no_banco(ambiente, monkeypatch, capsys):
    app, ncbi, falso, tmp = ambiente
    app.get_connection().close()
    antes = _taxids(tmp)
    chamadas = []

    def sem_rede(url, timeout):
        chamadas.append(url)
        raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))
    monkeypatch.setattr(ncbi, "_abrir", sem_rede)
    _responder(monkeypatch, "s")
    app.verificar_taxonomia_ncbi()
    out = capsys.readouterr().out
    assert "Não consegui falar com o NCBI" in out and "resolver o endereço" in out
    assert len(chamadas) == 1                      # nao repete o mesmo erro 16 vezes
    assert _taxids(tmp) == antes


def test_429_tenta_de_novo_e_depois_funciona(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    n = {"i": 0}

    def instavel(url, timeout):
        n["i"] += 1
        if n["i"] == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        return falso(url, timeout)
    monkeypatch.setattr(ncbi, "_abrir", instavel)
    assert ncbi.buscar_taxids("Solanum lycopersicum") == [4081]
    assert n["i"] == 2


def test_429_persistente_vira_erro_claro(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente

    def sempre_429(url, timeout):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(ncbi, "_abrir", sempre_429)
    with pytest.raises(ncbi.NCBIErro, match="NCBI_API_KEY"):
        ncbi.buscar_taxids("Solanum lycopersicum")


def test_resposta_fora_do_formato(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    monkeypatch.setattr(ncbi, "_abrir", lambda u, t: b"<html>erro</html>")
    with pytest.raises(ncbi.NCBIErro, match="inesperada"):
        ncbi.buscar_taxids("Solanum lycopersicum")
    monkeypatch.setattr(ncbi, "_abrir", lambda u, t: b"isto nao e xml")
    with pytest.raises(ncbi.NCBIErro, match="XML"):
        ncbi.detalhes(4081)


def test_ambiguo_nao_e_corrigido(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    falso.ids_extra = {"Solanum lycopersicum": [4081, 3649]}
    r = ncbi.verificar_planta(1, "x", "Solanum lycopersicum", 3649, "Solanaceae", "Solanum")
    assert r["status"] == "ambiguo"


def test_avisa_familia_divergente(ambiente):
    app, ncbi, falso, tmp = ambiente
    r = ncbi.verificar_planta(1, "x", "Solanum lycopersicum", 4081, "Rosaceae", "Solanum")
    assert r["status"] == "ok" and any("família" in a for a in r["avisos"])


def test_chave_e_email_vao_na_url(ambiente, monkeypatch):
    app, ncbi, falso, tmp = ambiente
    monkeypatch.setenv("NCBI_API_KEY", "abc123")
    monkeypatch.setenv("NCBI_EMAIL", "a@b.c")
    ncbi.buscar_taxids("Solanum lycopersicum")
    assert "api_key=abc123" in falso.chamadas[-1] and "email=a%40b.c" in falso.chamadas[-1]


def test_sem_o_modulo_o_menu_nao_quebra(ambiente, monkeypatch, capsys):
    app, ncbi, falso, tmp = ambiente
    (tmp / "ncbi_taxonomia.py").unlink()
    monkeypatch.setitem(sys.modules, "ncbi_taxonomia", None)   # forca ImportError
    app.verificar_taxonomia_ncbi()
    assert "ncbi_taxonomia.py" in capsys.readouterr().out
