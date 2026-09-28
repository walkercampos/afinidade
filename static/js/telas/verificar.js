// Destino do link do e-mail (#/verificar/<token>). O token fica no fragmento da URL, que o
// navegador nunca envia a servidores; aqui ele é trocado por uma sessão e some do histórico.
import { confirmarLink, suportaPasskeys } from "../api.js";
import { h } from "../dom.js";
import { irPara } from "../roteador.js";

export async function telaVerificar(token, ctx) {
  ctx.carregando();
  history.replaceState(null, "", "#/verificando"); // o token não fica no histórico
  try {
    const r = await confirmarLink(token ?? "");
    irPara(r.novo && suportaPasskeys() ? "biometria" : "descobrir");
  } catch (e) {
    ctx.mostrar(h("h1", {}, "Link inválido"),
      h("div", { class: "cartao" }, h("p", {}, e.message),
        h("div", { class: "acoes" }, h("button", { type: "button", onclick: () => irPara("entrar") }, "Voltar"))));
  }
}
