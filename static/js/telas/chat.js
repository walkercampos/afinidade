// Chat efêmero: cada mensagem some 5 minutos depois de lida, para os dois lados.
// O servidor para de devolvê-la no instante em que expira; aqui ela também sai da tela.
import { api, carregarCatalogo } from "../api.js";
import { acoesDeSeguranca } from "../componentes.js";
import { formulario, h } from "../dom.js";
import { aoSairDaTela, irPara } from "../roteador.js";
import { formatarRestante, msAte } from "../util.js";

const INTERVALO_MS = 3000;

export async function telaChat(outroId, ctx) {
  if (!outroId) return irPara("conexoes");
  await carregarCatalogo();
  const conversa = (await api("/conversas")).find((c) => c.perfil.id === outroId);
  if (!conversa) return irPara("conexoes");

  const lista = h("ol", { class: "mensagens", "aria-live": "polite" });
  const vazio = h("p", { class: "vazio" }, "Nenhuma mensagem. As mensagens somem 5 minutos depois de lidas.");
  const exibidas = new Map(); // id -> { el, contador, expiraEm }

  function desenhar(m) {
    let item = exibidas.get(m.id);
    if (!item) {
      const contador = h("small", { class: "expira" });
      const el = h("li", { class: m.minha ? "msg minha" : "msg" }, h("p", {}, m.texto), contador);
      item = { el, contador, expiraEm: null };
      exibidas.set(m.id, item);
      lista.append(el);
    }
    item.expiraEm = m.expira_em;
  }

  function atualizarRelogios() {
    for (const [id, item] of exibidas) {
      if (!item.expiraEm) {
        item.contador.textContent = item.el.classList.contains("minha") ? "não lida" : "";
        continue;
      }
      const resta = msAte(item.expiraEm);
      if (resta <= 0) { item.el.remove(); exibidas.delete(id); } else item.contador.textContent = `some em ${formatarRestante(resta)}`;
    }
    vazio.hidden = exibidas.size > 0;
  }

  async function sincronizar() {
    if (document.hidden) return; // não marca como lida o que ninguém está vendo
    const mensagens = await api(`/conversas/${outroId}/mensagens?limite=100`);
    const ids = new Set(mensagens.map((m) => m.id));
    for (const [id, item] of exibidas) if (!ids.has(id)) { item.el.remove(); exibidas.delete(id); }
    mensagens.forEach(desenhar);
    atualizarRelogios();
  }

  const campo = h("textarea", { name: "texto", required: true, maxlength: 2000, rows: 2, "aria-label": "Mensagem" });
  const envio = formulario(async (f) => {
    const m = await api(`/conversas/${outroId}/mensagens`, { metodo: "POST", corpo: { texto: f.get("texto") } });
    campo.value = "";
    desenhar(m);
    atualizarRelogios();
    lista.lastElementChild?.scrollIntoView({ block: "end" });
  }, campo, h("div", { class: "acoes" }, h("button", { type: "submit" }, "Enviar")));

  const cabecalho = h("div", { class: "cartao" });
  cabecalho.append(
    h("div", { class: "nome" }, conversa.perfil.nome_exibicao),
    h("p", { class: "nota" }, "Mensagens cifradas no servidor e apagadas 5 minutos depois de lidas."),
    h("div", { class: "acoes" },
      ...acoesDeSeguranca(outroId, () => cabecalho, { comMensagens: true }),
      h("button", { type: "button", class: "secundario", onclick: async () => {
        if (!confirm("Apagar agora todas as mensagens que você enviou nesta conversa?")) return;
        await api(`/conversas/${outroId}/mensagens`, { metodo: "DELETE" });
        await sincronizar();
      } }, "Apagar as minhas")),
  );

  ctx.mostrar(h("h1", {}, "Conversa"), cabecalho, vazio, lista, envio);
  await sincronizar();
  if (!ctx.ativa()) return; // a pessoa saiu enquanto carregava: não deixa timers órfãos
  const busca = setInterval(() => sincronizar().catch(() => {}), INTERVALO_MS);
  const relogio = setInterval(atualizarRelogios, 1000);
  aoSairDaTela(() => { clearInterval(busca); clearInterval(relogio); });
}
