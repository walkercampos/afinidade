import { avisar, carregando, mostrar } from "./dom.js";
import { lerRota } from "./util.js";

const menu = document.getElementById("menu");
const rotas = new Map();
let aoSair = [];
let geracao = 0;

export function registrarRota(nome, tela, { comMenu = true } = {}) {
  rotas.set(nome, { tela, comMenu });
}

/** Tarefas (timers, polling) a cancelar quando a pessoa sai da tela atual. */
export function aoSairDaTela(fn) {
  aoSair.push(fn);
}

/**
 * Navega SEM criar entradas no histórico (location.replace): depois do botão de pânico,
 * o "voltar" do navegador não percorre as telas do app.
 */
export function irPara(rota) {
  const alvo = `#/${rota}`;
  if (location.hash === alvo) renderizar();
  else location.replace(alvo);
}

/**
 * Contexto de UMA navegação. Se a pessoa já foi para outra tela, `mostrar` vira no-op:
 * uma tela lenta que termina depois não sobrescreve a tela nova.
 */
function criarContexto(minhaGeracao) {
  const ativa = () => minhaGeracao === geracao;
  return {
    ativa,
    mostrar: (...nos) => { if (ativa()) mostrar(...nos); },
    carregando: () => { if (ativa()) carregando(); },
  };
}

export async function renderizar() {
  aoSair.forEach((fn) => fn());
  aoSair = [];
  const ctx = criarContexto(++geracao);
  const { rota, parametro } = lerRota(location.hash);
  const { tela, comMenu } = rotas.get(rota) ?? rotas.get("descobrir");
  menu.hidden = !comMenu;
  for (const a of menu.querySelectorAll("a")) {
    if (a.dataset.rota === rota) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  try { await tela(parametro, ctx); } catch (e) { if (ctx.ativa() && e.status !== 401) avisar(e.message); }
}

export function iniciarRoteador() {
  window.addEventListener("hashchange", renderizar);
  // Links internos também trocam a página sem empilhar histórico.
  document.addEventListener("click", (ev) => {
    const a = ev.target.closest("a[href^='#/']");
    if (!a) return;
    ev.preventDefault();
    irPara(a.getAttribute("href").slice(2));
  });
  renderizar();
}
