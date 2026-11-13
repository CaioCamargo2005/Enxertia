"""
Testes do motor de ML (app/ml_service.py) e da integracao hibrida em
app/compatibility.py. Pressupoe que o modelo ja foi treinado (rode
`python train_model.py` antes de rodar os testes, ou veja
test_ml_service_sem_modelo() abaixo, que testa o caso de modelo ausente
apontando para um caminho que nao existe -- esse nao depende de treino previo).
"""

from pathlib import Path

from app.compatibility import hybrid_score, score_compatibility
from app.ml_service import MLCompatibilityService, ml_service
from app.models import TaxonomyInfo


def _tax(name, family, genus):
    return TaxonomyInfo(scientific_name=name, family=family, genus=genus, source="fallback_local")


def test_ml_service_indisponivel_quando_arquivo_nao_existe():
    servico = MLCompatibilityService(
        model_path=Path("/tmp/nao_existe_ml_model.joblib"),
        meta_path=Path("/tmp/nao_existe_ml_model_meta.json"),
    )
    assert servico.is_available() is False
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Citrus limon", "Rutaceae", "Citrus")
    assert servico.predict(porta, enxerto) is None


def test_hybrid_score_motor_regras_ignora_ml():
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Poncirus trifoliata", "Rutaceae", "Poncirus")
    resultado = hybrid_score("Citrus sinensis", "Poncirus trifoliata", porta, enxerto, motor="regras")
    assert resultado.source == "regras"
    assert resultado.score == 0.40  # mesmo valor de score_compatibility() puro


def test_hybrid_score_auto_usa_ml_quando_disponivel_e_confiavel():
    if not ml_service.is_available():
        import subprocess
        subprocess.run(["python", "train_model.py"], cwd=Path(__file__).parent, check=True)
        ml_service._tentou_carregar = False  # forca recarregar apos treinar

    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Poncirus trifoliata", "Rutaceae", "Poncirus")
    resultado = hybrid_score("Citrus sinensis", "Poncirus trifoliata", porta, enxerto, motor="auto")

    # Essa combinacao tem uma excecao documentada no dataset de treino
    # (Poncirus e o porta-enxerto mais usado do mundo pra citros); o modelo
    # deve aprender que o score e mais alto que a regra pura de "mesma
    # familia, generos diferentes" (0.40).
    assert resultado.source == "ml"
    assert resultado.score > 0.40


def test_hybrid_score_cai_para_regras_sem_taxonomia_completa():
    resultado = hybrid_score("Especie desconhecida", "Citrus limon", None, _tax("Citrus limon", "Rutaceae", "Citrus"), motor="auto")
    assert resultado.source == "regras"
    assert resultado.level == "desconhecida"


def test_score_compatibility_puro_nao_foi_afetado_pela_integracao():
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Citrus limon", "Rutaceae", "Citrus")
    resultado = score_compatibility("Citrus sinensis", "Citrus limon", porta, enxerto)
    assert resultado.source == "regras"
    assert resultado.score == 0.75


def test_ml_se_abstem_para_mesma_especie():
    # O dataset de treino nao tem pares de mesma especie; o modelo nao pode
    # opinar (daria ~0.75) e as regras respondem 0.95.
    tax = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    resultado = hybrid_score("Citrus sinensis", "Citrus sinensis", tax, tax, motor="auto")
    assert resultado.source == "regras"
    assert resultado.score == 0.95
