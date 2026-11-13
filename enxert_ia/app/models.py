from pydantic import BaseModel
from typing import List, Optional


class TaxonomyInfo(BaseModel):
    scientific_name: str
    common_name: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    source: str  # "gbif", "reflora", "fallback_local" ou "usuario"


class CompatibilityResult(BaseModel):
    rootstock: str
    scion: str
    score: float
    level: str
    justification: str
    rootstock_taxonomy: Optional[TaxonomyInfo] = None
    scion_taxonomy: Optional[TaxonomyInfo] = None
    source: str = "regras"  # "banco", "ml" ou "regras" -- de onde veio o score
    evidencia: Optional[str] = None  # so quando source == "banco": tipo de evidencia do registro
    fonte: Optional[str] = None      # so quando source == "banco": citacao, se houver
    # Registros da literatura que tocam o par (contexto; nao entram no score).
    literatura: List[dict] = []
    literatura_total: int = 0


class SpeciesCandidate(BaseModel):
    scientific_name: str
    confidence: float


class NovaCombinacao(BaseModel):
    porta_enxerto: str
    enxerto: str
    compatibilidade: float  # 0 a 1
    tipo_evidencia: str     # "citada", "conhecimento_geral" ou "relato_nao_verificado"
    fonte: Optional[str] = None
    observacoes: Optional[str] = None
    vale_nos_dois_sentidos: bool = True


class NovaEspecie(BaseModel):
    nome_cientifico: str
    nome_popular: Optional[str] = None
    familia: Optional[str] = None
    genero: Optional[str] = None
    observacoes: Optional[str] = None
    preencher_pelo_gbif: bool = True  # completa familia/genero vazios pela GBIF, se ela responder
