"""
Motor de compatibilidade baseado em aprendizado de maquina -- complementa
(nao substitui) o motor de regras em app/compatibility.py.

Como funciona:
1. train_model.py treina um RandomForestRegressor sobre data/
   compatibilidade_seed.csv (features: mesma_especie/mesmo_genero/mesma_
   familia + genero/familia de cada lado, one-hot) e salva o modelo em
   app/ml_model.joblib + metadados em app/ml_model_meta.json.
2. Em runtime, MLCompatibilityService carrega esse arquivo (se existir) e
   oferece predict(), que devolve um score continuo em [0, 1] e uma
   confianca estimada pela dispersao dos votos das arvores da floresta
   (baixa dispersao entre arvores = alta confianca).
3. Quando o modelo nao esta disponivel (nao foi treinado ainda) ou a
   confianca fica abaixo de MIN_CONFIDENCE, predict() retorna None -- e
   quem chama (app/compatibility.py) cai de volta para o motor de regras.
   Isso e proposital: preferimos "sem opiniao" a uma opiniao de ML pouco
   confiavel disfarcada de score preciso.

Limitacao honesta (ver data/build_seed_dataset.py e README.md para mais
detalhes): o dataset de treino e pequeno e montado a mao a partir de
conhecimento hortícola geral, nao de uma mineracao sistematica da
literatura. O modelo tende a memorizar as excecoes conhecidas do dataset
em vez de generalizar bem para pares totalmente novos -- ele e uma prova de
conceito do pipeline de treino, nao (ainda) uma fonte mais confiavel que as
regras taxonomicas.
"""

import json
from pathlib import Path
from typing import Optional

from app.models import TaxonomyInfo, CompatibilityResult
from app.score_bands import nivel_para_score

MODEL_PATH = Path(__file__).parent / "ml_model.joblib"
META_PATH = Path(__file__).parent / "ml_model_meta.json"

MIN_CONFIDENCE = 0.45  # abaixo disso, predict() se abstem e devolve None


class MLCompatibilityService:
    """Encapsula o modelo treinado. Falha de forma segura (retorna None/False)
    sempre que o modelo nao esta disponivel, em vez de lancar excecao -- o
    resto do app nunca deve quebrar por causa do motor de ML."""

    def __init__(self, model_path: Path = MODEL_PATH, meta_path: Path = META_PATH):
        self.model_path = model_path
        self.meta_path = meta_path
        self._pipeline = None
        self._meta = None
        self._tentou_carregar = False

    def _carregar(self):
        if self._tentou_carregar:
            return
        self._tentou_carregar = True
        if not self.model_path.exists():
            return
        try:
            import joblib
            self._pipeline = joblib.load(self.model_path)
            if self.meta_path.exists():
                self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except Exception:
            # Modelo corrompido/incompativel com a versao instalada do
            # sklearn etc. -- trata como "indisponivel" em vez de derrubar o
            # servidor.
            self._pipeline = None

    def is_available(self) -> bool:
        self._carregar()
        return self._pipeline is not None

    def metadata(self) -> Optional[dict]:
        self._carregar()
        return self._meta

    def _features(self, rootstock: TaxonomyInfo, scion: TaxonomyInfo):
        import pandas as pd
        return pd.DataFrame([{
            "same_species": int(rootstock.scientific_name.lower() == scion.scientific_name.lower()),
            "same_genus": int(bool(rootstock.genus) and rootstock.genus == scion.genus),
            "same_family": int(bool(rootstock.family) and rootstock.family == scion.family),
            "rootstock_genus": rootstock.genus or "desconhecido",
            "scion_genus": scion.genus or "desconhecido",
            "rootstock_family": rootstock.family or "desconhecido",
            "scion_family": scion.family or "desconhecido",
        }])

    def predict(self, rootstock: TaxonomyInfo, scion: TaxonomyInfo) -> Optional[dict]:
        """Retorna {"score", "level", "confidence"} ou None se o modelo nao
        estiver disponivel, faltar taxonomia suficiente, ou a confianca for
        baixa demais pra valer a pena usar em vez das regras."""
        self._carregar()
        if self._pipeline is None:
            return None
        if not rootstock or not scion or not rootstock.genus or not scion.genus:
            return None
        # O dataset de treino so tem pares de especies DIFERENTES (same_species
        # e sempre 0), entao o modelo nunca aprendeu esse caso e o trataria
        # como "mesmo genero" (~0.75 em vez de 0.95). Sem base pra opinar, se
        # abstem e deixa o motor de regras responder.
        if rootstock.scientific_name.strip().lower() == scion.scientific_name.strip().lower():
            return None

        X = self._features(rootstock, scion)
        preprocessador = self._pipeline.named_steps["prep"]
        floresta = self._pipeline.named_steps["model"]

        X_transformado = preprocessador.transform(X)
        votos = [arvore.predict(X_transformado)[0] for arvore in floresta.estimators_]
        media = sum(votos) / len(votos)
        desvio = (sum((v - media) ** 2 for v in votos) / len(votos)) ** 0.5

        # Confianca heuristica: desvio 0 entre arvores -> confianca 1.0;
        # desvio >= 0.35 (arvores bem divididas) -> confianca proxima de 0.
        confianca = max(0.0, 1.0 - (desvio / 0.35))
        score = max(0.0, min(1.0, media))

        if confianca < MIN_CONFIDENCE:
            return None

        return {"score": score, "level": nivel_para_score(score), "confidence": round(confianca, 2)}

    def predict_result(self, rootstock_name: str, scion_name: str,
                        rootstock_tax: TaxonomyInfo, scion_tax: TaxonomyInfo) -> Optional[CompatibilityResult]:
        pred = self.predict(rootstock_tax, scion_tax)
        if pred is None:
            return None
        return CompatibilityResult(
            rootstock=rootstock_name, scion=scion_name,
            score=pred["score"], level=pred["level"],
            justification=(
                f"Estimado pelo modelo de ML treinado em {self.metadata().get('treinado_em', '?') if self.metadata() else '?'} "
                f"({self.metadata().get('n_amostras', '?') if self.metadata() else '?'} exemplos), "
                f"confianca={pred['confidence']}."
            ),
            rootstock_taxonomy=rootstock_tax, scion_taxonomy=scion_tax,
            source="ml",
        )


# Instancia unica reaproveitada pelo app -- carrega o modelo (se existir)
# so na primeira chamada, nao na importacao do modulo.
ml_service = MLCompatibilityService()
