# Enxertia: Enxert.IA + Enxert.DB

Projeto de curso da Fatec Shunji Nishimura. Equipe: Brenda, Caio, Gustavo e Lorena.

## O que tem nesta pasta

| Pasta | Conteúdo |
| --- | --- |
| `enxert_ia/` | API e site: consulta de compatibilidade, recomendações, cadastro de plantas próprias (página **Plantas**), banco de combinações, evidências da literatura e a página **Catálogo** (que lê o Enxert.DB) |
| `enxert_db/` | banco SQLite do catálogo agronômico, menu em Python, automação e registros da literatura |
| `docs/` | documentação (Word), slides atualizados (PDF) e a planilha com os registros da literatura e suas fontes |

## Como rodar o site

Precisa de Python 3.10 ou mais novo.

```bash
cd enxert_ia
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

O navegador abre sozinho em http://127.0.0.1:8000. A página **Catálogo** cria e lê `enxert_db/enxert.db` automaticamente, por isso as duas pastas precisam ficar lado a lado.

## Como usar o menu do Enxert.DB

```bash
cd enxert_db
python interface_enxert_db.py
```

## Testes

```bash
cd enxert_ia && pytest     # 71 testes
cd ../enxert_db && pytest  # 25 testes
```

## O que ainda não foi verificado

- Os registros da literatura (53 no Enxert.IA e 45 no Enxert.DB, das mesmas 5 fontes) foram extraídos automaticamente e nenhum foi conferido no PDF.
- As chamadas reais ao GBIF e ao NCBI foram testadas só com respostas simuladas.
