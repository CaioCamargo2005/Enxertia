"""
Testes da ordem de prioridade em TaxonomyService.resolve():
GBIF -> Reflora -> banco local. Os clientes sao mockados pra nao depender
de rede nem de qual API responde primeiro no ambiente de teste.
"""

from unittest.mock import Mock

from app.taxonomy_service import TaxonomyService


def _cliente_que_resolve(dados):
    cliente = Mock()
    cliente.get_taxonomy.return_value = dados
    return cliente


def _cliente_que_nao_resolve():
    cliente = Mock()
    cliente.get_taxonomy.return_value = None
    return cliente


def test_usa_gbif_quando_disponivel():
    gbif = _cliente_que_resolve({"family": "Rutaceae", "genus": "Citrus"})
    reflora = _cliente_que_nao_resolve()
    servico = TaxonomyService(gbif_client=gbif, reflora_client=reflora)

    resultado = servico.resolve("Citrus sinensis")
    assert resultado.source == "gbif"
    assert resultado.family == "Rutaceae"
    reflora.get_taxonomy.assert_not_called()  # nao precisa tentar Reflora se GBIF ja resolveu


def test_cai_para_reflora_quando_gbif_nao_resolve():
    gbif = _cliente_que_nao_resolve()
    reflora = _cliente_que_resolve({"family": "Rutaceae", "genus": "Citrus"})
    servico = TaxonomyService(gbif_client=gbif, reflora_client=reflora)

    resultado = servico.resolve("Citrus sinensis")
    assert resultado.source == "reflora"


def test_cai_para_banco_local_quando_nenhuma_api_resolve():
    gbif = _cliente_que_nao_resolve()
    reflora = _cliente_que_nao_resolve()
    servico = TaxonomyService(gbif_client=gbif, reflora_client=reflora)

    resultado = servico.resolve("Citrus sinensis")
    assert resultado.source == "fallback_local"
    assert resultado.family == "Rutaceae"


def test_especie_nao_encontrada_em_lugar_nenhum():
    gbif = _cliente_que_nao_resolve()
    reflora = _cliente_que_nao_resolve()
    servico = TaxonomyService(gbif_client=gbif, reflora_client=reflora)

    assert servico.resolve("Especie que nao existe em nenhuma fonte") is None
