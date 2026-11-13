# Enxert.DB

Banco SQLite com o catálogo agronômico do projeto: plantas, métodos de enxertia, compatibilidade (status, taxa de pegamento, método), biomarcadores e resistências dos porta-enxertos.

## Como usar

Deixe todos os arquivos desta pasta juntos e rode:

```bash
python interface_enxert_db.py
```

Na primeira execução o banco `enxert.db` é criado com os dados iniciais da equipe e os registros da literatura. Para ver o catálogo no navegador, use a página **Catálogo** do Enxert.IA (pasta `../enxert_ia`).

| Arquivo | Para que serve |
| --- | --- |
| `interface_enxert_db.py` | menu de consulta e cadastro (opções 1 a 7) |
| `banco_enxert_db.py` | cria, migra e carrega o banco (usado pelo menu, pela automação e pelo site) |
| `enxert_db.sql` | estrutura e dados iniciais da equipe |
| `literatura_enxert_db.sql` | 45 combinações de 5 fontes abertas, com fonte, trecho e "conferido" |
| `auto_enxert_db.py` | mostra o que o catálogo sabe sobre um par e, se não houver registro, calcula uma estimativa por parentesco |
| `ncbi_taxonomia.py` | opção 7 do menu: confere TaxID e taxonomia no NCBI |

## Registros da literatura

- Cada combinação tem `id_fonte` (tabela `Fontes`, com referência e link), o `trecho` que a sustenta e `conferido` (0 ou 1).
- **Nenhum foi conferido ainda.** A extração foi automática; para marcar como conferido, ache o trecho no PDF e rode `UPDATE Compatibilidade SET conferido = 1 WHERE id_compatibilidade = ...` (ou edite no DB Browser).
- O status só foi preenchido quando a fonte usa as palavras "compatível" ou "incompatível". Nos outros casos fica vazio e o que a fonte diz vai em `observacoes`.
- Taxa de pegamento só aparece onde a fonte mede sobrevivência (estudo de melancia, por método de enxertia).
- Plantas novas entram sem TaxID; use a opção 7 para preencher pelo NCBI.

## Sobre a automação (`auto_enxert_db.py`)

A versão anterior sobrescrevia registros reais e gravava percentuais inventados (95%, 85%, 0%) como taxa de pegamento. Em um `enxert_2.db` de teste, ela trocou o registro Melancia × Abóbora da equipe (98%, "Excelente resistência a Fusarium...") por "85%, Afinidade moderada". A versão nova nunca altera a tabela `Compatibilidade` e grava estimativas numa tabela separada, `Estimativas`. Se você usou a versão antiga, recrie o banco (apague o `enxert.db` e rode o menu) em vez de reaproveitar o arquivo.

## Testes

```bash
pip install pytest
pytest
```
