// Peças de interface reaproveitadas por várias telas.
import { api, rotulo } from "./api.js";
import { avisar, h } from "./dom.js";
import { descreverDistancia } from "./util.js";

export function listaDeTags(slugs, destacadas = new Set()) {
  return h("ul", { class: "chips" },
    slugs.map((s) => h("li", { class: destacadas.has(s) ? "chip comum" : "chip" }, rotulo(s))));
}

/**
 * Fotos de outra pessoa. Quem não foi autorizado recebe do SERVIDOR uma versão já
 * borrada (a nítida nunca chega ao navegador); o blur do CSS só suaviza a miniatura.
 */
export function galeria(perfilId, fotos) {
  if (!fotos?.length) return null;
  const nitidas = fotos.every((f) => f.nitida);
  const pedido = h("p", { class: "nota" });
  const botao = !nitidas && h("button", {
    type: "button", class: "secundario",
    onclick: async () => {
      const { status } = await api(`/perfis/${perfilId}/fotos/solicitar`, { metodo: "POST" });
      botao.remove();
      pedido.textContent = status === "negado" ? "O acesso não foi liberado." : "Pedido enviado. As fotos ficam nítidas se a pessoa aprovar.";
    },
  }, "Pedir para ver as fotos");
  return h("div", { class: "galeria" },
    h("div", { class: "fotos" }, fotos.map((f) => h("div", { class: "moldura" },
      h("img", { src: f.url, alt: "Foto do perfil", loading: "lazy", class: f.nitida ? "foto" : "foto borrada" })))),
    botao, pedido);
}

const MOTIVOS = [
  ["assedio", "Assédio"], ["menor_de_idade", "Parece menor de idade"], ["perfil_falso", "Perfil falso"],
  ["spam", "Spam ou golpe"], ["conteudo_ilegal", "Conteúdo ilegal"], ["discurso_de_odio", "Discurso de ódio"],
  ["outro", "Outro motivo"],
];

/** Formulário de denúncia embutido no cartão. Denunciar também bloqueia. */
export function formDenuncia(perfilId, { comMensagens = false, aoConcluir }) {
  const motivo = h("select", { "aria-label": "Motivo" }, MOTIVOS.map(([v, t]) => h("option", { value: v }, t)));
  const detalhes = h("textarea", { maxlength: 1000, placeholder: "Detalhes (opcional)", "aria-label": "Detalhes" });
  const anexar = comMensagens && h("input", { type: "checkbox", checked: true });
  return h("div", { class: "denuncia" },
    h("label", {}, "Denunciar"), motivo, detalhes,
    anexar && h("label", { class: "check" }, anexar, "Anexar as mensagens recentes como evidência"),
    h("p", { class: "nota" }, "A pessoa não fica sabendo quem denunciou. Vocês deixam de se ver."),
    h("div", { class: "acoes" }, h("button", { type: "button", class: "perigo", onclick: async () => {
      await api(`/perfis/${perfilId}/denunciar`, { metodo: "POST", corpo: {
        motivo: motivo.value, detalhes: detalhes.value || null, incluir_mensagens: Boolean(anexar?.checked),
      } });
      avisar("Denúncia enviada. Obrigado por proteger a comunidade.");
      aoConcluir?.();
    } }, "Enviar denúncia")));
}

export function cartaoPerfil(perfil, compat, { fotos, acoes } = {}) {
  const comuns = new Set(compat?.tags_em_comum ?? []);
  const distancia = descreverDistancia(compat?.distancia_km);
  return h("article", { class: "cartao" },
    h("header", {},
      h("div", {},
        h("div", { class: "nome" }, perfil.nome_exibicao),
        h("div", { class: "genero" }, [rotulo(perfil.genero), distancia].filter(Boolean).join(" · "))),
      compat && h("div", { class: "score" }, `${compat.score_mutuo}%`, h("small", {}, "afinidade"))),
    galeria(perfil.id, fotos),
    perfil.bio && h("p", { class: "bio" }, perfil.bio),
    perfil.quero.length > 0 && [h("h2", {}, "Quer"), listaDeTags(perfil.quero, comuns)],
    perfil.curioso.length > 0 && [h("h2", {}, "Curioso(a)"), listaDeTags(perfil.curioso, comuns)],
    acoes && h("div", { class: "acoes" }, acoes));
}

/** Botões "Bloquear" e "Denunciar" (o segundo abre o formulário dentro do cartão). */
export function acoesDeSeguranca(perfilId, obterCartao, { comMensagens = false } = {}) {
  return [
    h("button", { type: "button", class: "secundario", onclick: async () => {
      if (!confirm("Bloquear este perfil? Vocês deixam de se ver para sempre.")) return;
      await api(`/perfis/${perfilId}/bloquear`, { metodo: "POST" });
      obterCartao().remove();
      avisar("Perfil bloqueado");
    } }, "Bloquear"),
    h("button", { type: "button", class: "secundario", onclick: (ev) => {
      ev.currentTarget.disabled = true;
      const cartao = obterCartao();
      cartao.append(formDenuncia(perfilId, { comMensagens, aoConcluir: () => cartao.remove() }));
    } }, "Denunciar"),
  ];
}
