"""
Cliente para a API v2 do Reflora / Flora e Funga do Brasil (JBRJ).

ATUALIZACAO - por que isso provavelmente nunca retorna nada:
Pesquisei mais a fundo (ver README.md, secao "Resolucao de taxonomia") e,
pelo que encontrei, o JBRJ nao parece expor um endpoint REST de busca por
taxon por nome como este codigo assume. O jeito oficial de acessar os dados
da Flora e Funga do Brasil e via um arquivo Darwin Core Archive publicado em
lote no IPT (https://ipt.jbrj.gov.br/jbrj/resource?r=lista_especies_flora_brasil),
nao uma API de consulta individual -- confirmei isso olhando como o pacote R
floraR (DBOSlab/floraR, feito especificamente pra acessar esses dados)
funciona: ele baixa o arquivo inteiro, nao faz uma chamada por especie.

Isso explica por que o schema REST abaixo nunca foi confirmado: pode nao
existir nesse formato. Mantenho este cliente mesmo assim, como segunda
tentativa best-effort depois da GBIF (app/clients/gbif.py) -- se o JBRJ
abrir um endpoint assim no futuro, ou se alguem confirmar um path real,
basta ajustar ENDPOINT_PATH e _parse_response() abaixo.

Importante: isso NAO significa que o projeto ficou sem dados do Reflora/
REFLORA. A GBIF (fonte primaria de taxonomia do projeto) agrega dados de
varias fontes nacionais, e o registro que ela devolveu para especies deste
projeto (confirmado manualmente para Prunus persica) cita o "Brazil Flora
Group / REFLORA Program" entre as fontes do dataset de origem. Ou seja: via
GBIF, o sistema acaba se beneficiando de dados que passam pelo proprio
programa REFLORA, so que agregados, nao por uma chamada direta a
servicos.jbrj.gov.br.
"""

import requests
from typing import Optional

REFLORA_BASE_URL = "https://servicos.jbrj.gov.br/v2/flora"
ENDPOINT_PATH = "/taxon"  # TODO: confirmar no Swagger


class RefloraClient:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def get_taxonomy(self, scientific_name: str) -> Optional[dict]:
        """Retorna {family, genus, scientific_name} ou None se nao encontrar/API fora do ar."""
        url = f"{REFLORA_BASE_URL}{ENDPOINT_PATH}"
        try:
            resp = requests.get(url, params={"nome": scientific_name}, timeout=self.timeout)
            resp.raise_for_status()
            return self._parse_response(resp.json(), scientific_name)
        except (requests.RequestException, ValueError):
            return None

    @staticmethod
    def _parse_response(data: dict, scientific_name: str) -> Optional[dict]:
        # TODO: adaptar as chaves abaixo ao schema real do Reflora.
        if not data:
            return None
        item = data[0] if isinstance(data, list) and data else data
        family = item.get("family") or item.get("familia")
        genus = item.get("genus") or item.get("genero")
        if not family and not genus:
            return None
        return {"scientific_name": scientific_name, "family": family, "genus": genus}
