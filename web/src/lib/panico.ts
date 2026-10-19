// Saída rápida: botão vermelho ou tecla ESC, em qualquer tela (inclusive no login).
import { encerrarSessaoSemEsperar } from "./api";
import { CHAVE_DISCRETO, discretoAtual } from "./discricao";
import { DESTINO_PANICO } from "./util";

export function acionarPanico() {
  // 1) apaga a tela primeiro: nada fica visível nem por um quadro
  try {
    document.title = "Google";
    document.body.replaceChildren();
  } catch { /* segue */ }
  // 2) limpa o que o site guardou, menos o modo discreto (senão a próxima abertura mostraria
  //    "Afinidade" na aba antes do login, justamente o que a pessoa quer evitar)
  try {
    const discreto = discretoAtual();
    localStorage.clear();
    if (discreto) localStorage.setItem(CHAVE_DISCRETO, "1");
  } catch { /* segue */ }
  try { sessionStorage.clear(); } catch { /* segue */ }
  // 3) derruba a sessão no servidor sem esperar a resposta
  try { encerrarSessaoSemEsperar(); } catch { /* segue */ }
  // 4) replace: o "voltar" não retorna para o app
  location.replace(DESTINO_PANICO);
}

export function instalarAtalhoDoPanico() {
  // capture: roda antes de qualquer outro handler, mesmo com foco num campo de texto
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { ev.preventDefault(); acionarPanico(); }
  }, { capture: true });
}
