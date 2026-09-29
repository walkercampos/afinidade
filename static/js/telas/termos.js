// Aceite dos termos de uso e da política de privacidade (Parte 10; LGPD).
import { api } from "../api.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

export async function aceitarTermosAtuais() {
  const { versao } = await api("/termos");
  return api("/termos/aceitar", { metodo: "POST", corpo: { versao } });
}

export async function telaTermos(_parametro, ctx) {
  ctx.carregando();
  const [versao, situacao] = await Promise.all([api("/termos"), api("/termos/situacao")]);
  if (situacao.aceita) return irPara("descobrir");
  const data = new Date(`${versao.versao}T12:00:00`).toLocaleDateString("pt-BR");
  const botao = h("button", { type: "button", onclick: async () => {
    botao.disabled = true;
    try {
      await api("/termos/aceitar", { metodo: "POST", corpo: { versao: versao.versao } });
      avisar("Obrigado! Tudo certo.");
      irPara("descobrir");
    } catch (e) { avisar(e.message); botao.disabled = false; }
  } }, "Li e aceito");

  ctx.mostrar(h("h1", {}, situacao.versao_aceita ? "Os termos mudaram" : "Termos e privacidade"),
    h("section", { class: "cartao" },
      h("p", {}, situacao.versao_aceita
        ? `Atualizamos os termos de uso e a política de privacidade (versão de ${data}). Para continuar, leia e aceite.`
        : "Antes de ver perfis, leia e aceite os termos de uso e a política de privacidade."),
      h("ul", { class: "lista-simples" },
        h("li", {}, "Guardamos o mínimo e protegemos o que é sensível com criptografia."),
        h("li", {}, "Seus dados sobre sexualidade são usados só para gerar compatibilidades, com o seu consentimento."),
        h("li", {}, "Você pode excluir tudo, na hora, em Conta.")),
      h("p", {}, h("a", { href: versao.termos_url, target: "_blank", rel: "noopener" }, "Termos de uso"), " · ",
        h("a", { href: versao.privacidade_url, target: "_blank", rel: "noopener" }, "Política de privacidade")),
      h("div", { class: "acoes" }, botao)),
    h("p", { class: "nota" }, "Não concorda? Você pode ", h("a", { href: "#/conta" }, "excluir sua conta"), " agora."));
}
