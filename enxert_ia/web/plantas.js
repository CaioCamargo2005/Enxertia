// Pagina Plantas: lista as especies locais e cadastra/remove as do usuario.

let TODAS = [];

const $ = (id) => document.getElementById(id);

function mostrar(id, texto) {
  const e = $(id);
  e.textContent = texto;
  e.hidden = !texto;
}

function td(texto, classe) {
  const c = document.createElement('td');
  c.textContent = texto ?? '';
  if (classe) c.className = classe;
  return c;
}

function preencherFamilias() {
  const sel = $('filtro-familia');
  const atual = sel.value;
  const familias = [...new Set(TODAS.map((e) => e.family).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">Todas</option>';
  for (const f of familias) {
    const o = document.createElement('option');
    o.textContent = f;
    sel.appendChild(o);
  }
  sel.value = familias.includes(atual) ? atual : '';
}

function renderTabela() {
  const termo = normalizar($('busca').value);
  const origem = $('filtro-origem').value;
  const familia = $('filtro-familia').value;
  const lista = TODAS.filter((e) =>
    (!origem || e.origem === origem) &&
    (!familia || e.family === familia) &&
    (!termo || [e.scientific_name, e.common_name, e.family, e.genus].some((c) => normalizar(c).includes(termo))))
    .sort((a, b) => (a.origem === 'usuario' ? 0 : 1) - (b.origem === 'usuario' ? 0 : 1) ||
                    a.scientific_name.localeCompare(b.scientific_name));

  const doUsuario = TODAS.filter((e) => e.origem === 'usuario').length;
  $('contagem').textContent = `${lista.length} de ${TODAS.length} espécies (${doUsuario} cadastrada${doUsuario === 1 ? '' : 's'} por você)`;

  const area = $('tabela');
  area.innerHTML = '';
  if (!lista.length) {
    const p = document.createElement('p');
    p.className = 'picker__empty';
    p.textContent = 'Nenhuma espécie com esses filtros.';
    area.appendChild(p);
    return;
  }
  const tabela = document.createElement('table');
  tabela.className = 'banco-tabela';
  const cab = document.createElement('tr');
  for (const t of ['Nome científico', 'Nome popular', 'Família', 'Origem', '']) {
    const th = document.createElement('th'); th.textContent = t; cab.appendChild(th);
  }
  tabela.appendChild(cab);
  for (const e of lista) {
    const tr = document.createElement('tr');
    tr.appendChild(td(e.scientific_name, 'sp'));
    tr.appendChild(td(e.common_name || '—'));
    tr.appendChild(td(e.family));
    const tdOrigem = document.createElement('td');
    const tag = document.createElement('span');
    tag.className = e.origem === 'usuario' ? 'lit__tag lit__tag--forte' : 'lit__tag';
    tag.textContent = e.origem === 'usuario' ? 'sua planta' : 'do projeto';
    tdOrigem.appendChild(tag);
    tr.appendChild(tdOrigem);
    const tdAcoes = document.createElement('td');
    const acoes = document.createElement('div');
    acoes.className = 'acoes-linha';
    tdAcoes.appendChild(acoes);
    const usar = document.createElement('a');
    usar.href = `recomendar.html?${new URLSearchParams({ especie: e.scientific_name })}`;
    usar.textContent = 'recomendar';
    acoes.appendChild(usar);
    if (e.origem === 'usuario') {
      const btn = document.createElement('button');
      btn.className = 'btn btn--ghost btn--mini';
      btn.textContent = 'remover';
      btn.addEventListener('click', () => remover(e.scientific_name));
      acoes.appendChild(btn);
    }
    tr.appendChild(tdAcoes);
    tabela.appendChild(tr);
  }
  area.appendChild(tabela);
}

async function carregar() {
  TODAS = await (await fetch('/especies')).json();
  preencherFamilias();
  renderTabela();
}

async function preencherPelaGbif() {
  mostrar('msg-erro', ''); mostrar('msg-ok', '');
  const nome = $('f-nome').value.trim();
  if (!nome) { mostrar('msg-erro', 'Digite o nome científico primeiro.'); return; }
  await comCarregamento($('btn-gbif'), 'Consultando...', async () => {
    const resp = await fetch(`/taxonomia/${encodeURIComponent(nome.split(' (')[0])}`);
    if (!resp.ok) {
      mostrar('msg-gbif', 'A GBIF não reconheceu o nome ou não respondeu. Preencha família e gênero à mão.');
      return;
    }
    const t = await resp.json();
    if (t.source !== 'gbif') {
      mostrar('msg-gbif', t.source === 'usuario' || t.source === 'fallback_local'
        ? 'Essa espécie já está na lista local.'
        : 'A GBIF não respondeu agora. Preencha família e gênero à mão.');
      return;
    }
    if (t.family) $('f-familia').value = t.family;
    if (t.genus) $('f-genero').value = t.genus;
    mostrar('msg-gbif', `Família e gênero preenchidos pela GBIF (${t.family} / ${t.genus}). Confira antes de salvar.`);
  });
}

async function salvar() {
  mostrar('msg-erro', ''); mostrar('msg-ok', '');
  const corpo = {
    nome_cientifico: $('f-nome').value,
    nome_popular: $('f-popular').value,
    familia: $('f-familia').value,
    genero: $('f-genero').value,
    observacoes: $('f-obs').value,
  };
  await comCarregamento($('btn-salvar'), 'Salvando...', async () => {
    const resp = await fetch('/especies', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
    });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      mostrar('msg-erro', typeof dados.detail === 'string' ? dados.detail : 'Confira os campos: nome científico, família e gênero.');
      return;
    }
    mostrar('msg-ok', `${dados.scientific_name} adicionada${dados.preenchido_pela_gbif ? ' (família e gênero vieram da GBIF)' : ''}. Ela já aparece nos seletores de Consultar e Recomendar.`);
    for (const id of ['f-nome', 'f-popular', 'f-familia', 'f-genero', 'f-obs']) $(id).value = '';
    generoEditado = false;
    mostrar('msg-gbif', '');
    $('filtro-origem').value = 'usuario';
    await carregar();
  });
}

async function remover(nome) {
  if (!confirm(`Remover ${nome} da sua lista de plantas?`)) return;
  const resp = await fetch(`/especies/${encodeURIComponent(nome)}`, { method: 'DELETE' });
  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    alert(dados.detail || 'Não foi possível remover.');
  }
  carregar();
}

// Gênero acompanha a primeira palavra do nome, enquanto o usuário não editar o campo.
let generoEditado = false;
$('f-genero').addEventListener('input', () => { generoEditado = true; });
$('f-nome').addEventListener('input', () => {
  if (generoEditado) return;
  const primeira = $('f-nome').value.trim().split(/\s+/)[0] || '';
  $('f-genero').value = primeira ? primeira[0].toUpperCase() + primeira.slice(1).toLowerCase() : '';
});

$('btn-gbif').addEventListener('click', preencherPelaGbif);
$('btn-salvar').addEventListener('click', salvar);
$('busca').addEventListener('input', renderTabela);
$('filtro-origem').addEventListener('change', renderTabela);
$('filtro-familia').addEventListener('change', renderTabela);
carregar();
