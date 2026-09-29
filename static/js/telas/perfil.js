import { api, carregarCatalogo, enviarArquivo } from "../api.js";
import { avisar, formulario, h } from "../dom.js";
import { irPara } from "../roteador.js";
import { distanciaDoIndice, indiceDaDistancia, PARADAS_DISTANCIA, rotuloDistancia } from "../util.js";

const NIVEIS = [["quero", "Quero"], ["curioso", "Curioso"], ["limite_absoluto", "Limite"]];

function seletorDeInteresses(tags, atual) {
  const niveis = new Map();
  for (const [nivel] of NIVEIS) for (const s of atual?.tags_interesses[nivel] ?? []) niveis.set(s, nivel);
  const linhas = tags.map((t) => {
    const botoes = NIVEIS.map(([nivel, texto]) => h("button", {
      type: "button", "data-nivel": nivel, "aria-pressed": niveis.get(t.slug) === nivel,
      onclick: () => {
        const ativo = niveis.get(t.slug) === nivel;
        if (ativo) niveis.delete(t.slug); else niveis.set(t.slug, nivel);
        botoes.forEach((b) => b.setAttribute("aria-pressed", !ativo && b.dataset.nivel === nivel));
      },
    }, texto));
    return h("div", { class: "tag-linha" }, h("span", {}, t.rotulo),
      h("div", { class: "nivel", role: "group", "aria-label": t.rotulo }, botoes));
  });
  const valor = () => {
    const r = { quero: [], curioso: [], limite_absoluto: [] };
    for (const [slug, nivel] of niveis) r[nivel].push(slug);
    return r;
  };
  return { elemento: h("div", { class: "cartao" }, linhas), valor };
}

function formPerfil(generos, tags, atual, ctx) {
  const interesses = seletorDeInteresses(tags, atual);
  const bio = h("textarea", { id: "bio", name: "bio", maxlength: 500 });
  bio.value = atual?.bio ?? "";
  return formulario(async (f) => {
    const busca = f.getAll("busca_por");
    if (!busca.length) throw new Error("Escolha pelo menos um gênero que você busca.");
    await api("/perfil", { metodo: "PUT", corpo: {
      nome_exibicao: f.get("nome"), bio: f.get("bio") || null, genero: f.get("genero"), busca_por: busca,
      tags_interesses: interesses.valor(), visivel: f.get("visivel") === "on",
    } });
    avisar("Perfil salvo");
    // Só recarrega se a pessoa ainda estiver aqui (não a puxa de volta de outra tela).
    if (!atual && ctx.ativa()) irPara("perfil");
  },
  h("label", { for: "nome" }, "Nome de exibição"),
  h("input", { id: "nome", name: "nome", type: "text", required: true, maxlength: 40, value: atual?.nome_exibicao ?? "" }),
  h("label", { for: "bio" }, "Sobre você"), bio,
  h("p", { class: "nota" }, "Evite informações que identifiquem você: nome real, local de trabalho, @ de outras redes."),
  h("label", { for: "genero" }, "Seu gênero"),
  h("select", { id: "genero", name: "genero", required: true },
    h("option", { value: "" }, "Selecione…"),
    generos.map((g) => h("option", { value: g.slug, selected: atual?.genero === g.slug }, g.rotulo))),
  h("label", {}, "Você busca"),
  h("div", { class: "grade-generos" }, generos.map((g) => h("label", { class: "check" },
    h("input", { type: "checkbox", name: "busca_por", value: g.slug, checked: atual?.busca_por.includes(g.slug) }), g.rotulo))),
  h("h2", {}, "Interesses"),
  h("p", { class: "nota" }, "Quero = pratica e gosta · Curioso = aberto(a) a explorar · Limite = nunca. Seus limites não aparecem para ninguém: servem só para esconder pessoas incompatíveis."),
  interesses.elemento,
  h("label", { class: "check" }, h("input", { type: "checkbox", name: "visivel", checked: atual ? atual.visivel : true }),
    "Perfil visível na descoberta"),
  h("div", { class: "acoes" }, h("button", { type: "submit" }, "Salvar perfil")));
}

async function secaoFotos() {
  const fotos = await api("/fotos");
  const arquivo = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp", hidden: true, onchange: async () => {
    const f = arquivo.files[0];
    if (!f) return;
    try { await enviarArquivo("/fotos", f); avisar("Foto enviada"); } catch (e) { avisar(e.message); }
    secao.replaceWith(await secaoFotos());
  } });
  const secao = h("section", { class: "cartao" },
    h("h2", {}, "Suas fotos"),
    h("p", { class: "nota" }, "Localização, modelo do celular e outros dados escondidos na foto são apagados no envio. Quem você não autorizar vê só uma versão borrada."),
    h("div", { class: "fotos" }, fotos.map((f) => h("div", { class: "moldura" },
      h("img", { src: f.url, alt: "Sua foto", class: "foto" }),
      h("button", { type: "button", class: "secundario remover", onclick: async () => {
        await api(`/fotos/${f.id}`, { metodo: "DELETE" });
        secao.replaceWith(await secaoFotos());
      } }, "Remover")))),
    fotos.length < 3 && h("div", { class: "acoes" },
      h("button", { type: "button", class: "secundario", onclick: () => arquivo.click() }, "Adicionar foto")),
    arquivo);
  return secao;
}

async function secaoPedidos() {
  const pedidos = await api("/fotos/solicitacoes");
  if (!pedidos.length) return null;
  const secao = h("section", { class: "cartao" }, h("h2", {}, "Pedidos para ver suas fotos"),
    pedidos.map(({ visualizador }) => h("div", { class: "tag-linha" },
      h("span", {}, visualizador.nome_exibicao),
      h("div", { class: "nivel" }, [["Negar", false], ["Aprovar", true]].map(([texto, aprovar]) =>
        h("button", { type: "button", onclick: async (ev) => {
          await api(`/fotos/solicitacoes/${visualizador.id}`, { metodo: "POST", corpo: { aprovar } });
          ev.target.closest(".tag-linha").remove();
          avisar(aprovar ? "Acesso liberado" : "Pedido negado");
        } }, texto))))));
  return secao;
}

function secaoLocalizacao(atual) {
  const ativa = Boolean(atual.localizacao.regiao);
  const status = h("p", { class: "nota" }, ativa
    ? "Localização aproximada ativa (região de ~5 km)." : "Sem localização: você vê e é visto(a) sem filtro de distância.");
  const rotulo = h("output", { for: "distancia", class: "valor-barra" }, rotuloDistancia(atual.localizacao.distancia_max_km));
  const barra = h("input", {
    id: "distancia", type: "range", min: 0, max: PARADAS_DISTANCIA.length - 1, step: 1,
    value: indiceDaDistancia(atual.localizacao.distancia_max_km), disabled: !ativa,
    "aria-describedby": "distancia-nota",
  });
  const valor = () => distanciaDoIndice(barra.value);
  const mostrarValor = () => {
    rotulo.textContent = rotuloDistancia(valor());
    barra.setAttribute("aria-valuetext", rotulo.textContent);
  };
  mostrarValor();
  barra.addEventListener("input", mostrarValor);
  // Salva ao soltar a barra (não a cada pixel arrastado).
  barra.addEventListener("change", async () => {
    await api("/perfil/distancia", { metodo: "PUT", corpo: { distancia_max_km: valor() } });
    avisar(`Distância salva: ${rotuloDistancia(valor()).toLowerCase()}`);
  });
  return h("section", { class: "cartao" },
    h("h2", {}, "Localização"),
    h("p", { class: "nota" }, "O app guarda só um quadrado de ~5 km; sua posição exata é descartada. Os outros veem apenas \"até N km\"."),
    status,
    h("div", { class: "barra-distancia" },
      h("label", { for: "distancia" }, "Distância máxima"), rotulo),
    barra,
    h("p", { class: "nota", id: "distancia-nota" }, ativa
      ? "Arraste para escolher até onde quer ver pessoas. Vale para os dois lados: quem escolheu um raio menor também decide."
      : "Ative a localização para escolher uma distância."),
    h("div", { class: "acoes" },
      ativa && h("button", { type: "button", class: "secundario", onclick: async () => {
        await api("/perfil/localizacao", { metodo: "DELETE" });
        irPara("perfil");
      } }, "Remover"),
      h("button", { type: "button", onclick: () => {
        if (!navigator.geolocation) return avisar("Seu navegador não oferece localização.");
        navigator.geolocation.getCurrentPosition(async ({ coords }) => {
          await api("/perfil/localizacao", { metodo: "PUT", corpo: {
            lat: coords.latitude, lon: coords.longitude, distancia_max_km: valor(),
          } });
          avisar("Localização aproximada salva");
          irPara("perfil");
        }, () => avisar("Não foi possível obter a localização."), { enableHighAccuracy: false, maximumAge: 600000 });
      } }, ativa ? "Atualizar minha região" : "Usar minha localização")));
}

export async function telaPerfil(_parametro, ctx) {
  ctx.carregando();
  const { generos, tags } = await carregarCatalogo();
  let atual = null;
  try { atual = await api("/perfil"); } catch (e) { if (e.status !== 404) throw e; }
  if (!atual) return ctx.mostrar(h("h1", {}, "Crie seu perfil"), formPerfil(generos, tags, null, ctx));
  ctx.mostrar(h("h1", {}, "Seu perfil"), await secaoPedidos(), await secaoFotos(), secaoLocalizacao(atual),
    formPerfil(generos, tags, atual, ctx),
    h("p", { class: "nota" }, h("a", { href: "#/descobrir" }, "Ir para Descobrir →")));
}
