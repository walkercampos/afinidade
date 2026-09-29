import { api, carregarCatalogo } from "../api.js";
import { acoesDeSeguranca, cartaoPerfil } from "../componentes.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

const ORDENS = [
  ["compatibilidade", "Mais compatíveis"],
  ["afinidade", "Gostos parecidos"],
  ["recentes", "Ativos recentemente"],
];
let ordemAtual = "compatibilidade";

async function buscar(cursor) {
  const params = new URLSearchParams({ limite: "20", ordem: ordemAtual });
  if (cursor) params.set("cursor", cursor);
  const r = await fetch(`/api/descobrir?${params}`, { credentials: "same-origin" });
  if (r.status === 401) { irPara("entrar"); return null; }
  if (r.status === 409) { irPara("perfil"); return null; }
  if (r.status === 403) {
    const { detail } = await r.json().catch(() => ({}));
    if (detail === "Verificação de idade pendente") { irPara("idade"); return null; }
    throw new Error(detail ?? "Acesso negado.");
  }
  if (!r.ok) throw new Error("Não foi possível carregar os perfis.");
  return { itens: await r.json(), proximo: r.headers.get("X-Proximo-Cursor") };
}

function cartaoCandidato({ perfil, compatibilidade, fotos }) {
  const cartao = cartaoPerfil(perfil, compatibilidade, {
    fotos,
    acoes: [
      ...acoesDeSeguranca(perfil.id, () => cartao),
      h("button", { type: "button", class: "secundario", onclick: () => cartao.remove() }, "Pular"),
      h("button", { type: "button", onclick: async () => {
        const r = await api(`/perfis/${perfil.id}/curtir`, { metodo: "POST" });
        cartao.remove();
        avisar(r.conexao ? "É uma conexão! Vocês já podem conversar." : "Curtida enviada");
      } }, "Curtir"),
    ],
  });
  return cartao;
}

export async function telaDescobrir(_parametro, ctx) {
  ctx.carregando();
  await carregarCatalogo();
  const pagina = await buscar(null);
  if (!pagina) return;

  const lista = h("div", {});
  const mais = h("button", { type: "button", class: "secundario" }, "Ver mais");
  const vazio = h("p", { class: "vazio" });
  let proximo = pagina.proximo;
  let jaViuAlguem = false;
  // Sem cartões na tela: avisa por quê, em vez de deixar a página em branco.
  function atualizarVazio() {
    const semCartoes = lista.childElementCount === 0;
    vazio.hidden = !semCartoes || Boolean(proximo);
    vazio.textContent = jaViuAlguem
      ? "Você viu todo mundo por enquanto. Volte mais tarde para ver quem chegou."
      : "Ninguém compatível por enquanto. Volte mais tarde ou ajuste seus interesses e a distância.";
  }
  // Pular, Curtir, Bloquear e Denunciar removem o cartão: observa a lista em vez de cada botão.
  new MutationObserver(atualizarVazio).observe(lista, { childList: true });
  function acrescentar({ itens, proximo: p }) {
    lista.append(...itens.map(cartaoCandidato));
    jaViuAlguem ||= itens.length > 0;
    proximo = p;
    mais.hidden = !proximo;
    atualizarVazio();
  }
  mais.addEventListener("click", async () => { mais.disabled = true; acrescentar(await buscar(proximo)); mais.disabled = false; });

  const seletor = h("select", { "aria-label": "Ordenar por", onchange: (ev) => { ordemAtual = ev.target.value; irPara("descobrir"); } },
    ORDENS.map(([v, t]) => h("option", { value: v, selected: v === ordemAtual }, t)));

  ctx.mostrar(
    h("div", { class: "titulo-com-acao" }, h("h1", {}, "Descobrir"), seletor),
    lista,
    vazio,
    h("div", { class: "acoes" }, mais),
  );
  acrescentar(pagina);
}
