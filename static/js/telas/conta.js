import { adicionarPasskey, api, suportaPasskeys } from "../api.js";
import { avisar, h } from "../dom.js";
import { aplicarDiscreto, aplicarTema, temaAtual } from "../discricao.js";
import { irPara } from "../roteador.js";

const data = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "nunca");

async function secaoPasskeys() {
  const lista = await api("/passkeys");
  const secao = h("section", { class: "cartao" },
    h("h2", {}, "Biometria (passkeys)"),
    h("p", { class: "nota" }, lista.length
      ? "Você entra com a digital, o rosto ou o PIN destes aparelhos. Perdeu um? Entre por e-mail e remova-o aqui."
      : "Ative a biometria para entrar com a digital, o rosto ou o PIN, sem esperar código por e-mail."),
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
    } }, "Ativar biometria neste aparelho")));
  return secao;
}

const TEMAS = [["sistema", "Automático"], ["claro", "Claro"], ["escuro", "Escuro"]];

function secaoAparencia(preferencias) {
  const botoes = TEMAS.map(([valor, rotulo]) => h("button", {
    type: "button", role: "tab", "aria-selected": String(temaAtual() === valor),
    onclick: () => {
      aplicarTema(valor);
      botoes.forEach((b, i) => b.setAttribute("aria-selected", String(TEMAS[i][0] === valor)));
    },
  }, rotulo));
  const discreto = h("input", { type: "checkbox", name: "discreto", checked: preferencias.modo_discreto,
    onchange: async (ev) => {
      const ligado = ev.target.checked;
      try {
        await api("/conta/preferencias", { metodo: "PUT", corpo: { modo_discreto: ligado } });
        aplicarDiscreto(ligado);
        avisar(ligado ? "Modo discreto ligado" : "Modo discreto desligado");
      } catch (e) { ev.target.checked = !ligado; avisar(e.message); }
    } });
  return h("section", { class: "cartao" },
    h("h2", {}, "Aparência e discrição"),
    h("div", { class: "abas", role: "tablist", "aria-label": "Tema" }, botoes),
    h("label", { class: "check" }, discreto,
      h("span", {}, h("strong", {}, "Modo discreto. "),
        "Na aba do navegador, no histórico e na tela inicial o app aparece como \"Notas\", com um ícone neutro.")),
    h("p", { class: "nota" }, "Dica: instale o app na tela inicial com o modo discreto ligado."));
}

export async function telaConta(_parametro, ctx) {
  const [conta, passkeys, preferencias] = await Promise.all([api("/conta"), secaoPasskeys(), api("/conta/preferencias")]);
  ctx.mostrar(h("h1", {}, "Conta"),
    h("section", { class: "cartao" },
      h("h2", {}, "Acesso"),
      h("p", {}, `@${conta.handle}`),
      h("p", { class: "nota" }, conta.email
        ? `E-mail de acesso: ${conta.email}. Guardado criptografado; usado só para códigos de acesso e avisos sobre a conta.`
        : "Entre uma vez com um código por e-mail para registrar o e-mail de acesso.")),
    conta.moderador && h("section", { class: "cartao" },
      h("h2", {}, "Moderação"),
      h("p", { class: "nota" }, "Você tem acesso ao painel de moderação."),
      h("div", { class: "acoes" }, h("button", { type: "button", onclick: () => irPara("moderacao") }, "Abrir painel"))),
    passkeys,
    secaoAparencia(preferencias),
    h("div", { class: "cartao" },
      h("h2", {}, "Encontro seguro"),
      h("p", { class: "nota" }, "Vai encontrar alguém? Registre onde e com quem. Se você não fizer o check-in, um contato de confiança é avisado."),
      h("div", { class: "acoes" }, h("button", { type: "button", class: "secundario", onclick: () => irPara("encontros") }, "Abrir"))),
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
