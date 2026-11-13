"""
Cliente minimo do NCBI Taxonomy (o mesmo cadastro de especies que o GenBank usa
para os campos 'organism' e 'taxid' das sequencias). Usa so a biblioteca padrao.

API: NCBI E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/)
  - esearch.fcgi?db=taxonomy&term="Nome cientifico"[Scientific Name]&retmode=json
  - efetch.fcgi?db=taxonomy&id=<taxid>&retmode=xml

Limites do NCBI: 3 requisicoes/segundo sem chave, 10/s com chave. Opcional, via
variaveis de ambiente:
  NCBI_API_KEY  (gratis, em https://account.ncbi.nlm.nih.gov/settings/)
  NCBI_EMAIL    (o NCBI pede um contato nas requisicoes)

O que isto faz e o que NAO faz: confirma identidade taxonomica (TaxID, familia,
genero) de uma especie. NAO informa se duas plantas sao compativeis na enxertia
-- o GenBank nao tem esse dado.

Aviso: o formato das respostas foi implementado a partir da documentacao do
NCBI e testado com respostas simuladas; precisa ser conferido uma vez com
internet de verdade (o ambiente onde isto foi escrito nao alcanca o NCBI).
"""

import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ultima_chamada = 0.0


class NCBIErro(Exception):
    """Falha ao falar com o NCBI (rede, HTTP, resposta fora do formato)."""


# ---------------------------------------------------------------------------
# Baixo nivel
# ---------------------------------------------------------------------------

def _abrir(url, timeout):
    """Unico ponto que toca a rede (os testes substituem esta funcao)."""
    req = urllib.request.Request(url, headers={"User-Agent": "enxert-db/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _intervalo():
    return 0.12 if os.getenv("NCBI_API_KEY") else 0.35


def _motivo_rede(exc):
    razao = getattr(exc, "reason", exc)
    if isinstance(razao, ssl.SSLError) or "CERTIFICATE" in str(razao).upper():
        return ("falha de certificado SSL (antivírus/proxy interceptando HTTPS?): " + str(razao))
    if isinstance(razao, (socket.timeout, TimeoutError)):
        return "tempo esgotado ao conectar (internet lenta ou bloqueada?)"
    if isinstance(razao, socket.gaierror):
        return "não consegui resolver o endereço eutils.ncbi.nlm.nih.gov (sem internet/DNS?)"
    return f"erro de conexão: {razao}"


def _chamar(endpoint, params, timeout=15, tentativas=3):
    global _ultima_chamada
    params = dict(params)
    if os.getenv("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    if os.getenv("NCBI_EMAIL"):
        params["email"] = os.environ["NCBI_EMAIL"]
    params["tool"] = "enxert-db"
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}"

    for tentativa in range(1, tentativas + 1):
        espera = _intervalo() - (time.monotonic() - _ultima_chamada)
        if espera > 0:
            time.sleep(espera)
        _ultima_chamada = time.monotonic()
        try:
            return _abrir(url, timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentativa < tentativas:
                time.sleep(1.5 * tentativa)  # NCBI limitou/ficou instavel: espera e tenta de novo
                continue
            raise NCBIErro(f"HTTP {e.code} do NCBI"
                           + (" (limite de requisições excedido; use NCBI_API_KEY)" if e.code == 429 else ""))
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError, ConnectionError) as e:
            raise NCBIErro(_motivo_rede(e))


# ---------------------------------------------------------------------------
# Taxonomia
# ---------------------------------------------------------------------------

def binomio(nome_cientifico):
    """'Citrus sinensis (Pera D6)' -> 'Citrus sinensis'.
    Hibridos ('A x B') e nomes sem epiteto devolvem None: nao ha como consultar
    por nome sem risco de casar com a especie errada."""
    n = re.sub(r"\(.*?\)", "", nome_cientifico or "").strip()
    if re.search(r"\s[x×]\s", n, re.IGNORECASE):
        return None
    partes = n.split()
    if len(partes) < 2:
        return None
    return f"{partes[0]} {partes[1]}"


def buscar_taxids(nome):
    """IDs do NCBI Taxonomy cujo nome cientifico e exatamente `nome`."""
    dados = _chamar("esearch.fcgi", {
        "db": "taxonomy", "term": f'"{nome}"[Scientific Name]', "retmode": "json", "retmax": 5,
    })
    try:
        return [int(i) for i in json.loads(dados)["esearchresult"]["idlist"]]
    except (ValueError, KeyError, TypeError):
        raise NCBIErro("resposta inesperada do esearch (formato mudou ou erro do servidor)")


def detalhes(taxid):
    """Nome, rank, familia e genero de um TaxID. None se o NCBI nao devolver o taxon."""
    xml = _chamar("efetch.fcgi", {"db": "taxonomy", "id": str(taxid), "retmode": "xml"})
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        raise NCBIErro("resposta inesperada do efetch (XML inválido)")
    taxon = raiz.find("Taxon")
    if taxon is None:
        return None
    familia = genero = None
    for t in taxon.findall("./LineageEx/Taxon"):
        rank = (t.findtext("Rank") or "").lower()
        if rank == "family":
            familia = t.findtext("ScientificName")
        elif rank == "genus":
            genero = t.findtext("ScientificName")
    return {
        "taxid": int(taxon.findtext("TaxId")),
        "nome": taxon.findtext("ScientificName"),
        "rank": taxon.findtext("Rank"),
        "familia": familia,
        "genero": genero,
    }


# ---------------------------------------------------------------------------
# Verificacao do catalogo
# ---------------------------------------------------------------------------

def verificar_planta(id_planta, nome_comum, nome_cientifico, taxid_db, familia_db, genero_db):
    """Confere uma planta do catalogo contra o NCBI. status:
       ok | sem_taxid | diverge | nao_encontrado | ambiguo | hibrido"""
    r = {"id_planta": id_planta, "nome_comum": nome_comum, "nome_cientifico": nome_cientifico,
         "taxid_db": taxid_db, "taxid_ncbi": None, "nome_ncbi": None, "rank": None,
         "familia_ncbi": None, "genero_ncbi": None, "avisos": []}
    nome = binomio(nome_cientifico)
    if nome is None:
        r["status"] = "hibrido"
        return r

    ids = buscar_taxids(nome)
    if not ids:
        r["status"] = "nao_encontrado"
        return r
    if len(ids) > 1:
        r["status"] = "ambiguo"
        r["avisos"].append(f"NCBI devolveu {len(ids)} táxons: {ids}")
        return r

    d = detalhes(ids[0])
    if d is None:
        r["status"] = "nao_encontrado"
        return r
    r.update(taxid_ncbi=d["taxid"], nome_ncbi=d["nome"], rank=d["rank"],
             familia_ncbi=d["familia"], genero_ncbi=d["genero"])

    if familia_db and d["familia"] and familia_db != d["familia"]:
        r["avisos"].append(f"família no banco '{familia_db}' ≠ NCBI '{d['familia']}'")
    if genero_db and d["genero"] and genero_db != d["genero"]:
        r["avisos"].append(f"gênero no banco '{genero_db}' ≠ NCBI '{d['genero']}'")

    if taxid_db is None:
        r["status"] = "sem_taxid"
    elif taxid_db == d["taxid"]:
        r["status"] = "ok"
    else:
        r["status"] = "diverge"
    return r


def verificar_plantas(linhas, progresso=None):
    """linhas: (id_planta, nome_comum, nome_cientifico, ncbi_taxid, familia, genero).
    Se o NCBI estiver inacessivel, levanta NCBIErro na primeira chamada (nao
    repete o mesmo erro para cada planta)."""
    resultados = []
    for i, linha in enumerate(linhas, 1):
        if progresso:
            progresso(i, len(linhas), linha[2])
        resultados.append(verificar_planta(*linha))
    return resultados
