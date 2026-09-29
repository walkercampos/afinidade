// Encontro seguro (Parte 9): quem você vai encontrar, onde e até quando fazer o check-in. Se o
// check-in não vier, o contato de confiança recebe um e-mail com os detalhes.
import { api } from "../api.js";
import { avisar, formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";

const SITUACOES = {
  agendado: "Aguardando seu check-in",
  confirmado_ok: "Check-in feito: tudo bem",
  alerta_enviado: "Alerta enviado ao contato de confiança",
  cancelado: "Cancelado",
};

/** Valor para <input type="datetime-local"> no fuso do aparelho. */
function paraCampo(data) {
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

const quando = (iso) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

function cartaoEmergencia() {
  return h("section", { class: "cartao emergencia" },
    h("h2", {}, "Em perigo agora?"),
    h("div", { class: "acoes" },
      h("a", { class: "botao perigo", href: "tel:190" }, "Ligar 190 · Polícia"),
      h("a", { class: "botao secundario", href: "tel:180" }, "Ligar 180 · Violência contra a mulher")));
}

function cartaoEncontro(e) {
  const acoes = e.situacao === "agendado" ? h("div", { class: "acoes" },
    h("button", { type: "button", class: "secundario", onclick: async () => {
      await api(`/encontros/${e.id}/cancelar`, { metodo: "POST" });
      irPara("encontros");
    } }, "Cancelar"),
    h("button", { type: "button", onclick: async () => {
      await api(`/encontros/${e.id}/checkin`, { metodo: "POST" });
      avisar("Check-in feito. Que bom!");
      irPara("encontros");
    } }, "Estou bem")) : null;
  return h("section", { class: "cartao" },
    h("h2", {}, e.local),
    h("p", { class: "nota" }, `${quando(e.inicio_em)} · check-in até ${quando(e.checkin_ate)}`),
    e.com_handle && h("p", {}, `Com ${e.com_nome} (@${e.com_handle})`),
    h("p", { class: "nota" }, `Contato de confiança: ${e.contato_email}`),
    h("p", { class: `situacao ${e.situacao}` }, SITUACOES[e.situacao] ?? e.situacao),
    acoes);
}

export async function telaEncontros(comQuem, ctx) {
  ctx.carregando();
  const [lista, conexoes] = await Promise.all([api("/encontros"), api("/conexoes")]);
  const agora = new Date();
  const inicio = new Date(agora.getTime() + 60 * 60_000);
  const checkin = new Date(inicio.getTime() + 3 * 60 * 60_000);

  const form = formulario(async (f) => {
    await api("/encontros", { metodo: "POST", corpo: {
      com: f.get("com") || null,
      local: f.get("local"),
      observacoes: f.get("observacoes") ?? "",
      como_te_conhecem: f.get("como_te_conhecem") ?? "",
      contato_email: f.get("contato_email"),
      inicio_em: new Date(f.get("inicio")).toISOString(),
      checkin_ate: new Date(f.get("checkin")).toISOString(),
    } });
    avisar("Encontro registrado. Avisamos seu contato de confiança.");
    irPara("encontros");
  },
  h("label", { for: "com" }, "Com quem"),
  h("select", { id: "com", name: "com" },
    h("option", { value: "" }, "Prefiro não dizer"),
    conexoes.map((c) => h("option", { value: c.id, selected: c.id === comQuem }, c.nome_exibicao))),
  h("label", { for: "local" }, "Onde"),
  h("input", { id: "local", name: "local", required: true, minlength: 2, maxlength: 200,
    placeholder: "Nome e endereço do lugar" }),
  h("div", { class: "linha-campos" },
    h("div", {}, h("label", { for: "inicio" }, "Começa"),
      h("input", { id: "inicio", name: "inicio", type: "datetime-local", required: true, value: paraCampo(inicio) })),
    h("div", {}, h("label", { for: "checkin" }, "Check-in até"),
      h("input", { id: "checkin", name: "checkin", type: "datetime-local", required: true, value: paraCampo(checkin) }))),
  h("p", { class: "nota" }, "Se você não tocar em \"Estou bem\" até o check-in, seu contato recebe o local, o horário e com quem você está."),
  h("label", { for: "contato_email" }, "E-mail do contato de confiança"),
  h("input", { id: "contato_email", name: "contato_email", type: "email", required: true, autocomplete: "off",
    autocapitalize: "none", spellcheck: "false", maxlength: 254 }),
  h("label", { for: "como_te_conhecem" }, "Como essa pessoa conhece você"),
  h("input", { id: "como_te_conhecem", name: "como_te_conhecem", maxlength: 60, placeholder: "ex.: Ana, sua irmã" }),
  h("label", { for: "observacoes" }, "Observações (opcional)"),
  h("textarea", { id: "observacoes", name: "observacoes", maxlength: 500, placeholder: "ex.: volto de táxi às 23 h" }),
  h("p", { class: "nota" }, "Tudo fica guardado criptografado e é apagado 30 dias depois do encontro."),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Registrar encontro")));

  ctx.mostrar(h("h1", {}, "Encontro seguro"),
    cartaoEmergencia(),
    h("section", { class: "cartao" }, h("h2", {}, "Novo encontro"), form),
    lista.length ? lista.map(cartaoEncontro) : h("p", { class: "vazio" }, "Nenhum encontro registrado."));
}
