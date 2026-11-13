"""
Gera data/compatibilidade_seed.csv -- o dataset "semente" usado para treinar
o classificador de ML (train_model.py).

IMPORTANTE - de onde vem esse dataset (leia antes de confiar nos numeros):
Isso NAO e um dataset minerado sistematicamente da literatura (Alice/
Infoteca-e via OAI-PMH), que e o que o roadmap do projeto descreve como meta
de longo prazo. Minerar e rotular aquele acervo exigiria acesso a rede e um
pipeline de NLP que estao fora do escopo de tempo desta etapa. Em vez disso,
este dataset "semente" foi montado a mao a partir de conhecimento hortícola
amplamente documentado (manuais de fruticultura/propagacao, praticas
comerciais consolidadas) para deixar o pipeline de treino -> modelo ->
integracao funcionando de ponta a ponta com dados honestos, mesmo que em
escala pequena.

A maior parte dos pares recebe o mesmo score que a regra taxonomica (mesma
especie/genero/familia) ja daria -- ou seja, no caso geral o rotulo "verdade"
concorda com a regra. Um numero pequeno de pares recebe um rotulo diferente
do que a regra taxonomica sozinha daria, refletindo excecoes conhecidas e
bem documentadas na pratica de enxertia (ex: laranja sobre trifólio é o
porta-enxerto mais usado no mundo, apesar de serem generos diferentes; maca
e pera raramente sao compativeis apesar de serem da mesma familia). Essas
excecoes sao o que da ao classificador algo a aprender alem do que a arvore
de decisao "mesma especie/genero/familia" ja faz sozinha.

Limitacao honesta: com poucos exemplos por par especifico, o modelo treinado
tende a memorizar essas excecoes conhecidas em vez de generalizar para pares
nunca vistos. Ele e util como prova de conceito do pipeline de ML, nao como
substituto definitivo das regras. Ver README.md, secao "Sistema de
treinamento de dados", para mais detalhes.

Uso: python data/build_seed_dataset.py
"""

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # pra importar app.score_bands
from app.score_bands import nivel_para_score

FALLBACK_PATH = Path(__file__).parent.parent / "app" / "taxonomy_fallback.json"
OUT_PATH = Path(__file__).parent / "compatibilidade_seed.csv"

# Score-base por nivel de proximidade taxonomica -- mesmos valores usados
# pelo motor de regras (app/compatibility.py), para manter os dois sistemas
# comparaveis por padrao.
SCORE_SAME_GENUS = 0.75
SCORE_SAME_FAMILY = 0.40
SCORE_DIFFERENT_FAMILY = 0.05

# Excecoes conhecidas (pares especificos, nao capturadas pela regra
# taxonomica pura) -- fonte: praticas de propagacao amplamente documentadas
# em manuais de fruticultura/viticultura/cafeicultura, nao um estudo
# especifico. Chave: par de nomes cientificos (ordem nao importa).
EXCECOES = {
    frozenset({"Citrus sinensis", "Poncirus trifoliata"}):
        (0.88, "excecao: Poncirus trifoliata e o porta-enxerto mais usado no mundo para citros, apesar de generos diferentes"),
    frozenset({"Citrus reticulata", "Poncirus trifoliata"}):
        (0.80, "excecao: trifolio tambem e porta-enxerto consolidado para tangerinas"),
    frozenset({"Citrus paradisi", "Poncirus trifoliata"}):
        (0.65, "excecao: combinacao usada comercialmente, mas com mais restricao de solo que laranja/trifolio"),
    frozenset({"Citrus sinensis", "Fortunella margarita"}):
        (0.55, "excecao: kunquate tem compatibilidade razoavel com citros, acima da media de mesma familia"),
    frozenset({"Malus domestica", "Pyrus communis"}):
        (0.10, "excecao: maca e pera raramente sao compativeis na pratica apesar de serem Rosaceae"),
    frozenset({"Pyrus communis", "Eriobotrya japonica"}):
        (0.45, "excecao: nespereira por vezes enxertada em marmeleiro/pereira com compatibilidade moderada documentada"),
    frozenset({"Prunus persica", "Prunus avium"}):
        (0.30, "excecao: incompatibilidade tardia bem documentada entre pessego e cereja"),
    frozenset({"Prunus armeniaca", "Prunus domestica"}):
        (0.45, "excecao: damasco sobre ameixeira tem incompatibilidade tardia frequente em manuais de fruticultura"),
    frozenset({"Prunus persica", "Prunus dulcis"}):
        (0.80, "excecao: pessego e amendoeira sao interférteis e tem alta compatibilidade de enxertia documentada"),
    frozenset({"Vitis vinifera", "Vitis labrusca"}):
        (0.90, "excecao: enxertia de vinifera sobre porta-enxertos americanos e pratica padrao mundial (resistencia a filoxera)"),
    frozenset({"Theobroma cacao", "Theobroma grandiflorum"}):
        (0.35, "excecao: ensaios de enxertia cacau/cupuacu no Brasil mostram compatibilidade inconsistente apesar do mesmo genero"),
    frozenset({"Coffea arabica", "Coffea canephora"}):
        (0.80, "excecao: enxertia de arabica sobre porta-enxerto robusta e pratica documentada para resistencia a nematoides"),
    frozenset({"Diospyros kaki", "Diospyros virginiana"}):
        (0.82, "excecao: caqui japones sobre porta-enxertos Diospyros americanos e pratica consolidada"),
    frozenset({"Passiflora edulis", "Passiflora alata"}):
        (0.78, "excecao: maracuja-azedo sobre porta-enxertos de Passiflora silvestres e pratica para resistencia a doencas de solo"),
    frozenset({"Passiflora edulis", "Passiflora nitida"}):
        (0.75, "excecao: mesma logica do par acima -- porta-enxerto silvestre buscando tolerancia a fusariose"),
}


def _familia_da(especies_por_nome, nome):
    return especies_por_nome[nome]["family"]


def _genero_de(especies_por_nome, nome):
    return especies_por_nome[nome]["genus"]


def gerar_pares(especies):
    """
    Gera os pares a incluir no CSV: todos os pares dentro do mesmo genero,
    todos os pares dentro da mesma familia (generos diferentes) e uma amostra
    de pares entre familias diferentes -- pra nao deixar o dataset 100%
    "positivo".
    """
    especies_por_nome = {e["scientific_name"]: e for e in especies}
    nomes = list(especies_por_nome.keys())

    pares = []
    for a, b in combinations(nomes, 2):
        fam_a, fam_b = _familia_da(especies_por_nome, a), _familia_da(especies_por_nome, b)
        gen_a, gen_b = _genero_de(especies_por_nome, a), _genero_de(especies_por_nome, b)

        if gen_a == gen_b:
            pares.append((a, b, "mesmo_genero"))
        elif fam_a == fam_b:
            pares.append((a, b, "mesma_familia"))

    # Amostra fixa de pares entre familias diferentes, pra ter exemplos
    # negativos claros no dataset (senao o modelo nunca ve "improvavel").
    pares_familias_diferentes = [
        ("Citrus sinensis", "Coffea arabica"),
        ("Citrus sinensis", "Theobroma cacao"),
        ("Malus domestica", "Vitis vinifera"),
        ("Prunus persica", "Mangifera indica"),
        ("Coffea arabica", "Vitis vinifera"),
        ("Theobroma cacao", "Passiflora edulis"),
        ("Persea americana", "Citrus sinensis"),
        ("Olea europaea", "Prunus persica"),
        ("Camellia sinensis", "Coffea arabica"),
        ("Punica granatum", "Vitis vinifera"),
        ("Diospyros kaki", "Malus domestica"),
        ("Solanum lycopersicum", "Cucumis sativus"),
    ]
    for a, b in pares_familias_diferentes:
        pares.append((a, b, "familia_diferente"))

    return pares, especies_por_nome


def score_para_par(a, b, tipo):
    excecao = EXCECOES.get(frozenset({a, b}))
    if excecao:
        return excecao

    if tipo == "mesmo_genero":
        return SCORE_SAME_GENUS, "regra geral: mesmo genero"
    if tipo == "mesma_familia":
        return SCORE_SAME_FAMILY, "regra geral: mesma familia, generos diferentes"
    return SCORE_DIFFERENT_FAMILY, "regra geral: familias diferentes"


def main():
    with open(FALLBACK_PATH, encoding="utf-8") as f:
        especies = json.load(f)["species"]

    pares, especies_por_nome = gerar_pares(especies)

    linhas = []
    for a, b, tipo in pares:
        score, nota = score_para_par(a, b, tipo)
        linhas.append({
            "rootstock": a,
            "scion": b,
            "rootstock_genus": _genero_de(especies_por_nome, a),
            "scion_genus": _genero_de(especies_por_nome, b),
            "rootstock_family": _familia_da(especies_por_nome, a),
            "scion_family": _familia_da(especies_por_nome, b),
            "score": score,
            "level": nivel_para_score(score),
            "nota": nota,
        })

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)

    print(f"Gerado {OUT_PATH} com {len(linhas)} pares rotulados.")
    print(f"  mesmo_genero/mesma_familia/familia_diferente conforme regra, "
          f"com {len(EXCECOES)} excecoes documentadas aplicadas.")


if __name__ == "__main__":
    main()
