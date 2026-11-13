"""
Menu interativo de terminal para o Enxert.IA -- alternativa a interface web,
util para testes rapidos ou apresentacao em ambientes sem navegador.

Uso: python cli.py
"""

from app.taxonomy_service import TaxonomyService
from app.compatibility import score_compatibility, rank_candidates
from app.models import TaxonomyInfo

taxonomy_service = TaxonomyService()


def _resolver_ou_avisar(nome: str):
    tax = taxonomy_service.resolve(nome)
    if not tax:
        print(f"  [!] Taxonomia nao encontrada para '{nome}'. Tente um nome da lista (opcao 4).")
    return tax


def recomendar_combinacoes():
    print("\n-- Recomendar combinacoes --")
    especie = input("Especie de referencia (nome cientifico): ").strip()
    tax_alvo = _resolver_ou_avisar(especie)
    if not tax_alvo:
        return

    candidatos_txt = input("Candidatas especificas, separadas por virgula (Enter para usar todo o banco): ").strip()

    if candidatos_txt:
        nomes = [c.strip() for c in candidatos_txt.split(",") if c.strip()]
        pool = []
        for nome in nomes:
            tax = taxonomy_service.resolve(nome)
            if tax:
                pool.append(tax)
            else:
                print(f"  [!] '{nome}' nao encontrada, ignorando.")
    else:
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

    ranking = rank_candidates(especie, tax_alvo, pool)
    if not ranking:
        print("  Nenhuma candidata encontrada para comparar.")
        return

    print(f"\n  Melhores combinacoes para {especie}:")
    for i, r in enumerate(ranking[:10], start=1):
        outra = r.scion if r.rootstock.lower() == especie.lower() else r.rootstock
        print(f"  {i:>2}. {outra:<28} {r.score:.2f} ({r.level}) -- {r.justification}")


def consultar_compatibilidade():
    print("\n-- Consultar compatibilidade --")
    porta = input("Porta-enxerto (nome cientifico): ").strip()
    enxerto = input("Enxerto/copa (nome cientifico): ").strip()

    tax_porta = _resolver_ou_avisar(porta)
    tax_enxerto = _resolver_ou_avisar(enxerto)
    if not tax_porta or not tax_enxerto:
        return

    resultado = score_compatibility(porta, enxerto, tax_porta, tax_enxerto)
    print(f"\n  Score: {resultado.score:.2f} ({resultado.level})")
    print(f"  {resultado.justification}")
    print(f"  Motor: {resultado.source}")


def consultar_taxonomia():
    print("\n-- Consultar taxonomia --")
    nome = input("Nome cientifico: ").strip()
    tax = _resolver_ou_avisar(nome)
    if not tax:
        return
    print(f"\n  Nome: {tax.scientific_name}")
    print(f"  Nome popular: {tax.common_name or '(nao informado)'}")
    print(f"  Familia: {tax.family}")
    print(f"  Genero: {tax.genus}")
    print(f"  Fonte: {tax.source}")


def listar_especies():
    print("\n-- Especies disponiveis no banco local --")
    especies = sorted(taxonomy_service.list_fallback_species(), key=lambda s: s["scientific_name"])
    genero_atual = None
    for sp in especies:
        if sp["genus"] != genero_atual:
            genero_atual = sp["genus"]
            print(f"\n  [{genero_atual}] ({sp['family']})")
        nome_comum = f" -- {sp['common_name']}" if sp.get("common_name") else ""
        print(f"    {sp['scientific_name']}{nome_comum}")
    print(f"\n  Total: {len(especies)} especies.")


PARES_DE_TESTE = [
    ("Citrus sinensis", "Citrus limon"),
    ("Citrus sinensis", "Poncirus trifoliata"),
    ("Prunus persica", "Prunus armeniaca"),
    ("Malus domestica", "Pyrus communis"),
    ("Citrus sinensis", "Coffea arabica"),
]


def rodar_exemplos():
    print("\n-- Exemplos prontos --")
    for porta, enxerto in PARES_DE_TESTE:
        tax_porta = taxonomy_service.resolve(porta)
        tax_enxerto = taxonomy_service.resolve(enxerto)
        resultado = score_compatibility(porta, enxerto, tax_porta, tax_enxerto)
        print(f"  {porta:<20} x {enxerto:<22} -> {resultado.score:.2f} ({resultado.level})")


MENU = """
==================================================
  Enxert.IA -- Menu
==================================================
  1) Melhores combinacoes para uma especie (ranking)
  2) Consultar compatibilidade entre duas especies
  3) Consultar taxonomia de uma especie
  4) Listar especies disponiveis
  5) Rodar exemplos prontos
  6) Sair
--------------------------------------------------"""


def main():
    acoes = {
        "1": recomendar_combinacoes,
        "2": consultar_compatibilidade,
        "3": consultar_taxonomia,
        "4": listar_especies,
        "5": rodar_exemplos,
    }
    while True:
        print(MENU)
        escolha = input("Escolha uma opcao: ").strip()
        if escolha == "6":
            print("Ate mais!")
            break
        acao = acoes.get(escolha)
        if acao:
            acao()
        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    main()
