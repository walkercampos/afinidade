// Painel de moderação (Parte 7). Só aparece para quem tem o papel de moderador; a API responde 404
// para qualquer outra pessoa. Mostra a fila (casos graves primeiro), as denúncias e as evidências,
// e permite banir, restaurar e enviar um aviso por e-mail sem nunca ver o endereço.
import { api } from "../api.js";
import { avisar, formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";

const MOTIVOS = {
  menor_de_idade: "Menor de idade", conteudo_ilegal: "Conteúdo ilegal", assedio: "Assédio",
  perfil_falso: "Perfil falso", spam: "Spam", discurso_de_odio: "Discurso de ódio", outro: "Outro",
};
const GRAVES = new Set(["menor_de_idade", "conteudo_ilegal"]);
const quando = (iso) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

function blocoDenuncia(d) {
  return h("li", { class: GRAVES.has(d.motivo) ? "denuncia-item grave" : "denuncia-item" },
    h("strong", {}, MOTIVOS[d.motivo] ?? d.motivo), h("small", {}, ` · ${quando(d.criado_em)}`),
    d.detalhes && h("p", {}, d.detalhes),
    d.evidencias && h("details", {}, h("summary", {}, `Mensagens anexadas (${d.evidencias.length})`),
      h("ol", { class: "evidencias" }, d.evidencias.map((m) =>
        h("li", { class: m.de === "denunciado" ? "denunciado" : "" }, h("small", {}, `${m.de}: `), m.texto)))));
}

function cartaoCaso(caso) {
  const decidir = (acao) => async () => {
    const observacao = prompt(acao === "banir" ? "Motivo do banimento (fica no registro):" : "Observação (opcional):", "");
    if (observacao === null) return;
    await api(`/moderacao/contas/${caso.conta_id}/decisao`, { metodo: "POST", corpo: { acao, observacao: observacao || null } });
    avisar(acao === "banir" ? "Conta banida" : "Conta restaurada");
    irPara("moderacao");
  };
  const aviso = formulario(async (f) => {
    await api(`/moderacao/contas/${caso.conta_id}/aviso`, { metodo: "POST",
      corpo: { assunto: f.get("assunto"), mensagem: f.get("mensagem") } });
    avisar("Aviso enviado (o endereço não é mostrado a você)");
  },
  h("label", {}, "Assunto", h("input", { name: "assunto", required: true, minlength: 3, maxlength: 120 })),
  h("label", {}, "Mensagem", h("textarea", { name: "mensagem", required: true, minlength: 3, maxlength: 4000 })),
  h("div", { class: "acoes" }, h("button", { type: "submit", class: "secundario" }, "Enviar aviso por e-mail")));

  const p = caso.perfil;
  return h("section", { class: "cartao caso" },
    h("header", {},
      h("div", {}, h("div", { class: "nome" }, `@${caso.handle}`),
        h("div", { class: "genero" }, caso.situacao === "em_revisao" ? "Em revisão (oculta)" : "Ativa")),
      h("span", { class: "contador" }, `${caso.denuncias.length} denúncia(s)`)),
    p && h("div", { class: "perfil-moderado" },
      h("p", {}, h("strong", {}, p.nome_exibicao), ` · ${p.genero}`),
      p.bio && h("p", { class: "bio" }, p.bio)),
    h("ul", { class: "denuncias" }, caso.denuncias.map(blocoDenuncia)),
    h("div", { class: "acoes" },
      h("button", { type: "button", class: "secundario", onclick: decidir("restaurar") }, "Restaurar"),
      h("button", { type: "button", class: "perigo", onclick: decidir("banir") }, "Banir")),
    h("details", {}, h("summary", {}, "Enviar aviso à pessoa"), aviso));
}

export async function telaModeracao(_parametro, ctx) {
  ctx.carregando();
  let fila;
  try { fila = await api("/moderacao/fila"); } catch (e) {
    if (e.status === 404) return irPara("descobrir"); // não é moderador(a)
    throw e;
  }
  ctx.mostrar(h("h1", {}, "Moderação"),
    h("p", { class: "nota" }, "Casos graves primeiro. Cada decisão fica registrada com quem decidiu e por quê."),
    fila.length ? fila.map(cartaoCaso) : h("p", { class: "vazio" }, "Nenhum caso na fila. 🎉"));
}
