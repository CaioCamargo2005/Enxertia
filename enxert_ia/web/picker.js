// Seletor de especies compartilhado pelas paginas de consulta e recomendacao.
// Digite o nome popular ou cientifico (sem se preocupar com acentos) ou clique
// para navegar por genero. Enter escolhe a primeira sugestao; Esc fecha.

function normalizar(texto) {
  return (texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

function agruparPorGenero(lista) {
  const grupos = {};
  for (const sp of lista) {
    const genero = sp.genus || sp.scientific_name.split(' ')[0];
    if (!grupos[genero]) grupos[genero] = [];
    grupos[genero].push(sp);
  }
  return grupos;
}

function rotuloEspecie(sp) {
  return `${sp.scientific_name}${sp.common_name ? ' (' + sp.common_name + ')' : ''}`;
}

// Busca nas especies locais por nome cientifico, popular ou genero.
// Quem comeca com o termo vem antes de quem so o contem.
function buscarEspecies(lista, termo) {
  const t = normalizar(termo);
  if (!t) return [];
  const pontos = (sp) => {
    const campos = [sp.scientific_name, sp.common_name, sp.genus].map(normalizar);
    if (campos.some((c) => c.startsWith(t))) return 0;
    if (campos.some((c) => c.includes(t))) return 1;
    return -1;
  };
  return lista
    .map((sp) => [pontos(sp), sp])
    .filter(([p]) => p >= 0)
    .sort((a, b) => a[0] - b[0] || a[1].scientific_name.localeCompare(b[1].scientific_name))
    .map(([, sp]) => sp);
}

// Procura uma especie local pelo nome exato (cientifico ou popular).
function acharEspecie(lista, nome) {
  const t = normalizar(nome);
  return lista.find((sp) => normalizar(sp.scientific_name) === t || normalizar(sp.common_name) === t) || null;
}

function criarPicker({ raizId, inputId, painelId, especies, aoSelecionar, aoLimpar }) {
  const raiz = document.getElementById(raizId);
  const input = document.getElementById(inputId);
  const painel = document.getElementById(painelId);
  let sugestoes = [];

  function chip(texto, classe, aoClicar, titulo) {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.className = classe;
    b.textContent = texto;
    if (titulo) b.title = titulo;
    b.addEventListener('click', aoClicar);
    li.appendChild(b);
    return li;
  }

  function lista() {
    const ul = document.createElement('ul');
    ul.className = 'picker__list';
    return ul;
  }

  function renderGeneros() {
    sugestoes = [];
    const grupos = agruparPorGenero(especies());
    painel.innerHTML = '';
    const dica = document.createElement('div');
    dica.className = 'picker__breadcrumb';
    dica.textContent = 'Generos do banco local -- ou digite um nome popular ou cientifico';
    painel.appendChild(dica);
    const ul = lista();
    for (const genero of Object.keys(grupos).sort()) {
      ul.appendChild(chip(`${genero} (${grupos[genero].length})`, 'picker__chip', () => renderEspecies(genero)));
    }
    painel.appendChild(ul);
  }

  function chipEspecie(sp) {
    return chip(sp.scientific_name, 'picker__chip picker__chip--species', () => selecionar(sp), sp.common_name || '');
  }

  function renderEspecies(genero) {
    const grupos = agruparPorGenero(especies());
    sugestoes = grupos[genero] || [];
    painel.innerHTML = '';
    const crumb = document.createElement('div');
    crumb.className = 'picker__breadcrumb';
    const voltar = document.createElement('button');
    voltar.type = 'button';
    voltar.textContent = '< generos';
    voltar.addEventListener('click', () => { renderGeneros(); input.focus(); });
    crumb.appendChild(voltar);
    crumb.appendChild(document.createTextNode(genero));
    painel.appendChild(crumb);
    const ul = lista();
    for (const sp of sugestoes) ul.appendChild(chipEspecie(sp));
    painel.appendChild(ul);
  }

  function renderBusca(termo) {
    sugestoes = buscarEspecies(especies(), termo);
    painel.innerHTML = '';
    if (!sugestoes.length) {
      const vazio = document.createElement('p');
      vazio.className = 'picker__empty';
      vazio.textContent = 'Nenhuma especie do banco local com esse nome. Para outro nome cientifico, use o campo logo abaixo (a busca vai para a GBIF).';
      painel.appendChild(vazio);
      return;
    }
    const ul = lista();
    for (const sp of sugestoes) {
      ul.appendChild(chip(rotuloEspecie(sp), 'picker__chip picker__chip--species', () => selecionar(sp)));
    }
    painel.appendChild(ul);
  }

  function render() {
    if (input.value.trim()) renderBusca(input.value); else renderGeneros();
  }

  function abrir() {
    render();
    painel.hidden = false;
    document.addEventListener('click', aoClicarFora);
  }

  function fechar() {
    painel.hidden = true;
    document.removeEventListener('click', aoClicarFora);
  }

  function aoClicarFora(ev) {
    // composedPath() e imune ao chip clicado ser removido do DOM antes deste handler rodar.
    if (!ev.composedPath().includes(raiz)) fechar();
  }

  function selecionar(sp, { silencioso = false } = {}) {
    input.value = rotuloEspecie(sp);
    fechar();
    if (!silencioso) aoSelecionar(sp);
  }

  input.addEventListener('focus', () => { if (painel.hidden) abrir(); });
  input.addEventListener('click', () => { if (painel.hidden) abrir(); });
  input.addEventListener('input', () => {
    if (aoLimpar) aoLimpar();
    if (painel.hidden) abrir(); else render();
  });
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') { fechar(); return; }
    if (ev.key === 'Enter' && !painel.hidden && sugestoes.length) {
      ev.preventDefault();
      selecionar(sugestoes[0]);
    }
  });

  return { fechar, selecionar, limpar: () => { input.value = ''; } };
}

// Botao em estado "carregando" enquanto uma promessa roda.
async function comCarregamento(botao, textoCarregando, tarefa) {
  const original = botao.textContent;
  botao.disabled = true;
  botao.classList.add('btn--loading');
  botao.textContent = textoCarregando;
  try {
    return await tarefa();
  } finally {
    botao.textContent = original;
    botao.classList.remove('btn--loading');
    botao.disabled = false;
  }
}
