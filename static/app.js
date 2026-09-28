// Front-end sem dependências. Regra de segurança: dados vindos da API entram no DOM
// SOMENTE via textContent (nunca innerHTML), e a CSP bloqueia qualquer script inline.

const tela = document.getElementById("tela");
const menu = document.getElementById("menu");
const aviso = document.getElementById("aviso");

// ---------- utilidades ----------

function h(tag, attrs = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f != null && f !== false) el.append(f instanceof Node ? f : String(f));
  return el;
}

function mostrar(...nos) { tela.replaceChildren(...nos); window.scrollTo(0, 0); }

let avisoTimer;
function avisar(texto) {
  aviso.textContent = texto;
  aviso.hidden = false;
  clearTimeout(avisoTimer);
  avisoTimer = setTimeout(() => { aviso.hidden = true; }, 2600);
}

class ErroApi extends Error {
  constructor(status, detalhe) { super(detalhe); this.status = status; }
}

async function api(caminho, { metodo = "GET", corpo } = {}) {
  const r = await fetch(`/api${caminho}`, {
    method: metodo,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF": "1" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  if (r.status === 401 && !caminho.startsWith("/auth/")) { irPara("entrar"); throw new ErroApi(401, "Sessão expirada"); }
  if (r.status === 204) return null;
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErroApi(r.status, mensagemDeErro(dados));
  return dados;
}

function mensagemDeErro(dados) {
  const d = dados?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((e) => String(e.msg).replace(/^Value error, /, "")).join(" · ");
  return "Algo deu errado. Tente de novo.";
}

let catalogo = null;
async function carregarCatalogo() {
  if (!catalogo) {
    const [generos, tags] = await Promise.all([api("/catalogo/generos"), api("/catalogo/tags")]);
    catalogo = { generos, tags, rotulo: new Map([...generos, ...tags].map((i) => [i.slug, i.rotulo])) };
  }
  return catalogo;
}
const rotulo = (slug) => catalogo?.rotulo.get(slug) ?? slug;

function carregando() { mostrar(h("p", { class: "vazio" }, "Carregando…")); }

function formulario(onEnviar, ...campos) {
  const erro = h("p", { class: "erro", role: "alert" });
  const form = h("form", {
    onsubmit: async (ev) => {
      ev.preventDefault();
      const botao = form.querySelector("button[type=submit]");
      botao.disabled = true;
      erro.textContent = "";
      try { await onEnviar(new FormData(form)); } catch (e) { erro.textContent = e.message; } finally { botao.disabled = false; }
    },
  }, ...campos, erro);
  return form;
}

// ---------- telas ----------

function telaEntrar() {
  menu.hidden = true;
  let modo = "entrar";
  const abaEntrar = h("button", { type: "button", role: "tab", onclick: () => trocar("entrar") }, "Entrar");
  const abaCriar = h("button", { type: "button", role: "tab", onclick: () => trocar("criar") }, "Criar conta");
  const area = h("div");

  function trocar(novo) {
    modo = novo;
    abaEntrar.setAttribute("aria-selected", modo === "entrar");
    abaCriar.setAttribute("aria-selected", modo === "criar");
    area.replaceChildren(modo === "entrar" ? formEntrar() : formCriar());
  }

  const campoHandle = () => [
    h("label", { for: "handle" }, "Apelido"),
    h("input", { id: "handle", name: "handle", type: "text", required: true, autocomplete: "username",
      autocapitalize: "none", spellcheck: "false", pattern: "[a-zA-Z0-9_]{3,30}", maxlength: 30 }),
  ];

  function formEntrar() {
    return formulario(async (f) => {
      await api("/auth/login", { metodo: "POST", corpo: { handle: f.get("handle"), senha: f.get("senha") } });
      irPara("descobrir");
    },
    ...campoHandle(),
    h("label", { for: "senha" }, "Senha"),
    h("input", { id: "senha", name: "senha", type: "password", required: true, autocomplete: "current-password" }),
    h("div", { class: "acoes" }, h("button", { type: "submit" }, "Entrar")));
  }

  function formCriar() {
    return formulario(async (f) => {
      await api("/auth/registro", { metodo: "POST", corpo: {
        handle: f.get("handle"), senha: f.get("senha"), data_nascimento: f.get("nascimento"),
        confirmo_maior_de_idade: f.get("maior") === "on", consinto_dados_sensiveis: f.get("consinto") === "on",
      } });
      irPara("perfil");
    },
    h("p", { class: "nota" }, "Não pedimos e-mail, telefone nem nome real. Use um apelido que não identifique você em outras redes."),
    ...campoHandle(),
    h("p", { class: "nota" }, "3 a 30 caracteres: letras, números e _"),
    h("label", { for: "senha" }, "Senha"),
    h("input", { id: "senha", name: "senha", type: "password", required: true, minlength: 10, maxlength: 128, autocomplete: "new-password" }),
    h("p", { class: "nota" }, "Mínimo de 10 caracteres. Sem e-mail não há recuperação de senha: guarde-a num gerenciador."),
    h("label", { for: "nascimento" }, "Data de nascimento"),
    h("input", { id: "nascimento", name: "nascimento", type: "date", required: true }),
    h("p", { class: "nota" }, "Usada só para confirmar a maioridade. Não é armazenada."),
    h("label", { class: "check" }, h("input", { type: "checkbox", name: "maior", required: true }), "Tenho 18 anos ou mais."),
    h("label", { class: "check" }, h("input", { type: "checkbox", name: "consinto", required: true }),
      "Consinto com o tratamento dos meus dados sobre sexualidade para gerar compatibilidades. Posso excluir tudo a qualquer momento."),
    h("div", { class: "acoes" }, h("button", { type: "submit" }, "Criar conta")));
  }

  mostrar(h("h1", {}, "Conexões por afinidade, sem expor quem você é"),
    h("div", { class: "abas", role: "tablist" }, abaEntrar, abaCriar), area);
  trocar(modo);
}

function listaDeTags(slugs, comuns = new Set()) {
  return h("ul", { class: "chips" }, slugs.map((s) => h("li", { class: comuns.has(s) ? "chip comum" : "chip" }, rotulo(s))));
}

function cartaoPerfil(perfil, compat, acoes) {
  const comuns = new Set(compat?.tags_em_comum ?? []);
  return h("article", { class: "cartao" },
    h("header", {},
      h("div", {}, h("div", { class: "nome" }, perfil.nome_exibicao), h("div", { class: "genero" }, rotulo(perfil.genero))),
      compat && h("div", { class: "score" }, `${compat.score_mutuo}%`, h("small", {}, "afinidade"))),
    perfil.bio && h("p", { class: "bio" }, perfil.bio),
    perfil.quero.length > 0 && [h("h2", {}, "Quer"), listaDeTags(perfil.quero, comuns)],
    perfil.curioso.length > 0 && [h("h2", {}, "Curioso(a)"), listaDeTags(perfil.curioso, comuns)],
    acoes && h("div", { class: "acoes" }, acoes));
}

async function bloquearPerfil(id, cartao) {
  if (!confirm("Bloquear este perfil? Vocês deixam de se ver para sempre.")) return;
  await api(`/perfis/${id}/bloquear`, { metodo: "POST" });
  cartao.remove();
  avisar("Perfil bloqueado");
}

async function telaDescobrir() {
  carregando();
  await carregarCatalogo();
  let candidatos;
  try { candidatos = await api("/descobrir?limite=30"); } catch (e) {
    if (e.status === 409) return irPara("perfil");
    throw e;
  }
  if (!candidatos.length) {
    return mostrar(h("h1", {}, "Descobrir"),
      h("p", { class: "vazio" }, "Ninguém compatível por enquanto. Volte mais tarde ou ajuste seus interesses."));
  }
  const cartoes = candidatos.map(({ perfil, compatibilidade }) => {
    const cartao = cartaoPerfil(perfil, compatibilidade, [
      h("button", { type: "button", class: "secundario", onclick: () => bloquearPerfil(perfil.id, cartao) }, "Bloquear"),
      h("button", { type: "button", class: "secundario", onclick: () => cartao.remove() }, "Pular"),
      h("button", { type: "button", onclick: async () => {
        const r = await api(`/perfis/${perfil.id}/curtir`, { metodo: "POST" });
        cartao.remove();
        avisar(r.conexao ? "É uma conexão! 💞" : "Curtida enviada");
      } }, "Curtir"),
    ]);
    return cartao;
  });
  mostrar(h("h1", {}, "Descobrir"), ...cartoes);
}

async function telaConexoes() {
  carregando();
  await carregarCatalogo();
  const conexoes = await api("/conexoes");
  mostrar(h("h1", {}, "Conexões"),
    conexoes.length
      ? conexoes.map((p) => {
        const cartao = cartaoPerfil(p, null, [
          h("button", { type: "button", class: "secundario", onclick: () => bloquearPerfil(p.id, cartao) }, "Bloquear"),
        ]);
        return cartao;
      })
      : h("p", { class: "vazio" }, "Quando alguém que você curtiu curtir você de volta, aparece aqui."));
}

async function telaPerfil() {
  carregando();
  const { generos, tags } = await carregarCatalogo();
  let atual = null;
  try { atual = await api("/perfil"); } catch (e) { if (e.status !== 404) throw e; }

  const niveis = new Map();
  for (const nivel of ["quero", "curioso", "limite_absoluto"])
    for (const s of atual?.tags_interesses[nivel] ?? []) niveis.set(s, nivel);

  const NIVEIS = [["quero", "Quero"], ["curioso", "Curioso"], ["limite_absoluto", "Limite"]];
  const linhasTags = tags.map((t) => {
    const botoes = NIVEIS.map(([nivel, texto]) => h("button", {
      type: "button", "data-nivel": nivel, "aria-pressed": niveis.get(t.slug) === nivel,
      onclick: () => {
        const ativo = niveis.get(t.slug) === nivel;
        ativo ? niveis.delete(t.slug) : niveis.set(t.slug, nivel);
        botoes.forEach((b) => b.setAttribute("aria-pressed", !ativo && b.dataset.nivel === nivel));
      },
    }, texto));
    return h("div", { class: "tag-linha" }, h("span", {}, t.rotulo), h("div", { class: "nivel", role: "group", "aria-label": t.rotulo }, botoes));
  });

  const form = formulario(async (f) => {
    const tagsInteresses = { quero: [], curioso: [], limite_absoluto: [] };
    for (const [slug, nivel] of niveis) tagsInteresses[nivel].push(slug);
    const busca = f.getAll("busca_por");
    if (!busca.length) throw new Error("Escolha pelo menos um gênero que você busca.");
    await api("/perfil", { metodo: "PUT", corpo: {
      nome_exibicao: f.get("nome"), bio: f.get("bio") || null, genero: f.get("genero"), busca_por: busca,
      tags_interesses: tagsInteresses, visivel: f.get("visivel") === "on",
    } });
    avisar("Perfil salvo");
    if (!atual) irPara("descobrir");
  },
  h("label", { for: "nome" }, "Nome de exibição"),
  h("input", { id: "nome", name: "nome", type: "text", required: true, maxlength: 40, value: atual?.nome_exibicao ?? "" }),
  h("label", { for: "bio" }, "Sobre você"),
  (() => { const t = h("textarea", { id: "bio", name: "bio", maxlength: 500 }); t.value = atual?.bio ?? ""; return t; })(),
  h("p", { class: "nota" }, "Evite informações que identifiquem você: nome real, local de trabalho, @ de outras redes."),
  h("label", { for: "genero" }, "Seu gênero"),
  h("select", { id: "genero", name: "genero", required: true },
    h("option", { value: "" }, "Selecione…"),
    generos.map((g) => h("option", { value: g.slug, selected: atual?.genero === g.slug }, g.rotulo))),
  h("label", {}, "Você busca"),
  h("div", { class: "grade-generos" }, generos.map((g) => h("label", { class: "check" },
    h("input", { type: "checkbox", name: "busca_por", value: g.slug, checked: atual?.busca_por.includes(g.slug) }), g.rotulo))),
  h("h2", {}, "Interesses"),
  h("p", { class: "nota" }, "Quero = pratica e gosta · Curioso = aberto(a) a explorar · Limite = nunca. Seus limites não aparecem para ninguém: servem só para esconder pessoas incompatíveis."),
  h("div", { class: "cartao" }, linhasTags),
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "visivel", checked: atual ? atual.visivel : true }),
    "Perfil visível na descoberta"),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Salvar perfil")));

  mostrar(h("h1", {}, atual ? "Seu perfil" : "Crie seu perfil"), form);
}

function telaConta() {
  mostrar(h("h1", {}, "Conta"),
    h("div", { class: "cartao" },
      h("h2", {}, "Sair"),
      h("p", { class: "nota" }, "Encerra a sessão em todos os dispositivos."),
      h("div", { class: "acoes" }, h("button", { type: "button", class: "secundario", onclick: async () => {
        await api("/auth/sair", { metodo: "POST" });
        irPara("entrar");
      } }, "Sair de todos os dispositivos"))),
    h("div", { class: "cartao" },
      h("h2", {}, "Excluir conta"),
      h("p", { class: "nota" }, "Apaga definitivamente perfil, interesses, curtidas e conexões. Não há como desfazer."),
      h("div", { class: "acoes" }, h("button", { type: "button", class: "perigo", onclick: async () => {
        if (!confirm("Excluir sua conta e todos os seus dados para sempre?")) return;
        await api("/conta", { metodo: "DELETE" });
        irPara("entrar");
        avisar("Conta excluída");
      } }, "Excluir tudo"))));
}

// ---------- roteamento ----------

const ROTAS = { entrar: telaEntrar, descobrir: telaDescobrir, conexoes: telaConexoes, perfil: telaPerfil, conta: telaConta };

function irPara(rota) {
  if (location.hash === `#/${rota}`) renderizar();
  else location.hash = `#/${rota}`;
}

async function renderizar() {
  const rota = location.hash.replace(/^#\//, "") || "descobrir";
  const desenhar = ROTAS[rota] ?? telaDescobrir;
  if (rota !== "entrar") {
    menu.hidden = false;
    for (const a of menu.querySelectorAll("a")) {
      if (a.dataset.rota === rota) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
  }
  try { await desenhar(); } catch (e) { if (e.status !== 401) avisar(e.message); }
}

window.addEventListener("hashchange", renderizar);
window.addEventListener("unhandledrejection", (ev) => {
  if (ev.reason instanceof ErroApi) { ev.preventDefault(); if (ev.reason.status !== 401) avisar(ev.reason.message); }
});
renderizar();
