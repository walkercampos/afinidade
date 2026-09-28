// Funções puras (sem DOM nem rede): testadas com `node --test` em tests/js/.

export const DESTINO_PANICO = "https://www.google.com/";

/** Executa o botão de pânico. O ambiente é injetado para poder ser testado. */
export function executarPanico({ armazenamentos, limparTela, encerrarSessao, navegar }) {
  // 1) apaga a tela primeiro: nada fica visível nem por um quadro
  try { limparTela(); } catch { /* segue */ }
  // 2) limpa tudo o que o navegador guardou para este site
  for (const a of armazenamentos) {
    try { a.clear(); } catch { /* modo privado ou bloqueado: segue */ }
  }
  // 3) derruba a sessão no servidor sem esperar a resposta
  try { encerrarSessao(); } catch { /* segue */ }
  // 4) troca a página atual (replace: o "voltar" não retorna para o app)
  navegar(DESTINO_PANICO);
}

/** Milissegundos até `iso` (negativo se já passou). */
export function msAte(iso, agora = Date.now()) {
  return Date.parse(iso) - agora;
}

/** "4:05" a partir de milissegundos; nunca negativo. */
export function formatarRestante(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function descreverDistancia(km) {
  return km == null ? null : `até ${km} km`;
}

/** Texto amigável a partir do corpo de erro do FastAPI. */
export function mensagemDeErro(dados) {
  const d = dados?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((e) => String(e.msg).replace(/^Value error, /, "")).join(" · ");
  return "Algo deu errado. Tente de novo.";
}

/** Separa "#/chat/<id>" em { rota: "chat", parametro: "<id>" }. */
export function lerRota(hash) {
  const [rota = "", parametro = null] = hash.replace(/^#\/?/, "").split("/");
  return { rota: rota || "descobrir", parametro };
}

/**
 * Achata listas e descarta vazios (null, undefined, false) antes de inserir no DOM.
 * Sem isso, um array vira o texto "[object HTMLElement]" e um null vira "null".
 */
export function normalizarFilhos(filhos) {
  return filhos.flat(Infinity).filter((f) => f != null && f !== false);
}
