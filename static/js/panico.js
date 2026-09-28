import { encerrarSessaoSemEsperar } from "./api.js";
import { executarPanico } from "./util.js";

function acionar() {
  executarPanico({
    armazenamentos: [window.localStorage, window.sessionStorage],
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
