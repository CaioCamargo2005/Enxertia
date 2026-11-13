// Catalogo Enxert.DB: le /catalogo/resumo e /catalogo/combinacoes (somente leitura).

const CLASSE_STATUS = {
  'Compatível': 'pill--alta',
  'Incompatibilidade Localizada': 'pill--incerta',
  'Incompatibilidade Translocada': 'pill--improvavel',
  'Incompatível': 'pill--improvavel',
};

function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined && texto !== null) e.textContent = texto;
  return e;
}

function stat(valor, rotulo, destaque) {
  const box = el('div', `stat${destaque ? ' stat--destaque' : ''}`);
  box.appendChild(el('div', 'stat__valor', String(valor)));
  box.appendChild(el('div', 'stat__rotulo', rotulo));
  return box;
}

async function carregarResumo() {
  const area = document.getElementById('stats');
  try {
    const resp = await fetch('/catalogo/resumo');
    const r = await resp.json();
    if (!resp.ok) throw new Error(r.detail || `Erro ${resp.status}`);
    area.innerHTML = '';
    area.appendChild(stat(r.plantas, 'plantas no catálogo'));
    area.appendChild(stat(r.combinacoes, 'combinações'));
    area.appendChild(stat(r.da_literatura, `da literatura (${r.fontes} fontes)`, true));
    area.appendChild(stat(`${r.conferidas}/${r.da_literatura}`, 'conferidas no PDF'));
  } catch (err) {
    area.innerHTML = '';
  }
}

function cartao(c) {
  const card = el('article', 'cat-card');
  if (c.id_fonte) card.classList.add('cat-card--lit');

  const topo = el('div', 'cat-card__topo');
  const nomes = el('div');
  nomes.appendChild(el('div', 'cat-card__copa', c.copa));
  const sobre = el('div', 'cat-card__sobre');
  sobre.appendChild(document.createTextNode('sobre '));
  sobre.appendChild(el('strong', null, c.porta_enxerto));
  nomes.appendChild(sobre);
  nomes.appendChild(el('div', 'cat-card__cient', `${c.copa_cientifico} · ${c.porta_cientifico}`));
  topo.appendChild(nomes);
  topo.appendChild(el('span', `pill ${CLASSE_STATUS[c.status] || 'pill--quiet'}`, c.status || 'não classificado'));
  card.appendChild(topo);

  if (c.taxa_pegamento !== null && c.taxa_pegamento !== undefined) {
    const barra = el('div', 'taxa');
    const trilho = el('div', 'taxa__trilho');
    const cheio = el('div', 'taxa__cheio');
    cheio.style.width = `${Math.max(0, Math.min(100, c.taxa_pegamento))}%`;
    trilho.appendChild(cheio);
    barra.appendChild(trilho);
    barra.appendChild(el('span', 'taxa__valor', `${c.taxa_pegamento}% de pegamento`));
    card.appendChild(barra);
  }

  const meta = el('div', 'cat-card__meta');
  if (c.metodo) meta.appendChild(el('span', 'lit__tag', c.metodo));
  if (c.id_fonte) {
    meta.appendChild(el('span', c.conferido ? 'lit__tag lit__tag--ok' : 'lit__tag lit__tag--pendente',
      c.conferido ? 'conferido no PDF' : 'a conferir no PDF'));
  } else {
    meta.appendChild(el('span', 'lit__tag lit__tag--forte', 'registro da equipe'));
  }
  card.appendChild(meta);

  if (c.observacoes) card.appendChild(el('p', 'cat-card__obs', c.observacoes));
  if (c.resistencia_solo || c.tolerancia || c.vigor) {
    const partes = [c.resistencia_solo, c.tolerancia, c.vigor].filter((t) => t && t !== 'N/A');
    if (partes.length) card.appendChild(el('p', 'cat-card__resist', `Porta-enxerto: ${partes.join(' · ')}`));
  }

  if (c.id_fonte) {
    const fonte = el('div', 'lit__fonte');
    const ref = c.fonte_referencia || '';
    const curta = ref.length > 95 ? ref.slice(0, ref.lastIndexOf(' ', 92)) + '…' : ref;
    fonte.title = ref;
    fonte.appendChild(document.createTextNode(`Fonte: ${curta} `));
    if (c.fonte_url && /^https?:\/\//.test(c.fonte_url)) {
      const a = el('a', null, 'abrir a fonte');
      a.href = c.fonte_url; a.target = '_blank'; a.rel = 'noopener';
      fonte.appendChild(a);
    }
    card.appendChild(fonte);
    if (c.trecho) card.appendChild(el('div', 'lit__ressalva', `Trecho: "${c.trecho}"`));
  }
  return card;
}

async function carregar() {
  const lista = document.getElementById('lista');
  const erro = document.getElementById('erro');
  erro.hidden = true;
  const params = new URLSearchParams();
  const q = document.getElementById('busca').value.trim();
  const status = document.getElementById('filtro-status').value;
  const origem = document.getElementById('filtro-origem').value;
  if (q) params.set('q', q);
  if (status) params.set('status', status);
  if (origem) params.set('origem', origem);
  history.replaceState(null, '', `${location.pathname}${params.toString() ? '?' + params : ''}`);

  try {
    const resp = await fetch(`/catalogo/combinacoes?${params}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.detail || `Erro ${resp.status}`);
    lista.innerHTML = '';
    document.getElementById('contagem').textContent = `${dados.length} combinação(ões)`;
    if (!dados.length) {
      lista.appendChild(el('p', 'picker__empty', 'Nenhuma combinação com esses filtros.'));
      return;
    }
    for (const c of dados) lista.appendChild(cartao(c));
  } catch (err) {
    lista.innerHTML = '';
    document.getElementById('contagem').textContent = '';
    erro.textContent = `Não foi possível ler o catálogo Enxert.DB: ${err.message}`;
    erro.hidden = false;
  }
}

let espera = null;
document.getElementById('busca').addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(carregar, 250); });
document.getElementById('filtro-status').addEventListener('change', carregar);
document.getElementById('filtro-origem').addEventListener('change', carregar);

const inicial = new URLSearchParams(location.search);
if (inicial.get('q')) document.getElementById('busca').value = inicial.get('q');
if (inicial.get('status')) document.getElementById('filtro-status').value = inicial.get('status');
if (inicial.get('origem')) document.getElementById('filtro-origem').value = inicial.get('origem');
carregarResumo();
carregar();
