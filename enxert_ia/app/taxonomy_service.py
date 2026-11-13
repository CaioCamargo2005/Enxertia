from pathlib import Path
from typing import List, Optional

from app.clients.gbif import GBIFClient
from app.clients.reflora import RefloraClient
from app.especies import FonteArquivo, FonteUsuario
from app.models import TaxonomyInfo

FALLBACK_PATH = Path(__file__).parent / "taxonomy_fallback.json"


class TaxonomyService:
    """
    Resolve familia/genero de uma especie, em ordem de prioridade:

    1. GBIF (fonte PRIMARIA) -- API publica, sem chave, com schema
       confirmado e funcionando (ver app/clients/gbif.py). E a API externa
       de verdade que o nucleo do sistema (ranking/compatibilidade) usa.
    2. Reflora/JBRJ -- tentado como segunda opcao, best-effort: o schema do
       endpoint nunca foi confirmado (ver app/clients/reflora.py), entao na
       pratica normalmente nao retorna nada, mas o codigo tenta mesmo assim
       caso o TODO daquele arquivo seja resolvido no futuro.
    3. Fontes locais (app/especies.py), na ordem da lista `fontes_locais`:
       por padrao a lista que vem com o projeto (source "fallback_local") e
       as plantas cadastradas pelo usuario (source "usuario"). Usadas quando
       nem GBIF nem Reflora respondem (sem internet, nome que a GBIF nao
       reconhece) e para alimentar os seletores da interface.
    """

    def __init__(self, gbif_client: Optional[GBIFClient] = None, reflora_client: Optional[RefloraClient] = None,
                 fontes_locais: Optional[list] = None):
        self.gbif_client = gbif_client or GBIFClient()
        self.reflora_client = reflora_client or RefloraClient()
        self.fontes_locais = fontes_locais if fontes_locais is not None else [FonteArquivo(FALLBACK_PATH), FonteUsuario()]

    def resolve(self, scientific_name: str) -> Optional[TaxonomyInfo]:
        name = scientific_name.strip()

        gbif_data = self.gbif_client.get_taxonomy(name)
        if gbif_data:
            return TaxonomyInfo(
                scientific_name=name,
                family=gbif_data.get("family"),
                genus=gbif_data.get("genus"),
                source="gbif",
            )

        reflora_data = self.reflora_client.get_taxonomy(name)
        if reflora_data:
            return TaxonomyInfo(
                scientific_name=name,
                family=reflora_data.get("family"),
                genus=reflora_data.get("genus"),
                source="reflora",
            )

        for fonte in self.fontes_locais:
            entrada = fonte.buscar(name)
            if entrada:
                return TaxonomyInfo(
                    scientific_name=entrada["scientific_name"],
                    common_name=entrada.get("common_name"),
                    family=entrada.get("family"),
                    genus=entrada.get("genus"),
                    source="usuario" if entrada.get("origem") == "usuario" else "fallback_local",
                )

        return None

    def list_fallback_species(self) -> List[dict]:
        """Especies de todas as fontes locais (sem repetir nomes), pra listagem no CLI/web.
        Cada item traz `origem`: "base" (vem com o projeto) ou "usuario"."""
        vistas, todas = set(), []
        for fonte in self.fontes_locais:
            for e in fonte.listar():
                chave = e["scientific_name"].lower()
                if chave not in vistas:
                    vistas.add(chave)
                    todas.append(e)
        return todas
