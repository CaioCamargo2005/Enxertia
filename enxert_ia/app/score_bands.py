"""
Faixas que convertem um score continuo (0-1) no nivel categorico usado em
toda a aplicacao ("alta"/"provavel"/"incerta"/"improvavel"). Usado tanto
pelo motor de ML (app/ml_service.py, train_model.py) quanto pelo gerador do
dataset de treino (data/build_seed_dataset.py) -- centralizado aqui pra
garantir que as tres partes concordem sobre onde cada faixa comeca/termina.

Note que essas faixas NAO sao as mesmas do motor de regras
(app/compatibility.py), que usa pontos fixos (0.95/0.75/0.40/0.05) em vez de
faixas -- o motor de ML produz um score continuo, entao precisa de
intervalos pra decidir o nivel.
"""

ALTA_MIN = 0.80
PROVAVEL_MIN = 0.55
INCERTA_MIN = 0.20


def nivel_para_score(score: float) -> str:
    if score >= ALTA_MIN:
        return "alta"
    if score >= PROVAVEL_MIN:
        return "provavel"
    if score >= INCERTA_MIN:
        return "incerta"
    return "improvavel"
