import { encerrarSessaoSemEsperar } from "./api.js";
import { discretoAtual } from "./discricao.js";
import { executarPanico } from "./util.js";

// Apaga tudo o que o site guardou, menos o modo discreto (quando ligado): senão a próxima
// abertura mostraria "Afinidade" na aba antes do login, justamente o que a pessoa quer evitar.
const localPreservandoDiscricao = {
  clear() {
    const discreto = discretoAtual();
    window.localStorage.clear();
    if (discreto) window.localStorage.setItem("afinidade.discreto", "1");
  },
};

function acionar() {
  executarPanico({
    armazenamentos: [localPreservandoDiscricao, window.sessionStorage],
    limparTela: () => {
      document.title = "Google";
      document.body.replaceChildren();
    },
    encerrarSessao: encerrarSessaoSemEsperar,
    navegar: (url) => window.location.replace(url),
  });
}

/** Botão flutuante + tecla ESC, ativos em todas as telas (inclusive no login). */
export function instalarPanico() {
  document.getElementById("panico").addEventListener("click", acionar);
  // capture: roda antes de qualquer outro handler, mesmo com foco num campo de texto
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { ev.preventDefault(); acionar(); }
  }, { capture: true });
}
