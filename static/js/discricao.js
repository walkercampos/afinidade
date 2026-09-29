// Aparência e discrição. O tema fica só neste aparelho; o modo discreto vem da conta e fica
// guardado aqui também, para valer desde o primeiro instante ao abrir o app (antes do login).
const CHAVE_TEMA = "afinidade.tema";      // "sistema" | "claro" | "escuro"
const CHAVE_DISCRETO = "afinidade.discreto";

function ler(chave) { try { return localStorage.getItem(chave); } catch { return null; } }
// Só guarda o que difere do padrão: quem nunca mexeu nisso não deixa nenhum rastro no navegador.
function gravar(chave, valor, padrao) {
  try {
    if (valor === padrao) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch { /* modo privado */ }
}

export function temaAtual() { return ler(CHAVE_TEMA) ?? "sistema"; }

export function aplicarTema(tema = temaAtual()) {
  gravar(CHAVE_TEMA, tema, "sistema");
  if (tema === "sistema") delete document.documentElement.dataset.tema;
  else document.documentElement.dataset.tema = tema;
}

export function discretoAtual() { return ler(CHAVE_DISCRETO) === "1"; }

/** Modo discreto: nome e ícone neutros na aba do navegador, no histórico e na tela inicial. */
export function aplicarDiscreto(ligado = discretoAtual()) {
  gravar(CHAVE_DISCRETO, ligado ? "1" : "0", "0");
  document.documentElement.toggleAttribute("data-discreto", ligado);
  document.title = ligado ? "Notas" : "Afinidade";
  const icone = document.querySelector("link[rel=icon]");
  if (icone) icone.href = ligado ? "icon-neutro.svg" : "icon.svg";
  // "Adicionar à tela inicial" usa o manifesto: no modo discreto, nome e ícone neutros.
  const manifesto = document.querySelector("link[rel=manifest]");
  if (manifesto) manifesto.href = ligado ? "manifest-neutro.webmanifest" : "manifest.webmanifest";
  const marca = document.querySelector(".marca");
  if (marca) marca.textContent = ligado ? "Notas" : "Afinidade";
}

/** Busca a preferência da conta sem incomodar quem não entrou (sem redirecionar no 401). */
export async function sincronizarDiscreto() {
  try {
    const r = await fetch("/api/conta/preferencias", { credentials: "same-origin" });
    if (r.ok) aplicarDiscreto((await r.json()).modo_discreto);
  } catch { /* sem rede: mantém o que estava guardado */ }
}
