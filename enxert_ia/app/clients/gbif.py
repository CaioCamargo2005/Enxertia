"""
Cliente para a GBIF Species API (https://www.gbif.org/developer/species) --
a maior base de dados taxonomicos do mundo (Global Biodiversity Information
Facility), publica, sem necessidade de chave de API.

Diferente do Reflora (app/clients/reflora.py), cujo endpoint exato nunca foi
confirmado, este endpoint foi testado e confirmado manualmente antes de
escrever este cliente:

  GET https://api.gbif.org/v1/species/match?name=Prunus%20persica&kingdom=Plantae
  -> {"usageKey": 8149923, "scientificName": "Prunus persica (L.) Stokes",
      "canonicalName": "Prunus persica", "rank": "SPECIES", "status": "ACCEPTED",
      "confidence": 99, "matchType": "EXACT", "kingdom": "Plantae",
      "family": "Rosaceae", "genus": "Prunus", ...}

Para nomes sem correspondencia, a API responde so com
{"confidence": ..., "matchType": "NONE", "synonym": false} -- sem campos de
familia/genero, o que e tratado abaixo como "nao encontrado".

E usado como fonte PRIMARIA de taxonomia (ver app/taxonomy_service.py),
porque e a unica das integracoes externas deste projeto com o schema
confirmado e funcionando de ponta a ponta -- o motivo pelo qual o nucleo do
sistema (ranking/compatibilidade) agora de fato depende de uma API externa
real, nao so do banco local.
"""

import requests
from typing import Optional

GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"

# matchType "NONE" = sem correspondencia. "EXACT"/"FUZZY"/"HIGHERRANK" tem
# graus diferentes de confianca -- so aceitamos EXACT e FUZZY como resolucao
# valida; HIGHERRANK (ex: so achou o genero, nao a especie) nao e confiavel
# o bastante pra alimentar o motor de compatibilidade.
MATCH_TYPES_ACEITOS = {"EXACT", "FUZZY"}


class GBIFError(RuntimeError):
    pass


class GBIFClient:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def get_taxonomy(self, scientific_name: str) -> Optional[dict]:
        """Retorna {scientific_name, family, genus} ou None se nao encontrar
        correspondencia confiavel, ou se a API estiver fora do ar."""
        try:
            resp = requests.get(
                GBIF_MATCH_URL,
                params={"name": scientific_name, "kingdom": "Plantae"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return self._parse_response(resp.json(), scientific_name)
        except (requests.RequestException, ValueError):
            return None

    def diagnosticar(self, scientific_name: str = "Citrus sinensis") -> dict:
        """
        Faz a mesma chamada de get_taxonomy(), mas em vez de engolir o erro,
        devolve o motivo. Usado pelo /status e pelo hub pra mostrar POR QUE a
        GBIF nao esta respondendo (sem internet, proxy, certificado SSL,
        timeout, resposta inesperada...) -- get_taxonomy() sozinho so devolve
        None e nao deixa ver a causa.
        Retorna {"ok": bool, "erro": str | None}.
        """
        try:
            resp = requests.get(
                GBIF_MATCH_URL,
                params={"name": scientific_name, "kingdom": "Plantae"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            if self._parse_response(resp.json(), scientific_name) is None:
                return {"ok": False, "erro": "a GBIF respondeu, mas sem correspondencia utilizavel para a especie de teste"}
            return {"ok": True, "erro": None}
        except requests.exceptions.SSLError as exc:
            return {"ok": False, "erro": f"erro de certificado SSL (antivirus/proxy interceptando HTTPS?): {exc}"}
        except requests.exceptions.ProxyError as exc:
            return {"ok": False, "erro": f"erro de proxy: {exc}"}
        except requests.exceptions.ConnectTimeout:
            return {"ok": False, "erro": f"tempo esgotado ({self.timeout}s) ao conectar na GBIF -- internet lenta ou bloqueada"}
        except requests.exceptions.ConnectionError as exc:
            return {"ok": False, "erro": f"sem conexao com api.gbif.org (internet/firewall/DNS): {exc}"}
        except requests.exceptions.HTTPError as exc:
            return {"ok": False, "erro": f"a GBIF respondeu com erro HTTP: {exc}"}
        except (requests.RequestException, ValueError) as exc:
            return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    def _parse_response(data: dict, scientific_name: str) -> Optional[dict]:
        if not data or data.get("matchType") not in MATCH_TYPES_ACEITOS:
            return None
        family = data.get("family")
        genus = data.get("genus")
        if not family or not genus:
            return None
        return {
            "scientific_name": scientific_name,
            "family": family,
            "genus": genus,
            "match_type": data.get("matchType"),
            "confidence": data.get("confidence"),
            "gbif_status": data.get("status"),
        }
