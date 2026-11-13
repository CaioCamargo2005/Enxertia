"""
Demo nao-interativa: roda uma bateria de exemplos e imprime os resultados.
Util para conferir rapidamente que a instalacao esta funcionando, ou para
rodar em apresentacao sem depender de input do usuario.

Uso: python demo_offline.py
"""

from app.taxonomy_service import TaxonomyService
from app.compatibility import score_compatibility, rank_candidates
from app.models import TaxonomyInfo

PARES_DE_TESTE = [
    ("Citrus sinensis", "Citrus limon"),
    ("Citrus sinensis", "Poncirus trifoliata"),
    ("Citrus sinensis", "Fortunella margarita"),
    ("Prunus persica", "Prunus armeniaca"),
    ("Prunus persica", "Malus domestica"),
    ("Malus domestica", "Pyrus communis"),
    ("Coffea arabica", "Coffea canephora"),
    ("Theobroma cacao", "Theobroma grandiflorum"),
    ("Citrus sinensis", "Coffea arabica"),
    ("Vitis vinifera", "Vitis labrusca"),
]


def main():
    taxonomy_service = TaxonomyService()

    print("=" * 60)
    print("Enxert.IA -- demo offline (compatibilidade par-a-par)")
    print("=" * 60)
    for porta, enxerto in PARES_DE_TESTE:
        tax_porta = taxonomy_service.resolve(porta)
        tax_enxerto = taxonomy_service.resolve(enxerto)
        resultado = score_compatibility(porta, enxerto, tax_porta, tax_enxerto)
        print(f"{porta:<22} x {enxerto:<24} -> {resultado.score:.2f} ({resultado.level}) [{resultado.source}]")

    print()
    print("=" * 60)
    print("Enxert.IA -- demo offline (ranking / recomendacoes)")
    print("=" * 60)
    especie_alvo = "Citrus sinensis"
    tax_alvo = taxonomy_service.resolve(especie_alvo)
    pool = [
        TaxonomyInfo(
            scientific_name=sp["scientific_name"],
            common_name=sp.get("common_name"),
            family=sp.get("family"),
            genus=sp.get("genus"),
            source="fallback_local",
        )
        for sp in taxonomy_service.list_fallback_species()
    ]
    ranking = rank_candidates(especie_alvo, tax_alvo, pool)
    print(f"Top 5 combinacoes para {especie_alvo}:")
    for i, r in enumerate(ranking[:5], start=1):
        outra = r.scion if r.rootstock.lower() == especie_alvo.lower() else r.rootstock
        print(f"  {i}. {outra:<26} {r.score:.2f} ({r.level})")

    print()
    print(f"Total de especies no banco local: {len(taxonomy_service.list_fallback_species())}")


if __name__ == "__main__":
    main()
