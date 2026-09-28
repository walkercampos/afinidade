import { api, carregarCatalogo } from "../api.js";
import { acoesDeSeguranca, cartaoPerfil } from "../componentes.js";
import { h } from "../dom.js";
import { irPara } from "../roteador.js";

export async function telaConexoes(_parametro, ctx) {
  ctx.carregando();
  await carregarCatalogo();
  const conversas = await api("/conversas");
  ctx.mostrar(h("h1", {}, "Conexões"),
    conversas.length
      ? conversas.map(({ perfil, nao_lidas: naoLidas }) => {
        const cartao = cartaoPerfil(perfil, null, {
          acoes: [
            ...acoesDeSeguranca(perfil.id, () => cartao, { comMensagens: true }),
            h("button", { type: "button", onclick: () => irPara(`chat/${perfil.id}`) },
              naoLidas ? `Conversar (${naoLidas} nova${naoLidas > 1 ? "s" : ""})` : "Conversar"),
          ],
        });
        return cartao;
      })
      : h("p", { class: "vazio" }, "Quando alguém que você curtiu curtir você de volta, aparece aqui."));
}
