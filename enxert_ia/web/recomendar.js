// Ranking de melhores combinacoes de enxertia para
// uma especie de referencia -- contra todo o banco, ou contra uma lista de
// candidatas especificas que o usuario digita.

let SPECIES = [];
let especieSelecionada = null;
let pickerEspecie = null;

function renderRanking(data) {
  const area = document.getElementById('recomendacoes-area');
  area.innerHTML = '';

  if (data.candidatas_nao_encontradas && data.candidatas_nao_encontradas.length) {
    const aviso = document.createElement('p');
    aviso.className = 'hint';
    aviso.textContent = `Nao encontradas no banco (ignoradas): ${data.candidatas_nao_encontradas.join(', ')}`;
    area.appendChild(aviso);
  }

  if (!data.recomendacoes.length) {
    const vazio = document.createElement('p');
    vazio.className = 'picker__empty';
    vazio.textContent = 'Nenhuma candidata encontrada para comparar.';
    area.appendChild(vazio);
    return;
  }

  const titulo = document.createElement('h2');
  titulo.textContent = `Melhores combinacoes para ${data.especie}`;
  area.appendChild(titulo);

  const lista = document.createElement('ul');
  lista.className = 'ranking';
  for (const item of data.recomendacoes) {
    const outra = item.rootstock.toLowerCase() === data.especie.toLowerCase() ? item.scion : item.rootstock;
    const taxOutra = item.rootstock.toLowerCase() === data.especie.toLowerCase()
      ? item.scion_taxonomy : item.rootstock_taxonomy;

    const li = document.createElement('li');
    li.className = 'ranking__item';

    const nomeDiv = document.createElement('div');
    const nome = document.createElement('span');
    nome.className = 'ranking__name';
    nome.textContent = outra;
    nomeDiv.appendChild(nome);
    if (taxOutra && taxOutra.common_name) {
      const comum = document.createElement('span');
      comum.className = 'ranking__common';
      comum.textContent = `${taxOutra.common_name} -- ${item.justification}`;
      nomeDiv.appendChild(comum);
    } else {
      const just = document.createElement('span');
      just.className = 'ranking__common';
      just.textContent = item.justification;
      nomeDiv.appendChild(just);
    }
    li.appendChild(nomeDiv);

    const lado = document.createElement('div');
    lado.className = 'ranking__lado';
    const score = document.createElement('span');
    score.className = `ranking__score level-${item.level}`;
    score.textContent = `${Math.round(item.score * 100)}% · ${item.level}`;
    lado.appendChild(score);
    const ver = document.createElement('a');
    ver.className = 'ranking__ver';
    ver.href = `compatibilidade.html?${new URLSearchParams({ porta: item.rootstock, enxerto: item.scion })}`;
    ver.textContent = 'ver detalhes';
    lado.appendChild(ver);
    li.appendChild(lado);

    lista.appendChild(li);
  }
  area.appendChild(lista);
}

async function verRecomendacoes() {
  const errorMsg = document.getElementById('error-msg');
  errorMsg.hidden = true;
  document.getElementById('recomendacoes-area').innerHTML = '';

  const params = new URLSearchParams({ especie: especieSelecionada.scientific_name, limite: '15' });
  const candidatasTexto = document.getElementById('candidatas-input').value.trim();
  if (candidatasTexto) params.set('candidatos', candidatasTexto);

  const url = new URLSearchParams({ especie: especieSelecionada.scientific_name });
  if (candidatasTexto) url.set('candidatos', candidatasTexto);
  history.replaceState(null, '', `${location.pathname}?${url}`);

  await comCarregamento(document.getElementById('btn-recomendar'), 'Calculando...', async () => {
    try {
      const resp = await fetch(`/recomendacoes?${params}`);
      if (resp.status === 404) throw new Error('especie nao encontrada: nao esta no banco local e a GBIF nao respondeu ou nao reconheceu o nome');
      if (!resp.ok) throw new Error(`Erro ${resp.status}`);
      renderRanking(await resp.json());
    } catch (err) {
      errorMsg.textContent = `Nao foi possivel obter recomendacoes (${err.message}).`;
      errorMsg.hidden = false;
    }
  });
}

async function init() {
  const resp = await fetch('/especies');
  SPECIES = await resp.json();
  const botao = document.getElementById('btn-recomendar');

  pickerEspecie = criarPicker({
    raizId: 'picker-especie', inputId: 'especie-input', painelId: 'panel-especie',
    especies: () => SPECIES,
    aoSelecionar: (sp) => {
      especieSelecionada = sp;
      document.getElementById('especie-livre').value = '';
      botao.disabled = false;
    },
    aoLimpar: () => {
      if (!document.getElementById('especie-livre').value.trim()) { especieSelecionada = null; botao.disabled = true; }
    },
  });

  document.getElementById('especie-livre').addEventListener('input', (ev) => {
    const nome = ev.target.value.trim();
    especieSelecionada = nome ? { scientific_name: nome } : null;
    if (nome) pickerEspecie.limpar();
    botao.disabled = !nome;
  });
  document.getElementById('especie-livre').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !botao.disabled) verRecomendacoes();
  });

  botao.addEventListener('click', verRecomendacoes);

  // Ranking vindo de um link compartilhado (?especie=...&candidatos=...).
  const url = new URLSearchParams(location.search);
  if (url.get('especie')) {
    const nome = url.get('especie');
    const sp = acharEspecie(SPECIES, nome);
    if (sp) { especieSelecionada = sp; pickerEspecie.selecionar(sp, { silencioso: true }); }
    else { especieSelecionada = { scientific_name: nome }; document.getElementById('especie-livre').value = nome; }
    if (url.get('candidatos')) document.getElementById('candidatas-input').value = url.get('candidatos');
    botao.disabled = false;
    verRecomendacoes();
  }
}

init();
