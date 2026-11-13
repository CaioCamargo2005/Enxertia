"""
Carrega/atualiza as evidencias da literatura no banco (data/enxertia.db).

Uso: python data/importar_literatura.py

O servidor ja faz isso sozinho ao subir. Rode este script depois de editar
data/literatura_enxertia.csv (por exemplo, marcando `conferido = sim` em um
registro cujo trecho voce achou no PDF) se nao quiser reiniciar o servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import db, literatura  # noqa: E402

if __name__ == "__main__":
    db.init_db(seed=True)
    resumo = literatura.importar()
    print(f"{resumo['registros']} registros da literatura ({resumo['novos']} novos).")
    print(f"{resumo['promovidos_ao_banco']} pares promovidos ao banco de combinacoes; "
          f"{resumo['atualizados_no_banco']} atualizados; {resumo['pares_ja_existentes']} ja existiam (mantidos).")
