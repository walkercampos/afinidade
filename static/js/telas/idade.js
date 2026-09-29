// Verificação de idade (ECA Digital, Lei 15.211/2025). Quem verifica é um provedor externo;
// o app guarda só "verificada em tal data". Nenhum documento ou foto fica com a gente.
import { api } from "../api.js";
import { avisar, h } from "../dom.js";
import { irPara } from "../roteador.js";

export async function telaIdade(_parametro, ctx) {
  ctx.carregando();
  const s = await api("/idade");
  if (s.verificada) {
    return ctx.mostrar(h("h1", {}, "Idade verificada"),
      h("section", { class: "cartao" },
        h("p", {}, "Tudo certo: sua idade já foi confirmada."),
        h("div", { class: "acoes" }, h("button", { type: "button", onclick: () => irPara("descobrir") }, "Ir para Descobrir"))));
  }
  const botao = h("button", { type: "button", disabled: !s.disponivel, onclick: async () => {
    botao.disabled = true;
    try {
      const { url } = await api("/idade/iniciar", { metodo: "POST" });
      location.assign(url);
    } catch (e) {
      avisar(e.message);
      botao.disabled = false;
    }
  } }, s.pendente ? "Continuar a verificação" : "Verificar minha idade");

  ctx.mostrar(h("h1", {}, "Confirme sua idade"),
    h("section", { class: "cartao" },
      h("p", {}, "Por lei (ECA Digital), só pessoas adultas com idade confirmada podem ver perfis, curtir e conversar."),
      h("ul", { class: "lista-simples" },
        h("li", {}, "A verificação é feita por uma empresa especializada: uma selfie com prova de vida."),
        h("li", {}, "O Afinidade recebe só o resultado (maior de idade: sim ou não)."),
        h("li", {}, "Nenhuma foto, documento ou CPF fica guardado aqui.")),
      !s.disponivel && h("p", { class: "nota" }, "A verificação está indisponível no momento. Tente mais tarde."),
      h("div", { class: "acoes" }, botao)),
    h("p", { class: "nota" }, "Enquanto isso, você pode montar seu perfil. ", h("a", { href: "#/perfil" }, "Ir para o perfil")));
}

/** "Página do provedor" de mentira: só existe em desenvolvimento (a API recusa em produção). */
export async function telaIdadeSimulada(sessao, ctx) {
  const concluir = (aprovar) => async () => {
    try {
      await api(`/idade/simulado/${encodeURIComponent(sessao)}`, { metodo: "POST", corpo: { aprovar } });
      avisar(aprovar ? "Idade confirmada (simulação)" : "Verificação recusada (simulação)");
    } catch (e) { avisar(e.message); }
    irPara("idade");
  };
  ctx.mostrar(h("h1", {}, "Provedor simulado"),
    h("section", { class: "cartao" },
      h("p", { class: "nota" }, "Esta tela só existe em desenvolvimento e faz o papel da empresa que verifica a idade."),
      h("div", { class: "acoes" },
        h("button", { type: "button", class: "secundario", onclick: concluir(false) }, "Recusar"),
        h("button", { type: "button", onclick: concluir(true) }, "Aprovar"))));
}
