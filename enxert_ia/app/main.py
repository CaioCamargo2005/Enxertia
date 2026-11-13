import os
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.clients.gbif import GBIFClient
from app.taxonomy_service import TaxonomyService
from app.compatibility import hybrid_score, rank_candidates
from app.models import CompatibilityResult, TaxonomyInfo, NovaCombinacao, NovaEspecie
from app import especies
from app import db, literatura, catalogo
from app.ml_service import ml_service

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Abre o hub no navegador assim que o servidor sobe, pra nao precisar
    digitar a URL na mao. Desative com ENXERTIA_NO_AUTOOPEN=1 no .env (util
    se voce roda com --reload e nao quer uma aba nova a cada hot-reload).
    Host/porta customizados: defina ENXERTIA_HOST / ENXERTIA_PORT no .env
    se voce rodar o uvicorn com --host ou --port diferentes do padrao.
    """
    try:
        db.init_db(seed=True)  # cria o banco de combinacoes e cadastra o seed se estiver vazio
        literatura.importar_se_possivel()  # carrega/atualiza as evidencias da literatura (CSV em data/)
    except Exception:
        pass  # o banco e opcional pro resto do sistema; nunca derruba o servidor
    if not (os.getenv("ENXERTIA_NO_AUTOOPEN") or os.getenv("PYTEST_CURRENT_TEST")):
        host = os.getenv("ENXERTIA_HOST", "127.0.0.1")
        port = os.getenv("ENXERTIA_PORT", "8000")
        url = f"http://{host}:{port}/"
        threading.Timer(1.0, lambda: webbrowser.open_new_tab(url)).start()
    yield


app = FastAPI(
    title="Enxert.IA - Compatibilidade de Enxertia",
    description="Banco de combinacoes de enxertia consultavel automaticamente, com estimativa "
                "por ML e regras taxonomicas (GBIF, com fallback local) quando o par nao esta no banco.",
    version="1.0.0",
    lifespan=lifespan,
)

taxonomy_service = TaxonomyService()

# Cliente GBIF dedicado pra checagem ao vivo no /status, com timeout curto
# (3s) -- diferente do taxonomy_service.resolve(), que tem a cadeia inteira
# de fallback (GBIF -> Reflora -> local) e pode demorar mais se a rede
# estiver ruim. Aqui queremos uma resposta rapida sobre "a API externa esta
# respondendo agora?", nao a resolucao completa de uma especie.
_gbif_status_client = GBIFClient(timeout=3)


def _resumo_catalogo_ou_none():
    try:
        return catalogo.resumo()
    except Exception:
        return None


@app.get("/status")
def status():
    """
    O campo `gbif_respondendo_agora` faz uma chamada de verdade pra GBIF
    (consultando "Citrus sinensis", que sabemos que existe) e reporta se ela
    respondeu com sucesso. Isso existe porque o hub (web/index.html) so
    mostrava "servidor ok" antes, sem nenhuma confirmacao visivel de que a
    API externa de taxonomia estava realmente sendo usada -- esse campo
    corrige isso.
    """
    diagnostico_gbif = _gbif_status_client.diagnosticar("Citrus sinensis")
    return {
        "status": "ok",
        "especies_no_banco": len(taxonomy_service.list_fallback_species()),
        "endpoints": ["/recomendacoes", "/compatibilidade", "/banco/combinacoes", "/literatura", "/catalogo/combinacoes", "/especies", "/taxonomia/{nome_cientifico}", "/especies"],
        "gbif_respondendo_agora": diagnostico_gbif["ok"],
        "gbif_erro": diagnostico_gbif["erro"],
        "combinacoes_no_banco": db.contar(),
        "evidencias_literatura": literatura.contar(),
        "catalogo_enxert_db": _resumo_catalogo_ou_none(),
        "modelo_ml_disponivel": ml_service.is_available(),
        "modelo_ml_metadados": ml_service.metadata(),
    }


@app.get("/banco/combinacoes")
def listar_combinacoes(q: str = None, limite: int = 500):
    """Lista os registros do banco de combinacoes (filtra por especie, fonte ou observacao com `q`)."""
    return db.listar(q, limite)


@app.post("/banco/combinacoes", status_code=201)
def criar_combinacao(nova: NovaCombinacao):
    """Cadastra uma combinacao. Evidencia 'citada' exige `fonte`."""
    try:
        return db.inserir(**nova.model_dump())
    except db.RegistroDuplicado as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except db.RegistroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/literatura")
def listar_literatura(q: str = None, cultura: str = None, limite: int = 500):
    """Evidencias extraidas de artigos e boletins abertos (cada uma com fonte e link).
    `conferido` = 0 significa que o trecho ainda nao foi conferido contra o PDF."""
    return literatura.listar(q, cultura, limite)


def _catalogo(funcao, *args, **kwargs):
    try:
        return funcao(*args, **kwargs)
    except catalogo.CatalogoIndisponivel as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/catalogo/resumo")
def resumo_catalogo():
    """Contagens do catalogo Enxert.DB (plantas, combinacoes, registros da literatura)."""
    return _catalogo(catalogo.resumo)


@app.get("/catalogo/combinacoes")
def combinacoes_catalogo(q: str = None, status: str = None, origem: str = None, limite: int = 500):
    """Combinacoes do Enxert.DB com metodo, taxa de pegamento e fonte.
    `status`: um dos quatro status ou "sem_status"; `origem`: "equipe", "literatura" ou "a_conferir"."""
    return _catalogo(catalogo.combinacoes, q, status, origem, limite)


@app.get("/catalogo/plantas")
def plantas_catalogo():
    return _catalogo(catalogo.plantas)


@app.delete("/banco/combinacoes/{registro_id}")
def apagar_combinacao(registro_id: int):
    if not db.remover(registro_id):
        raise HTTPException(status_code=404, detail="Registro nao encontrado.")
    return {"removido": registro_id}


@app.get("/taxonomia/{nome_cientifico}", response_model=TaxonomyInfo)
def get_taxonomia(nome_cientifico: str):
    resultado = taxonomy_service.resolve(nome_cientifico)
    if not resultado:
        raise HTTPException(status_code=404, detail=f"Taxonomia nao encontrada para '{nome_cientifico}'.")
    return resultado


@app.get("/compatibilidade", response_model=CompatibilityResult)
def get_compatibilidade(porta_enxerto: str, enxerto: str, motor: str = "auto"):
    """
    `motor`: "auto" (padrao: banco de combinacoes -> modelo de ML -> regras),
    "regras" (forca o motor taxonomico classico) ou "ml" (ML -> regras, sem
    consultar o banco). Ver hybrid_score() em app/compatibility.py.
    """
    tax_porta = taxonomy_service.resolve(porta_enxerto)
    tax_enxerto = taxonomy_service.resolve(enxerto)
    resultado = hybrid_score(porta_enxerto, enxerto, tax_porta, tax_enxerto, motor=motor)
    try:
        achadas = literatura.relacionadas(tax_porta, tax_enxerto)
        resultado.literatura = achadas["registros"]
        resultado.literatura_total = achadas["total"]
    except Exception:
        pass  # a literatura e contexto: nunca derruba a consulta de compatibilidade
    return resultado


@app.get("/especies")
def listar_especies():
    """Lista as especies locais (as do projeto e as cadastradas pelo usuario), usada pelos seletores.
    Cada item traz `origem`: "base" ou "usuario"."""
    return taxonomy_service.list_fallback_species()


def _fonte_usuario() -> especies.FonteUsuario:
    for fonte in taxonomy_service.fontes_locais:
        if isinstance(fonte, especies.FonteUsuario):
            return fonte
    raise HTTPException(status_code=503, detail="Cadastro de plantas desativado nesta instalacao.")


@app.post("/especies", status_code=201)
def cadastrar_especie(nova: NovaEspecie):
    """Cadastra uma planta propria. Familia e genero vazios sao preenchidos pela GBIF quando
    `preencher_pelo_gbif` e verdadeiro e a GBIF responde; senao, precisam ser informados."""
    fonte = _fonte_usuario()
    nome = especies.normalizar_nome(nova.nome_cientifico)
    for outra in taxonomy_service.fontes_locais:
        if not isinstance(outra, especies.FonteUsuario) and outra.buscar(nome):
            raise HTTPException(status_code=409, detail=f"'{nome}' ja faz parte da lista do projeto.")
    familia, genero, preenchido = nova.familia, nova.genero, False
    if (not familia or not genero) and nova.preencher_pelo_gbif:
        dados = _gbif_status_client.get_taxonomy(nome.split(" (")[0])
        if dados:
            familia, genero, preenchido = familia or dados.get("family"), genero or dados.get("genus"), True
    try:
        criada = fonte.adicionar(nome, familia, genero, nova.nome_popular, nova.observacoes)
    except especies.EspecieDuplicada as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except especies.EspecieInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {**criada, "preenchido_pela_gbif": preenchido}


@app.delete("/especies/{nome_cientifico}")
def remover_especie(nome_cientifico: str):
    """Remove uma planta cadastrada pelo usuario. As especies que vem com o projeto nao podem ser removidas."""
    if not _fonte_usuario().remover(nome_cientifico):
        raise HTTPException(status_code=404,
                            detail="So plantas cadastradas por usuario podem ser removidas, e esta nao foi encontrada.")
    return {"removida": nome_cientifico}


@app.get("/recomendacoes")
def get_recomendacoes(especie: str, candidatos: str = None, limite: int = 10, motor: str = "auto"):
    """
    Dado uma especie, retorna as melhores combinacoes de enxertia disponiveis.

    - Sem `candidatos`: rankeia contra todo o dataset local (~77 especies),
      retornando as `limite` melhores.
    - Com `candidatos` (nomes separados por virgula): rankeia so entre essas
      opcoes especificas -- util pra comparar 2-3 candidatas que o usuario
      ja tem em mente.
    - `motor`: "auto" (padrao), "regras" ou "ml" -- ver /compatibilidade.
    """
    tax_alvo = taxonomy_service.resolve(especie)
    if not tax_alvo:
        raise HTTPException(status_code=404, detail=f"Taxonomia nao encontrada para '{especie}'.")

    if candidatos:
        nomes = [c.strip() for c in candidatos.split(",") if c.strip()]
        pool = [taxonomy_service.resolve(nome) for nome in nomes]
        nao_encontradas = [nomes[i] for i, p in enumerate(pool) if not p]
        pool = [p for p in pool if p]
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
        nao_encontradas = []

    ranking = rank_candidates(especie, tax_alvo, pool, motor=motor)

    return {
        "especie": especie,
        "taxonomia": tax_alvo,
        "recomendacoes": ranking[:limite],
        "candidatas_nao_encontradas": nao_encontradas,
    }


# Interface web (frontend estatico) -- montada por ultimo, na raiz, para que
# as rotas de API acima (mais especificas) sejam sempre resolvidas primeiro.
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")
