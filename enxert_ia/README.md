# Enxert.IA

Sistema de apoio a decisao para **enxertia agricola**. O objetivo e
**automatizar a consulta**: dadas duas plantas, dizer se a enxertia e
compativel, de onde vem essa resposta e quanto confiar nela; e, dada uma
especie, recomendar as melhores combinacoes.

A resposta vem de tres camadas, em ordem de confiabilidade: um **banco de
combinacoes** com tipo de evidencia e fonte por registro, um **modelo de ML**
e **regras taxonomicas**. A taxonomia vem de uma API publica real (GBIF).
Cada resposta diz qual camada a produziu.

## Por que existe

Trabalho de curso ("rotina") com o requisito de usar APIs de forma densa. O
nucleo e a consulta de compatibilidade sustentada por dados com procedencia
explicita (banco) e por estimativa (ML e regras) quando o par nao esta
registrado. Identificacao de planta por foto foi avaliada e **retirada** do
projeto por estar fora desse objetivo.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env       # opcional -- nenhuma chave e obrigatoria

uvicorn app.main:app --reload
```

O servidor abre automaticamente uma aba do navegador no hub (`/`) assim que
sobe. Desative com `ENXERTIA_NO_AUTOOPEN=1` no `.env` se estiver usando
`--reload` e nao quiser uma aba nova a cada hot-reload.

Alternativas:
- `python cli.py` -- menu interativo de terminal, sem precisar de navegador.
- `python demo_offline.py` -- roda uma bateria de exemplos prontos e imprime
  o resultado, sem precisar do servidor rodando.

## Estrutura

```
app/
  main.py               endpoints FastAPI + hub estatico
  models.py             modelos Pydantic (TaxonomyInfo, CompatibilityResult)
  compatibility.py       motor de regras + hybrid_score() (integra regras e ML)
  db.py                  banco de combinacoes (SQLite): consulta, cadastro, seed
  ml_service.py          carrega o modelo treinado e faz as predicoes de ML
  taxonomy_service.py    resolve taxonomia (GBIF -> Reflora -> fallback local)
  taxonomy_fallback.json banco local de ~77 especies relevantes pra enxertia
  clients/
    gbif.py                cliente da GBIF Species API -- fonte primaria, real e confirmada
    reflora.py              cliente da API do Reflora/JBRJ -- schema nunca confirmado, best-effort
  ml_model.joblib         modelo treinado (gerado por train_model.py, nao versionar se for privado)
  ml_model_meta.json      metadados do ultimo treino (data, tamanho, metricas)
data/
  enxertia.db             banco de combinacoes (criado e semeado automaticamente ao subir o servidor)
  build_seed_dataset.py   gera o CSV de treino a partir do banco de especies + excecoes conhecidas
  compatibilidade_seed.csv dataset "semente" usado por train_model.py
train_model.py            treina o modelo de ML e salva em app/ml_model.*
web/                      frontend estatico (hub + paginas Banco, Recomendar e Compatibilidade)
cli.py                    menu de terminal
demo_offline.py           demo nao-interativa
test_*.py                 testes (pytest)
```

## Endpoints principais

| Endpoint | Descricao |
|---|---|
| `GET /especies` | lista as ~77 especies do banco local (alimenta os seletores da UI) |
| `GET /taxonomia/{nome_cientifico}` | resolve familia/genero de uma especie (Reflora, com fallback local) |
| `GET /banco/combinacoes?q=` | lista/filtra os registros do banco de combinacoes |
| `POST /banco/combinacoes` | cadastra uma combinacao (evidencia `citada` exige `fonte`) |
| `DELETE /banco/combinacoes/{id}` | apaga um registro |
| `GET /compatibilidade?porta_enxerto=&enxerto=&motor=` | compatibilidade par-a-par, com justificativa |
| `GET /recomendacoes?especie=&candidatos=&limite=&motor=` | ranking das melhores combinacoes (contra todo o banco, ou contra uma lista especifica de candidatas) |
| `GET /status` | saude do servidor + se o modelo de ML esta carregado e seus metadados |

O parametro `motor` (em `/compatibilidade` e `/recomendacoes`) aceita:
- `auto` (padrao) -- banco de combinacoes -> modelo de ML (se confiavel) ->
  regras taxonomicas.
- `ml` -- modelo de ML -> regras, ignorando o banco.
- `regras` -- so o motor de regras.

O campo `source` de toda resposta diz qual camada gerou aquele score
(`"banco"`, `"ml"` ou `"regras"`); quando vem do banco, `evidencia` e
`fonte` acompanham.

## Sistema de treinamento de dados (motor de ML)

Alem do motor de regras taxonomicas (mesma especie/genero/familia), o
projeto tem um segundo motor de decisao: um `RandomForestRegressor` do
scikit-learn treinado para prever o score de compatibilidade.

### Pipeline

1. **`data/build_seed_dataset.py`** gera `data/compatibilidade_seed.csv`: um
   dataset rotulado de pares porta-enxerto/enxerto, construido a partir do
   banco de ~77 especies + um conjunto pequeno de excecoes conhecidas (ex:
   laranja sobre trifólio funciona muito melhor na pratica do que a regra
   "familias diferentes" sozinha sugeriria; maca sobre pereira raramente
   funciona apesar de serem da mesma familia).
2. **`train_model.py`** le esse CSV, monta features (mesma especie/genero/
   familia + genero/familia de cada lado, one-hot) e treina um
   `RandomForestRegressor` (scikit-learn, 200 arvores, `max_depth=6`,
   `min_samples_leaf=2`), salvando em `app/ml_model.joblib` + metadados em
   `app/ml_model_meta.json`: data do treino, tamanho do dataset, MAE de
   validacao cruzada (5 folds) e **precision/recall/F1 por nivel**, estes
   calculados fora-da-amostra (`cross_val_predict`) convertendo o score
   continuo previsto em nivel pelas mesmas faixas usadas em runtime
   (`app/score_bands.py`) e comparando com o nivel real do CSV.

   Ultimo treino (`app/ml_model_meta.json`):

   | nivel | precision | recall | f1 | n |
   |---|---|---|---|---|
   | alta | 0.00 | 0.00 | 0.00 | 6 |
   | provavel | 0.79 | 0.95 | 0.86 | 40 |
   | incerta | 0.94 | 0.93 | 0.93 | 81 |
   | improvavel | 1.00 | 0.92 | 0.96 | 13 |
   | **macro avg** | **0.68** | **0.70** | **0.69** | 140 |

   Recall bom pra tres dos quatro niveis -- mas **recall 0 pra "alta"**: so
   6 exemplos tem esse rotulo no dataset, e os hiperparametros conservadores
   do regressor (`max_depth`/`min_samples_leaf`, escolhidos de proposito pra
   nao decorar o dataset pequeno) puxam a predicao pra media da vizinhanca,
   entao o modelo quase nunca arrisca prever um score alto o bastante pra
   cair na faixa "alta". Isso so melhora com mais exemplos rotulados "alta"
   no dataset de treino.
3. **`app/ml_service.py`** carrega esse modelo em runtime e oferece
   `predict()`. A confianca de cada predicao e estimada pela dispersao dos
   votos das arvores da floresta -- quando as arvores discordam muito entre
   si, o servico se abstem (retorna `None`) e quem chamou cai de volta pro
   motor de regras, em vez de expor um numero pouco confiavel.
4. **`app/compatibility.py`** (`hybrid_score()`) decide, por chamada, se usa
   o motor de ML ou o de regras, conforme o parametro `motor` do endpoint.

Retreinar depois de mudar o dataset:
```bash
python data/build_seed_dataset.py   # regenera o CSV, se voce mudou as excecoes
python train_model.py               # retreina e salva o modelo
```

### Limitacoes honestas deste sistema (leia antes de confiar nos numeros)

- **O dataset "semente" nao e literatura minerada.** O roadmap original do
  projeto propunha minerar o acervo Alice/Infoteca-e da Embrapa (via
  OAI-PMH) pra construir um dataset rotulado com casos testados em campo.
  Isso exigiria acesso a rede e um pipeline de NLP fora do escopo de tempo
  desta etapa. Em vez disso, `data/build_seed_dataset.py` monta o CSV a mao a
  partir de conhecimento hortícola amplamente documentado (manuais de
  fruticultura/viticultura/cafeicultura, praticas comerciais consolidadas).
  Isso deixa o **pipeline** (features -> modelo -> integracao com a API)
  real e testavel de ponta a ponta, mas o dataset em si e pequeno (140
  pares) e nao passou por validacao de campo formal.
- **As metricas de validacao cruzada sao otimistas.** Varias linhas do
  dataset compartilham exatamente as mesmas features categoricas (todo par
  dentro do genero *Citrus* sem excecao documentada, por exemplo, vira o
  mesmo vetor de entrada). Isso faz o MAE e o recall/precision/F1
  parecerem melhores do que realmente medem generalizacao -- o modelo as
  vezes so esta reconhecendo um padrao que ja viu em uma linha "irma" no
  outro fold, nao aprendendo algo que valeria pra um par de especies
  totalmente novo. `app/ml_model_meta.json` guarda esse aviso
  explicitamente (`aviso_mae`) junto com os numeros, pra nao ficar
  escondido.
- **Por isso o modo `auto` e o recomendado**, nao `ml` puro: o sistema so
  usa a predicao do modelo quando a floresta esta "de acordo consigo mesma"
  sobre aquele par especifico (geralmente pares parecidos com uma das
  excecoes documentadas no treino); no resto dos casos, cai pras regras
  taxonomicas, que sao mais conservadoras mas nao dependem da qualidade do
  dataset de treino.
- **Proximo passo real** (nao feito nesta versao): substituir
  `data/compatibilidade_seed.csv` por um dataset maior, gerado a partir de
  uma mineracao de fato da literatura (ou de dados de campo do grupo/
  orientador), mantendo o mesmo formato de colunas -- o resto do pipeline
  (`train_model.py`, `app/ml_service.py`, `hybrid_score()`) ja funciona sem
  mudanca nenhuma com um CSV maior e mais confiavel.

## Banco de combinacoes (consulta automatica)

Objetivo do grupo: **automatizar a consulta** "estas duas plantas sao
compativeis na enxertia?". O sistema consulta, nesta ordem (`motor=auto`):

1. **Banco de combinacoes** (`app/db.py`, SQLite em `data/enxertia.db`) --
   registros conhecidos. `source: "banco"` na resposta.
2. **Modelo de ML** -- estimativa, quando o par nao esta no banco.
3. **Regras taxonomicas** -- estimativa final de seguranca.

Cada registro e uma afirmacao sobre um par, com o **tipo de evidencia**:

| tipo | significa | exige |
|---|---|---|
| `citada` | tem fonte (artigo, manual, livro) | campo `fonte` |
| `conhecimento_geral` | pratica conhecida, sem citacao formal | -- |
| `relato_nao_verificado` | ouvido/lido, sem confirmacao | -- |

A resposta de `/compatibilidade` repete a evidencia e a fonte, entao quem
le o resultado sabe o quanto confiar nele. Cadastro e consulta pela pagina
**Banco de combinacoes** do hub (ou pela API).

**O que tem no banco hoje:** apenas as 15 excecoes curadas em
`data/build_seed_dataset.py`, todas como `conhecimento_geral` e **sem
fonte** -- sao conhecimento geral meu, nao citacoes. Precisam ser
verificadas e, quando o grupo achar a fonte, substituidas por registros
`citada`. As ~125 linhas restantes do dataset de treino do ML NAO entram no
banco: foram geradas pela regra taxonomica, nao sao observacoes. O banco so
guarda afirmacoes sobre pares especificos; o que nao esta nele e estimado, e
a resposta diz isso.

Para mudar o local do arquivo: `ENXERTIA_DB=/caminho/enxertia.db`. Para
recomecar do zero, apague `data/enxertia.db` (ele e recriado e semeado no
proximo start).

## Evidencias da literatura (fontes abertas)

O projeto traz 53 registros extraidos de 5 fontes abertas (2 da Embrapa Mandioca e Fruticultura sobre citros, 1 da Embrapa Hortalicas sobre tomate em Solanum, 1 revisao sobre pera e marmeleiro e 1 estudo sobre porta-enxertos de melancia). Cada registro tem a fonte, o link e o trecho que sustenta a afirmacao.

- Arquivos: `data/literatura_enxertia.csv` (registros) e `data/literatura_fontes.csv` (referencias). O servidor carrega os dois ao subir; para recarregar sem reiniciar, rode `python data/importar_literatura.py`.
- **Ninguem conferiu ainda os trechos contra os PDFs.** A extracao foi automatica. Todo registro entra com `conferido = 0` e aparece como "a conferir" na interface. Depois de achar o trecho no PDF, escreva `sim` na coluna `conferido` e recarregue.
- **Contexto, nao score.** Em `/compatibilidade`, os campos `literatura` e `literatura_total` listam os registros que tocam o par, respeitando a orientacao (porta-enxerto com porta-enxerto, copa com copa). `correspondencia = "especie"` quando as duas pontas casam pela especie; `"genero"` quando a fonte tratou de outra cultivar, hibrido ou especie do mesmo genero, o que e pista e nao resposta.
- **Banco de combinacoes.** So 5 registros de nivel especie, em que a fonte afirma compatibilidade ou incompatibilidade em palavras, entram no banco que responde primeiro. O indice (0,9 compativel / 0,1 incompativel) e convencao do projeto, igual ao formulario do banco. Entram como `relato_nao_verificado`, viram `citada` quando conferidos e sao direcionais. Se alguem apagar um deles, ele nao volta sozinho; um par cadastrado a mao nunca e sobrescrito.
- Os nomes cientificos de `copa_taxon` e `porta_taxon` sao mapeamento do projeto, nao vem das fontes. Hibridos de citros (citrumelo, citrange, citrandarin) aparecem como `Citrus;Poncirus`, isto e, por genero.
- Endpoint: `GET /literatura?q=&cultura=`. A pagina Banco de combinacoes mostra a tabela.

## Plantas cadastradas pelo usuario

A pagina **Plantas** (`plantas.html`) lista as especies locais e deixa cadastrar plantas proprias. Elas entram nos seletores de Consultar e Recomendar e sao resolvidas sem internet.

- Endpoints: `GET /especies` (cada item traz `origem`: `base` ou `usuario`), `POST /especies` e `DELETE /especies/{nome}` (so remove as do usuario).
- Ficam na tabela `especies_usuario` de `data/enxertia.db`. A lista do projeto (`app/taxonomy_fallback.json`) nao e alterada.
- Validacoes: nome no formato "Genero especie" (cultivar opcional entre parenteses), genero igual a primeira palavra do nome e familia terminada em "-aceae" (ou um dos oito nomes alternativos do codigo botanico). Familia e genero vazios podem ser preenchidos pela GBIF, quando ela responde.
- As fontes locais sao modulares (`app/especies.py`): qualquer classe com `listar()` e `buscar(nome)` pode entrar em `TaxonomyService(fontes_locais=[...])`, por exemplo para ler um CSV.
- O modelo de ML nao e retreinado com as plantas novas: para elas, o indice vem do banco de combinacoes (se houver registro) ou das regras e do modelo pelo genero e pela familia.

## Banco local de especies

`app/taxonomy_fallback.json` cobre ~77 especies com relevancia real para
enxertia (arvores frutiferas, videira, cafe, cacau, hortalicas solanaceas/
cucurbitaceas comumente enxertadas), escolhidas pra cobrir as culturas mais
comuns no Brasil. Culturas propagadas por semente/rizoma/estaca (milho,
soja, arroz, feijao, mandioca, cana, banana, abacaxi, mamao, algodao) foram
deixadas de fora de proposito, porque nao se enxertam na pratica -- inclui-
las so diluiria o banco sem valor real pro problema.

## Resolucao de taxonomia (API real no nucleo do sistema)

`TaxonomyService.resolve()` tenta, nessa ordem:

1. **GBIF Species API** (`app/clients/gbif.py`) -- publica, sem chave,
   schema confirmado manualmente (`GET https://api.gbif.org/v1/species/
   match?name=...&kingdom=Plantae`). Essa e a fonte primaria e a API
   externa de verdade que o nucleo do sistema (ranking/compatibilidade)
   usa -- nao e um recurso isolado, ela alimenta toda consulta de
   taxonomia.
2. **Reflora/JBRJ** (`app/clients/reflora.py`) -- tentado em seguida,
   best-effort. Ver limitacao abaixo -- provavelmente nunca retorna nada,
   porque o JBRJ nao parece expor o tipo de endpoint que esse cliente
   assume.
3. **Banco local** (`fallback_local`) -- usado so quando nem GBIF nem
   Reflora respondem (sem internet, GBIF fora do ar, nome nao reconhecido).

O campo `source` de `TaxonomyInfo` sempre diz qual das tres resolveu cada
consulta especifica.

### O Reflora/JBRJ nao parece ter uma API REST de busca por nome

Pesquisei bastante tentando confirmar o endpoint (ver `app/clients/
reflora.py` pra detalhes completos). O que encontrei: o JBRJ nao distribui
os dados da Flora e Funga do Brasil como uma API de consulta por taxon --
eles publicam um arquivo **Darwin Core Archive em lote** via
`ipt.jbrj.gov.br` (o sistema de publicacao de dados do GBIF), pensado pra
ser baixado inteiro, nao consultado especie por especie. Confirmei isso
olhando como o pacote R `floraR` (feito especificamente pra acessar esses
dados) funciona: ele baixa o arquivo completo, nao faz uma chamada HTTP por
nome cientifico.

**Isso nao significa que o projeto ficou sem Reflora.** A resposta que a
GBIF devolve pra especies deste projeto (conferi manualmente pra *Prunus
persica*) cita o "Brazil Flora Group / REFLORA Program" entre as fontes do
dataset de origem -- a GBIF agrega varios checklists nacionais, incluindo
dados que passam pelo proprio programa REFLORA. Ou seja: o sistema se
beneficia de dados do REFLORA de forma indireta/agregada atraves da GBIF,
nao por uma chamada direta e isolada a `servicos.jbrj.gov.br`. E uma
diferenca importante de deixar clara numa apresentacao: nao e "integracao
direta com a API do Reflora", e "resolucao de taxonomia via GBIF, que
agrega (entre outras fontes) dados do programa REFLORA/JBRJ".

### Usando especies fora do banco local

O banco local (~77 especies) alimenta so as **listas de selecao** da
interface. Qualquer outra especie funciona digitando o nome cientifico no
campo "ou digite outro nome" (paginas Recomendar e Compatibilidade, ou
`?especie=` / `?porta_enxerto=` na API): o nome e resolvido pela GBIF. Dois
detalhes:

- O **ranking sem candidatas** ("melhores combinacoes") sempre compara
  contra as ~77 especies do banco local. Pra comparar com outras, use o
  campo "Candidatas especificas".
- Se a GBIF nao responder (internet, proxy, firewall, antivirus
  interceptando HTTPS), o hub mostra o **motivo** logo abaixo de "GBIF
  indisponivel" (campo `gbif_erro` de `/status`). Teste direto no
  navegador: `http://127.0.0.1:8000/taxonomia/Vaccinium corymbosum` -- se
  voltar `"source": "gbif"`, esta funcionando.

## Outras limitacoes conhecidas
- **Ambiente de desenvolvimento usado pra gerar este projeto**: o sandbox
  onde este codigo foi escrito bloqueia chamadas de rede de saida
  arbitrarias (so permite registries de pacotes e GitHub), entao o cliente
  GBIF foi validado contra a API real via busca manual (o schema acima e
  uma copia literal de uma resposta real), mas as chamadas HTTP em si so
  foram testadas com mocks (`test_gbif_client.py`), nao com uma chamada de
  ponta a ponta naquele ambiente. Na sua maquina, com internet normal, isso
  deve funcionar direto -- mas vale conferir rodando `/status` ou uma
  consulta de `/taxonomia/{nome}` e olhando o campo `source` da resposta.

## Testes

```bash
pytest
```

Cobre o motor de regras, o ranking, o banco de combinacoes, a integracao
com o motor de ML (com fallback seguro quando o modelo nao esta treinado
ainda) e o cliente GBIF (mockado, sem depender de rede).
