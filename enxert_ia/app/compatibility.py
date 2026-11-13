"""
Motor de compatibilidade de enxertia - regras taxonomicas, usado como base e
como fallback do motor de ML (app/ml_service.py) quando o modelo treinado
nao esta disponivel ou nao tem confianca suficiente numa combinacao.

Regra classica de horticultura: quanto mais proximas taxonomicamente porta-enxerto
e enxerto, maior a chance de pega. Isso NAO substitui validacao em campo - e um
ponto de partida para priorizar combinacoes a testar.
"""

from app.models import TaxonomyInfo, CompatibilityResult
from app.ml_service import ml_service
from app import db

SAME_SPECIES = (0.95, "alta", "Mesma especie - compatibilidade esperada muito alta.")
SAME_GENUS = (0.75, "provavel", "Mesmo genero, especies diferentes - compatibilidade comum (ex: citros, Prunus).")
SAME_FAMILY = (0.40, "incerta", "Mesma familia, generos diferentes - compatibilidade possivel, mas precisa de validacao em campo.")
DIFFERENT_FAMILY = (0.05, "improvavel", "Familias diferentes - compatibilidade rara sem tecnicas especiais.")
UNKNOWN = (None, "desconhecida", "Nao foi possivel resolver a taxonomia de uma das especies.")


def score_compatibility(rootstock: str, scion: str,
                         rootstock_taxonomy: TaxonomyInfo = None,
                         scion_taxonomy: TaxonomyInfo = None) -> CompatibilityResult:

    if rootstock_taxonomy is None or scion_taxonomy is None:
        score, level, justification = UNKNOWN
        return CompatibilityResult(
            rootstock=rootstock, scion=scion,
            score=score if score is not None else 0.0,
            level=level, justification=justification,
            rootstock_taxonomy=rootstock_taxonomy, scion_taxonomy=scion_taxonomy,
            source="regras",
        )

    if rootstock_taxonomy.scientific_name.lower() == scion_taxonomy.scientific_name.lower():
        score, level, justification = SAME_SPECIES
    elif rootstock_taxonomy.genus and rootstock_taxonomy.genus == scion_taxonomy.genus:
        score, level, justification = SAME_GENUS
    elif rootstock_taxonomy.family and rootstock_taxonomy.family == scion_taxonomy.family:
        score, level, justification = SAME_FAMILY
    else:
        score, level, justification = DIFFERENT_FAMILY

    return CompatibilityResult(
        rootstock=rootstock, scion=scion,
        score=score, level=level, justification=justification,
        rootstock_taxonomy=rootstock_taxonomy, scion_taxonomy=scion_taxonomy,
        source="regras",
    )


_TEXTO_EVIDENCIA = {
    "citada": "fonte citada",
    "conhecimento_geral": "conhecimento geral, sem citacao formal -- verificar",
    "relato_nao_verificado": "relato nao verificado",
}


def _resultado_do_banco(rootstock, scion, registro, rootstock_taxonomy, scion_taxonomy) -> CompatibilityResult:
    partes = [f"Registro no banco de combinacoes ({_TEXTO_EVIDENCIA.get(registro['tipo_evidencia'], registro['tipo_evidencia'])})"]
    if registro.get("fonte"):
        partes.append(f"fonte: {registro['fonte']}")
    if registro.get("inverso"):
        partes.append("registro cadastrado na ordem inversa (porta-enxerto/enxerto trocados)")
    justificativa = "; ".join(partes) + "."
    if registro.get("observacoes"):
        justificativa += f" {registro['observacoes']}"
    return CompatibilityResult(
        rootstock=rootstock, scion=scion,
        score=registro["compatibilidade"], level=registro["nivel"],
        justification=justificativa,
        rootstock_taxonomy=rootstock_taxonomy, scion_taxonomy=scion_taxonomy,
        source="banco", evidencia=registro["tipo_evidencia"], fonte=registro.get("fonte"),
    )


def hybrid_score(rootstock: str, scion: str,
                  rootstock_taxonomy: TaxonomyInfo = None,
                  scion_taxonomy: TaxonomyInfo = None,
                  motor: str = "auto") -> CompatibilityResult:
    """
    Ponto de entrada usado pelos endpoints. Ordem de decisao no modo "auto":
    1) banco de combinacoes (app/db.py) -> 2) motor de ML -> 3) regras.
    `motor` escolhe o que usar:

    - "regras": sempre usa score_compatibility() (comportamento historico).
    - "ml": tenta o modelo treinado; se ele nao estiver disponivel ou nao
      tiver confianca suficiente na combinacao, cai para as regras (o
      resultado sempre informa `source` corretamente -- nunca finge ter
      usado ML quando na verdade usou regras).
    - "auto" (padrao): consulta o banco primeiro; se o par nao estiver
      registrado, usa o modelo quando ele tem opiniao confiavel, e as regras
      no resto dos casos (incluindo antes do primeiro treino).
    """
    if motor not in ("regras", "ml", "auto"):
        motor = "auto"

    # 1) Banco de combinacoes: registro conhecido tem prioridade sobre
    #    qualquer estimativa. So o modo "auto" consulta o banco.
    if motor == "auto":
        registro = db.buscar_combinacao(rootstock, scion)
        if registro:
            return _resultado_do_banco(rootstock, scion, registro, rootstock_taxonomy, scion_taxonomy)

    if motor != "regras" and rootstock_taxonomy and scion_taxonomy:
        resultado_ml = ml_service.predict_result(rootstock, scion, rootstock_taxonomy, scion_taxonomy)
        if resultado_ml is not None:
            return resultado_ml

    return score_compatibility(rootstock, scion, rootstock_taxonomy, scion_taxonomy)


def rank_candidates(target_name: str, target_taxonomy: TaxonomyInfo, candidates, motor: str = "auto") -> list:
    """
    Rankeia uma lista de especies candidatas pela compatibilidade com a especie
    alvo, do maior pro menor score. Usada tanto para "me de as N melhores opcoes"
    quanto para "compare esses candidatos especificos entre si" - o candidatos
    e so uma lista maior ou menor de TaxonomyInfo. `motor` e repassado para
    hybrid_score() (ver docstring acima).
    """
    resultados = []
    for candidata in candidates:
        if not candidata:
            continue
        if candidata.scientific_name.strip().lower() == target_name.strip().lower():
            continue
        resultado = hybrid_score(target_name, candidata.scientific_name, target_taxonomy, candidata, motor=motor)
        resultados.append(resultado)
    resultados.sort(key=lambda r: r.score, reverse=True)
    return resultados
