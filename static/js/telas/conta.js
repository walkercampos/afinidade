import { adicionarPasskey, api, suportaPasskeys } from "../api.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

const data = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "nunca");

async function secaoPasskeys() {
  const lista = await api("/passkeys");
  const secao = h("section", { class: "cartao" },
    h("h2", {}, "Passkeys"),
    h("p", { class: "nota" }, lista.length
      ? "Entre com a digital, o rosto ou o PIN. Tenha pelo menos duas (ex.: celular e computador) para não perder o acesso."
      : "Adicione uma passkey para entrar sem senha, com a digital, o rosto ou o PIN do aparelho."),
    h("ul", { class: "lista-passkeys" }, lista.map((p) => h("li", {},
      h("div", {},
        h("strong", {}, p.nome),
        h("small", {}, `${p.sincronizada ? "sincronizada" : "só neste aparelho"} · criada ${data(p.criado_em)} · último uso ${data(p.usado_em)}`)),
      h("button", { type: "button", class: "secundario", onclick: async () => {
        if (!confirm(`Remover a passkey "${p.nome}"?`)) return;
        await api(`/passkeys/${p.id}`, { metodo: "DELETE" });
        avisar("Passkey removida");
        secao.replaceWith(await secaoPasskeys());
      } }, "Remover")))),
    suportaPasskeys() && h("div", { class: "acoes" }, h("button", { type: "button", onclick: async () => {
      try {
        await adicionarPasskey(prompt("Nome para esta passkey (ex.: Celular):", "") ?? "");
        avisar("Passkey adicionada");
        secao.replaceWith(await secaoPasskeys());
      } catch (e) { avisar(e.message); }
    } }, "Adicionar passkey neste aparelho")));
  return secao;
}

export async function telaConta(_parametro, ctx) {
  const passkeys = await secaoPasskeys();
  ctx.mostrar(h("h1", {}, "Conta"), passkeys,
    h("div", { class: "cartao" },
      h("h2", {}, "Saída rápida"),
      h("p", { class: "nota" }, "Aperte ESC ou o botão vermelho a qualquer momento: a tela some, a sessão é encerrada e você vai para o Google."),
    ),
    h("div", { class: "cartao" },
      h("h2", {}, "Sair"),
      h("p", { class: "nota" }, "Encerra a sessão em todos os dispositivos."),
      h("div", { class: "acoes" }, h("button", { type: "button", class: "secundario", onclick: async () => {
        await api("/auth/sair", { metodo: "POST" });
        irPara("entrar");
      } }, "Sair de todos os dispositivos"))),
    h("div", { class: "cartao" },
      h("h2", {}, "Excluir conta"),
      h("p", { class: "nota" }, "Apaga definitivamente perfil, fotos, interesses, curtidas, conexões e mensagens. Não há como desfazer."),
      h("div", { class: "acoes" }, h("button", { type: "button", class: "perigo", onclick: async () => {
        if (!confirm("Excluir sua conta e todos os seus dados para sempre?")) return;
        await api("/conta", { metodo: "DELETE" });
        irPara("entrar");
        avisar("Conta excluída");
      } }, "Excluir tudo"))));
}
