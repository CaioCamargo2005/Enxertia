"""
Treina o classificador de ML de compatibilidade e salva em app/ml_model.joblib
(+ metadados em app/ml_model_meta.json).

Le data/compatibilidade_seed.csv (gerado por data/build_seed_dataset.py --
rode aquele script primeiro se o CSV nao existir ou se quiser regenera-lo).

Uso: python train_model.py

Sobre os numeros que este script imprime: a validacao cruzada aqui usa um
dataset pequeno (~140 pares) e montado a mao (ver data/build_seed_dataset.py
para a explicacao completa de onde vieram os rotulos). Trate a metrica
impressa como um sinal de que o pipeline esta funcionando, nao como uma
medida confiavel de qualidade preditiva em campo -- isso so vem com um
dataset maior e validado, que e o proximo passo do roadmap (mineracao da
literatura Alice/Infoteca-e).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import classification_report
from sklearn.model_selection import KFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.score_bands import nivel_para_score

DATA_PATH = Path(__file__).parent / "data" / "compatibilidade_seed.csv"
MODEL_PATH = Path(__file__).parent / "app" / "ml_model.joblib"
META_PATH = Path(__file__).parent / "app" / "ml_model_meta.json"

NUMERIC_FEATURES = ["same_species", "same_genus", "same_family"]
CATEGORICAL_FEATURES = ["rootstock_genus", "scion_genus", "rootstock_family", "scion_family"]


def carregar_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"{DATA_PATH} nao encontrado. Rode primeiro: python data/build_seed_dataset.py"
        )
    df = pd.read_csv(DATA_PATH)
    df["same_species"] = 0  # o seed dataset so tem pares de especies diferentes
    df["same_genus"] = (df["rootstock_genus"] == df["scion_genus"]).astype(int)
    df["same_family"] = (df["rootstock_family"] == df["scion_family"]).astype(int)
    return df


def construir_pipeline() -> Pipeline:
    preprocessador = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERIC_FEATURES),
    ])
    modelo = RandomForestRegressor(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42,
    )
    return Pipeline([("prep", preprocessador), ("model", modelo)])


def main():
    df = carregar_dataset()
    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df["score"]

    pipeline = construir_pipeline()

    # Validacao cruzada (5 folds) so pra ter um numero honesto de "o quao bem
    # o modelo se sai em pares que ele nao viu durante aquele fold" -- com um
    # dataset deste tamanho, o numero tem bastante variancia entre folds.
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    scores_mae = -cross_val_score(pipeline, X, y, cv=cv, scoring="neg_mean_absolute_error")

    # Precision/recall/F1 por nivel ("alta"/"provavel"/"incerta"/"improvavel").
    # O modelo e um REGRESSOR (preve um score continuo, nao uma classe), entao
    # essas metricas de classificacao nao saem direto do sklearn -- calculamos
    # assim: pegamos a predicao de cada linha feita por um fold onde ela NAO
    # entrou no treino (cross_val_predict, fora-da-amostra de verdade), convertemos
    # esse score continuo pro nivel categorico pelas mesmas faixas que o app usa
    # em runtime (app/score_bands.py), e comparamos com o nivel "verdadeiro" do
    # CSV. Isso da precision/recall/F1 reais, nao inventados.
    y_pred_cv = cross_val_predict(pipeline, X, y, cv=cv)
    nivel_real = df["level"].tolist()
    nivel_previsto = [nivel_para_score(s) for s in y_pred_cv]
    relatorio_classificacao = classification_report(
        nivel_real, nivel_previsto, zero_division=0, output_dict=True
    )

    # Aviso honesto: varias linhas do seed dataset compartilham exatamente as
    # mesmas features categoricas (todo par Citrus x Citrus sem excecao
    # documentada vira o mesmo vetor de entrada). Isso faz o MAE de validacao
    # cruzada parecer ótimo mesmo quando o modelo so esta memorizando o rotulo
    # de linhas duplicadas que vazaram entre treino e teste -- nao porque
    # aprendeu a generalizar para pares de especies nunca vistos.
    n_combinacoes_unicas = len(X.drop_duplicates())
    razao_duplicacao = round(1 - (n_combinacoes_unicas / len(X)), 2)

    pipeline.fit(X, y)

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    meta = {
        "treinado_em": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "n_amostras": len(df),
        "mae_validacao_cruzada_5fold": round(float(scores_mae.mean()), 3),
        "mae_desvio_padrao_entre_folds": round(float(scores_mae.std()), 3),
        "classificacao_por_nivel_fora_da_amostra": {
            nivel: {
                "precision": round(vals["precision"], 2),
                "recall": round(vals["recall"], 2),
                "f1": round(vals["f1-score"], 2),
                "n": int(vals["support"]),
            }
            for nivel, vals in relatorio_classificacao.items()
            if nivel not in ("accuracy", "macro avg", "weighted avg")
        },
        "recall_macro": round(relatorio_classificacao["macro avg"]["recall"], 2),
        "precision_macro": round(relatorio_classificacao["macro avg"]["precision"], 2),
        "f1_macro": round(relatorio_classificacao["macro avg"]["f1-score"], 2),
        "combinacoes_unicas_de_features": n_combinacoes_unicas,
        "proporcao_de_linhas_duplicadas_em_features": razao_duplicacao,
        "features_categoricas": CATEGORICAL_FEATURES,
        "features_numericas": NUMERIC_FEATURES,
        "origem_dataset": (
            "seed dataset curado a mao a partir de conhecimento horticola geral "
            "(ver data/build_seed_dataset.py) -- NAO e literatura minerada sistematicamente."
        ),
        "aviso_mae": (
            f"{n_combinacoes_unicas} combinacoes unicas de generos/familias entre {len(df)} linhas "
            f"({int(razao_duplicacao * 100)}% das linhas compartilham features com outra linha) -- "
            "o MAE e as metricas de classificacao acima sao otimistas por causa dessa duplicacao, "
            "nao medem generalizacao real para pares de especies nunca vistos. recall/precision/f1 "
            "foram calculados fora-da-amostra (cross_val_predict), nao sobre o treino, mas o viés "
            "de duplicacao de features entre folds continua valendo."
        ),
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Modelo treinado com {len(df)} amostras.")
    print(f"MAE (validacao cruzada, 5 folds): {meta['mae_validacao_cruzada_5fold']} "
          f"(+/- {meta['mae_desvio_padrao_entre_folds']})")
    print()
    print("Precision / Recall / F1 por nivel (fora-da-amostra, cross_val_predict):")
    print(f"{'nivel':<14}{'precision':>10}{'recall':>10}{'f1':>10}{'n':>6}")
    for nivel, vals in meta["classificacao_por_nivel_fora_da_amostra"].items():
        print(f"{nivel:<14}{vals['precision']:>10}{vals['recall']:>10}{vals['f1']:>10}{vals['n']:>6}")
    print(f"{'macro avg':<14}{meta['precision_macro']:>10}{meta['recall_macro']:>10}{meta['f1_macro']:>10}")
    print()
    print(f"AVISO: {meta['aviso_mae']}")
    print(f"Salvo em: {MODEL_PATH}")
    print(f"Metadados em: {META_PATH}")


if __name__ == "__main__":
    main()
