"""
Confirma que train_model.py de fato calcula e salva precision/recall/F1 por
nivel (nao so o MAE de regressao) -- isso foi adicionado especificamente
porque recall/precision e algo esperado pra avaliar esse tipo de trabalho,
e um RandomForestRegressor nao devolve essas metricas de classificacao de
graca (ver comentario em train_model.py).
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
META_PATH = PROJECT_ROOT / "app" / "ml_model_meta.json"


def test_meta_tem_metricas_de_classificacao_apos_treino():
    subprocess.run([sys.executable, "train_model.py"], cwd=PROJECT_ROOT, check=True)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    assert "classificacao_por_nivel_fora_da_amostra" in meta
    for nivel in ("alta", "provavel", "incerta", "improvavel"):
        assert nivel in meta["classificacao_por_nivel_fora_da_amostra"]
        vals = meta["classificacao_por_nivel_fora_da_amostra"][nivel]
        assert 0.0 <= vals["precision"] <= 1.0
        assert 0.0 <= vals["recall"] <= 1.0
        assert 0.0 <= vals["f1"] <= 1.0
        assert vals["n"] > 0

    assert 0.0 <= meta["recall_macro"] <= 1.0
    assert 0.0 <= meta["precision_macro"] <= 1.0
    # soma de "n" por nivel deve bater com o total de amostras do dataset
    total_n = sum(v["n"] for v in meta["classificacao_por_nivel_fora_da_amostra"].values())
    assert total_n == meta["n_amostras"]
