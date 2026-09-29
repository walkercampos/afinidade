// Chat efêmero: cada mensagem some um tempo depois de lida (24 h por padrão), para os dois
// lados. O prazo é combinado entre as duas pessoas: uma propõe, a outra confirma, e o novo prazo
// vale para as mensagens enviadas a partir daí. O servidor para de devolver a mensagem no
// instante em que expira; aqui ela também sai da tela.
import { api, carregarCatalogo } from "../api.js";
import { acoesDeSeguranca } from "../componentes.js";
import { avisar, formulario, h } from "../dom.js";
import { aoSairDaTela, irPara } from "../roteador.js";
import { conectarAvisos } from "../tempo_real.js";
import { descreverPrazo, formatarRestante, msAte, rotuloPrazo } from "../util.js";

// Com o canal em tempo real aberto, a busca periódica vira só uma reserva.
const INTERVALO_SEM_AVISOS_MS = 3000;
const INTERVALO_COM_AVISOS_MS = 20000;

export async function telaChat(outroId, ctx) {
  if (!outroId) return irPara("conexoes");
  await carregarCatalogo();
  const conversa = (await api("/conversas")).find((c) => c.perfil.id === outroId);
  if (!conversa) return irPara("conexoes");

  const lista = h("ol", { class: "mensagens", "aria-live": "polite" });
  const vazio = h("p", { class: "vazio" }, "Nenhuma mensagem ainda.");
  const exibidas = new Map(); // id -> { el, contador, expiraEm, nuncaExpira }

  function desenhar(m) {
    let item = exibidas.get(m.id);
    if (!item) {
      const contador = h("small", { class: "expira" });
      const el = h("li", { class: m.minha ? "msg minha" : "msg" }, h("p", {}, m.texto), contador);
      item = { el, contador, expiraEm: null, nuncaExpira: false };
      exibidas.set(m.id, item);
      lista.append(el);
    }
    item.expiraEm = m.expira_em;
    item.nuncaExpira = m.ttl_minutos === null;
  }

  function atualizarRelogios() {
    for (const [id, item] of exibidas) {
      if (!item.expiraEm) {
        const minha = item.el.classList.contains("minha");
        item.contador.textContent = item.nuncaExpira ? "não some" : minha ? "não lida" : "";
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
    mostrarPrazo(await api(`/conversas/${outroId}/prazo`));
  }

  // ----- prazo da conversa -----
  const textoPrazo = h("p", { class: "nota" });
  const areaProposta = h("div", { class: "proposta-prazo", "aria-live": "polite" });
  const escolha = h("select", { "aria-label": "Novo prazo das mensagens" });
  const propor = h("button", { type: "button", class: "secundario" }, "Propor");
  let assinatura = ""; // evita redesenhar (e perder o foco do seletor) quando nada mudou

  // Cada chamada fica escrita por inteiro (o teste de contrato confere todas contra a API).
  async function acao(chamar, mensagem) {
    try {
      mostrarPrazo(await chamar() ?? await api(`/conversas/${outroId}/prazo`));
      if (mensagem) avisar(mensagem);
    } catch (e) {
      avisar(e.message);
    }
  }
  const desistirOuRecusar = () => acao(() => api(`/conversas/${outroId}/prazo/proposta`, { metodo: "DELETE" }));

  propor.addEventListener("click", () => {
    const valor = escolha.value === "nunca" ? null : Number(escolha.value);
    acao(() => api(`/conversas/${outroId}/prazo`, { metodo: "POST", corpo: { ttl_minutos: valor } }), "Proposta enviada");
  });

  function mostrarPrazo(s) {
    const nova = JSON.stringify(s);
    if (nova === assinatura) return;
    assinatura = nova;
    textoPrazo.textContent = descreverPrazo(s.ttl_minutos);
    escolha.replaceChildren(...s.opcoes.filter((o) => o !== s.ttl_minutos).map((o) =>
      h("option", { value: o ?? "nunca" }, o == null ? "Nunca somem" : `${rotuloPrazo(o)} depois de lidas`)));
    const p = s.proposta;
    if (!p) {
      areaProposta.replaceChildren(h("div", { class: "linha-prazo" }, escolha, propor));
    } else if (p.minha) {
      areaProposta.replaceChildren(
        h("p", {}, `Você propôs: ${rotuloPrazo(p.ttl_minutos)}. Esperando ${conversa.perfil.nome_exibicao} confirmar.`),
        h("div", { class: "acoes" }, h("button", { type: "button", class: "secundario",
          onclick: desistirOuRecusar }, "Desistir")));
    } else {
      areaProposta.replaceChildren(
        h("p", {}, `${conversa.perfil.nome_exibicao} propôs mudar para: ${rotuloPrazo(p.ttl_minutos)}. Vale para as próximas mensagens.`),
        h("div", { class: "acoes" },
          h("button", { type: "button", class: "secundario", onclick: desistirOuRecusar }, "Recusar"),
          h("button", { type: "button", onclick: () => acao(
            () => api(`/conversas/${outroId}/prazo/confirmar`, { metodo: "POST" }),
            "Prazo novo combinado. Vale para as próximas mensagens.") }, "Aceitar")));
    }
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
    textoPrazo,
    h("details", { class: "prazo" }, h("summary", {}, "Prazo das mensagens"),
      h("p", { class: "nota" }, "Mudar o prazo precisa das duas pessoas e vale só para as mensagens enviadas depois."),
      areaProposta),
    h("div", { class: "acoes" },
      ...acoesDeSeguranca(outroId, () => cabecalho, { comMensagens: true }),
      h("button", { type: "button", class: "secundario", onclick: () => irPara(`encontros/${outroId}`) }, "Encontro seguro"),
      h("button", { type: "button", class: "secundario", onclick: async () => {
        if (!confirm("Apagar agora todas as mensagens que você enviou nesta conversa?")) return;
        await api(`/conversas/${outroId}/mensagens`, { metodo: "DELETE" });
        await sincronizar();
      } }, "Apagar as minhas")),
  );

  ctx.mostrar(h("h1", {}, "Conversa"), cabecalho, vazio, lista, envio);
  await sincronizar();
  if (!ctx.ativa()) return; // a pessoa saiu enquanto carregava: não deixa timers órfãos
  const avisos = conectarAvisos((aviso) => {
    if (aviso.conversa === outroId) sincronizar().catch(() => {});
  });
  let ultimaBusca = Date.now();
  const busca = setInterval(() => {
    const intervalo = avisos.conectado() ? INTERVALO_COM_AVISOS_MS : INTERVALO_SEM_AVISOS_MS;
    if (Date.now() - ultimaBusca < intervalo) return;
    ultimaBusca = Date.now();
    sincronizar().catch(() => {});
  }, 1000);
  const relogio = setInterval(atualizarRelogios, 1000);
  aoSairDaTela(() => { clearInterval(busca); clearInterval(relogio); avisos.fechar(); });
}
