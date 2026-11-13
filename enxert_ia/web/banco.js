// Banco de combinacoes: listar/filtrar e cadastrar registros.
const ROTULO_EVIDENCIA = {
  citada: 'citada',
  conhecimento_geral: 'conhecimento geral (sem citacao)',
  relato_nao_verificado: 'relato nao verificado',
};

function celula(texto, classe) {
  const td = document.createElement('td');
  td.textContent = texto ?? '';
  if (classe) td.className = classe;
  return td;
}

function renderTabela(registros) {
  const area = document.getElementById('tabela-area');
  area.innerHTML = '';
  document.getElementById('contagem').textContent = `${registros.length} registro(s)`;
  if (!registros.length) {
    const p = document.createElement('p');
    p.className = 'picker__empty';
    p.textContent = 'Nenhum registro encontrado.';
    area.appendChild(p);
    return;
  }
  const tabela = document.createElement('table');
  tabela.className = 'banco-tabela';
  const cab = document.createElement('tr');
  for (const t of ['Porta-enxerto', 'Enxerto', 'Compat.', 'Evidencia', 'Fonte / observacoes', '']) {
    const th = document.createElement('th'); th.textContent = t; cab.appendChild(th);
  }
  tabela.appendChild(cab);
  for (const r of registros) {
    const tr = document.createElement('tr');
    tr.appendChild(celula(r.porta_enxerto, 'sp'));
    tr.appendChild(celula(r.enxerto, 'sp'));
    tr.appendChild(celula(`${Math.round(r.compatibilidade * 100)}% ${r.nivel}`, `level-${r.nivel}`));
    tr.appendChild(celula(ROTULO_EVIDENCIA[r.tipo_evidencia] || r.tipo_evidencia));
    tr.appendChild(celula([r.fonte, r.observacoes].filter(Boolean).join(' -- ')));
    const tdAcao = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'btn btn--ghost btn--mini';
    btn.textContent = 'apagar';
    btn.addEventListener('click', async () => {
      if (!confirm(`Apagar ${r.porta_enxerto} x ${r.enxerto}? Isso nao pode ser desfeito.`)) return;
      await fetch(`/banco/combinacoes/${r.id}`, { method: 'DELETE' });
      carregar();
    });
    tdAcao.appendChild(btn);
    tr.appendChild(tdAcao);
    tabela.appendChild(tr);
  }
  area.appendChild(tabela);
}

function renderLiteratura(registros) {
  const area = document.getElementById('tabela-lit');
  area.innerHTML = '';
  document.getElementById('contagem-lit').textContent = `${registros.length} registro(s) da literatura`;
  if (!registros.length) return;
  const tabela = document.createElement('table');
  tabela.className = 'banco-tabela';
  const cab = document.createElement('tr');
  for (const t of ['Copa', 'Porta-enxerto', 'O que a fonte afirma', 'Conferido', 'Fonte']) {
    const th = document.createElement('th'); th.textContent = t; cab.appendChild(th);
  }
  tabela.appendChild(cab);
  for (const r of registros) {
    const tr = document.createElement('tr');
    tr.appendChild(celula(r.copa, 'sp'));
    tr.appendChild(celula(r.porta_enxerto, 'sp'));
    tr.appendChild(celula(`${r.afirmacao}${r.medida ? ' (' + r.medida + ')' : ''}${r.ressalva ? ' -- ' + r.ressalva : ''}`));
    tr.appendChild(celula(r.conferido ? 'sim' : 'nao'));
    const tdFonte = document.createElement('td');
    tdFonte.appendChild(document.createTextNode(`${r.id_registro}: ${r.fonte_referencia} `));
    if (r.fonte_url && /^https?:\/\//.test(r.fonte_url)) {
      const a = document.createElement('a'); a.href = r.fonte_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'abrir';
      tdFonte.appendChild(a);
    }
    tr.appendChild(tdFonte);
    tabela.appendChild(tr);
  }
  area.appendChild(tabela);
}

async function carregar() {
  const q = document.getElementById('busca').value.trim();
  const cultura = document.getElementById('filtro-cultura').value;
  const sufixo = q ? `?q=${encodeURIComponent(q)}` : '';
  const paramsLit = new URLSearchParams();
  if (q) paramsLit.set('q', q);
  if (cultura) paramsLit.set('cultura', cultura);
  const url = new URLSearchParams(paramsLit);
  history.replaceState(null, '', `${location.pathname}${url.toString() ? '?' + url : ''}`);
  const [resp, respLit] = await Promise.all([fetch('/banco/combinacoes' + sufixo), fetch(`/literatura?${paramsLit}`)]);
  renderTabela(await resp.json());
  renderLiteratura(respLit.ok ? await respLit.json() : []);
}

async function salvar() {
  const erro = document.getElementById('msg-erro');
  const ok = document.getElementById('msg-ok');
  erro.hidden = true; ok.hidden = true;
  const corpo = {
    porta_enxerto: document.getElementById('f-porta').value,
    enxerto: document.getElementById('f-enxerto').value,
    compatibilidade: parseFloat(document.getElementById('f-resultado').value),
    tipo_evidencia: document.getElementById('f-evidencia').value,
    fonte: document.getElementById('f-fonte').value,
    observacoes: document.getElementById('f-obs').value,
  };
  const resp = await fetch('/banco/combinacoes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
  });
  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    erro.textContent = typeof dados.detail === 'string' ? dados.detail : 'Dados invalidos.';
    erro.hidden = false;
    return;
  }
  ok.textContent = 'Registro salvo.';
  ok.hidden = false;
  for (const id of ['f-porta', 'f-enxerto', 'f-fonte', 'f-obs']) document.getElementById(id).value = '';
  carregar();
}

let esperaBusca = null;
document.getElementById('busca').addEventListener('input', () => {
  clearTimeout(esperaBusca);
  esperaBusca = setTimeout(carregar, 250);
});
document.getElementById('filtro-cultura').addEventListener('change', carregar);
document.getElementById('btn-salvar').addEventListener('click', salvar);

// Filtros vindos da URL (ex.: link "ver todos" da pagina de compatibilidade).
const inicial = new URLSearchParams(location.search);
if (inicial.get('q')) document.getElementById('busca').value = inicial.get('q');
if (inicial.get('cultura')) document.getElementById('filtro-cultura').value = inicial.get('cultura');
carregar();
