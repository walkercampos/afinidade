import { api } from "../api.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

export function telaConta(_parametro, ctx) {
  ctx.mostrar(h("h1", {}, "Conta"),
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
