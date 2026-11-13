// Pagina de compatibilidade par a par.
// - seletores com busca por nome popular ou cientifico (picker.js);
// - botao para trocar porta-enxerto e copa;
// - a consulta fica na URL (?porta=...&enxerto=...), entao o link pode ser compartilhado.

let SPECIES = [];
const selecionado = { porta: null, enxerto: null };
const pickers = {};

const ROTULO_SOURCE = { banco: 'banco de combinacoes', ml: 'modelo de ML', regras: 'regras taxonomicas' };
const ROTULO_NIVEL = { alta: 'alta', provavel: 'provavel', incerta: 'incerta', improvavel: 'improvavel', desconhecida: 'desconhecida' };

function atualizarBotao() {
  document.getElementById('btn-consultar').disabled = !(selecionado.porta && selecionado.enxerto);
}

function definirLado(chave, nome, { silencioso = true } = {}) {
  const sp = acharEspecie(SPECIES, nome);
  if (sp) {
    selecionado[chave] = sp;
    pickers[chave].selecionar(sp, { silencioso });
    document.getElementById(`${chave}-livre`).value = '';
  } else {
    selecionado[chave] = nome ? { scientific_name: nome } : null;
    pickers[chave].limpar();
    document.getElementById(`${chave}-livre`).value = nome || '';
  }
}

function linkDaConsulta() {
  const params = new URLSearchParams({ porta: selecionado.porta.scientific_name, enxerto: selecionado.enxerto.scientific_name });
  return `${location.origin}${location.pathname}?${params}`;
}

function marca(texto, classe) {
  const tag = document.createElement('span');
  tag.className = classe;
  tag.textContent = texto;
  return tag;
}

// Evidencias da literatura que tocam o par consultado (contexto; nao entram no score).
function renderLiteratura(data) {
  const area = document.getElementById('literatura');
  const lista = document.getElementById('lit-lista');
  const mais = document.getElementById('lit-mais');
  lista.innerHTML = '';
  const regs = data.literatura || [];
  if (!regs.length) { area.hidden = true; return; }

  const total = data.literatura_total;
  document.getElementById('lit-titulo').textContent =
    `Na literatura: ${total} registro${total === 1 ? '' : 's'} relacionado${total === 1 ? '' : 's'}`;
  document.getElementById('lit-aviso').textContent =
    'Contexto: nao entra no indice. "Mesmo genero" quer dizer que a fonte tratou de outra cultivar, hibrido ou especie do mesmo genero; e uma pista, nao a resposta para este par.';

  for (const r of regs) {
    const li = document.createElement('li');
    const titulo = document.createElement('div');
    titulo.className = 'lit__titulo';
    const par = document.createElement('strong');
    par.textContent = `${r.copa} sobre ${r.porta_enxerto}`;
    titulo.appendChild(par);
    li.appendChild(titulo);

    const afirmacao = document.createElement('p');
    afirmacao.className = 'lit__afirmacao';
    afirmacao.textContent = `${r.afirmacao}${r.medida ? ' · ' + r.medida : ''}`;
    li.appendChild(afirmacao);

    const marcas = document.createElement('div');
    marcas.className = 'lit__marcas';
    marcas.appendChild(marca(r.correspondencia === 'especie' ? 'mesma especie' : 'mesmo genero',
      r.correspondencia === 'especie' ? 'lit__tag lit__tag--forte' : 'lit__tag'));
    marcas.appendChild(marca(r.conferido ? 'conferido no PDF' : 'a conferir no PDF',
      r.conferido ? 'lit__tag lit__tag--ok' : 'lit__tag lit__tag--pendente'));
    marcas.appendChild(marca(r.tipo_dado, 'lit__tag'));
    li.appendChild(marcas);

    const fonte = document.createElement('div');
    fonte.className = 'lit__fonte';
    fonte.appendChild(document.createTextNode(`${r.fonte_referencia} `));
    if (r.fonte_url && /^https?:\/\//.test(r.fonte_url)) {
      const a = document.createElement('a');
      a.href = r.fonte_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'abrir a fonte';
      fonte.appendChild(a);
    }
    li.appendChild(fonte);
    if (r.ressalva) {
      const nota = document.createElement('div');
      nota.className = 'lit__ressalva';
      nota.textContent = `Ressalva: ${r.ressalva}`;
      li.appendChild(nota);
    }
    lista.appendChild(li);
  }

  const generoPorta = (data.rootstock_taxonomy?.genus || data.rootstock || '').split(' ')[0];
  mais.href = `banco.html?q=${encodeURIComponent(generoPorta)}`;
  mais.textContent = total > regs.length
    ? `Ver os ${total} registros no Banco de combinacoes →`
    : 'Abrir no Banco de combinacoes →';
  mais.hidden = false;
  area.hidden = false;
}

async function consultarCompatibilidade() {
  const errorMsg = document.getElementById('error-msg');
  const result = document.getElementById('result');
  errorMsg.hidden = true;
  result.hidden = true;
  document.getElementById('literatura').hidden = true;

  const params = new URLSearchParams({
    porta_enxerto: selecionado.porta.scientific_name,
    enxerto: selecionado.enxerto.scientific_name,
  });
  history.replaceState(null, '', linkDaConsulta());

  const botao = document.getElementById('btn-consultar');
  await comCarregamento(botao, 'Consultando...', async () => {
    try {
      const resp = await fetch(`/compatibilidade?${params}`);
      if (!resp.ok) throw new Error(`Erro ${resp.status}`);
      const data = await resp.json();

      if (data.level === 'desconhecida') {
        errorMsg.textContent = 'Nao foi possivel resolver a taxonomia de uma das especies: o nome nao esta no banco local e a GBIF nao respondeu ou nao reconheceu o nome. Veja o status da GBIF na pagina inicial.';
        errorMsg.hidden = false;
        return;
      }
      document.getElementById('result-par').textContent = `${data.scion} sobre ${data.rootstock}`;
      const score = document.getElementById('result-score');
      score.textContent = `${Math.round(data.score * 100)}%`;
      score.className = `result__score level-${data.level}`;
      const nivel = document.getElementById('result-level');
      nivel.textContent = `compatibilidade ${ROTULO_NIVEL[data.level] || data.level}`;
      nivel.className = `pill pill--${data.level}`;
      document.getElementById('result-source').textContent = `respondido por: ${ROTULO_SOURCE[data.source] || data.source}`;
      document.getElementById('result-justification').textContent = data.justification;
      document.getElementById('result-meta').textContent =
        `${data.rootstock_taxonomy?.family || '?'} · taxonomia: porta-enxerto via ${data.rootstock_taxonomy?.source || '?'}, copa via ${data.scion_taxonomy?.source || '?'}`;
      result.hidden = false;
      renderLiteratura(data);
    } catch (err) {
      errorMsg.textContent = `Nao foi possivel consultar a compatibilidade (${err.message}).`;
      errorMsg.hidden = false;
    }
  });
  atualizarBotao();
}

async function init() {
  const resp = await fetch('/especies');
  SPECIES = await resp.json();

  for (const chave of ['porta', 'enxerto']) {
    pickers[chave] = criarPicker({
      raizId: `picker-${chave}`, inputId: `${chave}-input`, painelId: `panel-${chave}`,
      especies: () => SPECIES,
      aoSelecionar: (sp) => {
        selecionado[chave] = sp;
        document.getElementById(`${chave}-livre`).value = '';
        atualizarBotao();
      },
      aoLimpar: () => {
        if (!document.getElementById(`${chave}-livre`).value.trim()) selecionado[chave] = null;
        atualizarBotao();
      },
    });
    document.getElementById(`${chave}-livre`).addEventListener('input', (ev) => {
      const nome = ev.target.value.trim();
      selecionado[chave] = nome ? { scientific_name: nome } : null;
      if (nome) pickers[chave].limpar();
      atualizarBotao();
    });
    document.getElementById(`${chave}-livre`).addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !document.getElementById('btn-consultar').disabled) consultarCompatibilidade();
    });
  }

  document.getElementById('btn-trocar').addEventListener('click', () => {
    const porta = selecionado.porta?.scientific_name || '';
    const enxerto = selecionado.enxerto?.scientific_name || '';
    definirLado('porta', enxerto);
    definirLado('enxerto', porta);
    atualizarBotao();
    if (!document.getElementById('result').hidden && selecionado.porta && selecionado.enxerto) consultarCompatibilidade();
  });

  document.getElementById('btn-copiar').addEventListener('click', async (ev) => {
    const botao = ev.currentTarget;
    try {
      await navigator.clipboard.writeText(linkDaConsulta());
      botao.textContent = 'Link copiado';
    } catch {
      botao.textContent = 'Copie o endereco da barra do navegador';
    }
    setTimeout(() => { botao.textContent = 'Copiar link desta consulta'; }, 2200);
  });

  document.getElementById('btn-consultar').addEventListener('click', consultarCompatibilidade);

  // Consulta vinda de um link compartilhado ou do ranking de recomendacoes.
  const url = new URLSearchParams(location.search);
  if (url.get('porta') && url.get('enxerto')) {
    definirLado('porta', url.get('porta'));
    definirLado('enxerto', url.get('enxerto'));
    atualizarBotao();
    consultarCompatibilidade();
  }
}

init();
