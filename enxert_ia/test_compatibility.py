from app.compatibility import score_compatibility
from app.models import TaxonomyInfo


def _tax(name, family, genus, source="fallback_local"):
    return TaxonomyInfo(scientific_name=name, family=family, genus=genus, source=source)


def test_same_species():
    t = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    r = score_compatibility("Citrus sinensis", "Citrus sinensis", t, t)
    assert r.score == 0.95
    assert r.level == "alta"
    assert r.source == "regras"


def test_same_genus():
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Citrus limon", "Rutaceae", "Citrus")
    r = score_compatibility("Citrus sinensis", "Citrus limon", porta, enxerto)
    assert r.score == 0.75
    assert r.level == "provavel"


def test_same_family():
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Poncirus trifoliata", "Rutaceae", "Poncirus")
    r = score_compatibility("Citrus sinensis", "Poncirus trifoliata", porta, enxerto)
    assert r.score == 0.40
    assert r.level == "incerta"


def test_different_family():
    porta = _tax("Citrus sinensis", "Rutaceae", "Citrus")
    enxerto = _tax("Coffea arabica", "Rubiaceae", "Coffea")
    r = score_compatibility("Citrus sinensis", "Coffea arabica", porta, enxerto)
    assert r.score == 0.05
    assert r.level == "improvavel"


def test_unknown_taxonomy():
    r = score_compatibility("Especie inventada", "Coffea arabica", None, _tax("Coffea arabica", "Rubiaceae", "Coffea"))
    assert r.level == "desconhecida"
    assert r.score == 0.0
