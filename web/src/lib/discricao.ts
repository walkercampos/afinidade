// Aparência e discrição. O tema fica só neste aparelho; o modo discreto vem da conta e fica
// guardado aqui também, para valer desde o primeiro instante ao abrir o app (antes do login).
import { useSyncExternalStore } from "react";

export type Tema = "sistema" | "claro" | "escuro";
const CHAVE_TEMA = "afinidade.tema";
export const CHAVE_DISCRETO = "afinidade.discreto";

function ler(chave: string) { try { return localStorage.getItem(chave); } catch { return null; } }
// Só guarda o que difere do padrão: quem nunca mexeu nisso não deixa rastro no navegador.
function gravar(chave: string, valor: string, padrao: string) {
  try {
    if (valor === padrao) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch { /* modo privado */ }
}

export const temaAtual = (): Tema => (ler(CHAVE_TEMA) as Tema | null) ?? "sistema";

export function aplicarTema(tema: Tema = temaAtual()) {
  gravar(CHAVE_TEMA, tema, "sistema");
  if (tema === "sistema") delete document.documentElement.dataset.tema;
  else document.documentElement.dataset.tema = tema;
}

const ouvintes = new Set<() => void>();
let discreto = ler(CHAVE_DISCRETO) === "1";

export const discretoAtual = () => discreto;

/** Modo discreto: nome e ícone neutros na aba do navegador, no histórico e na tela inicial. */
export function aplicarDiscreto(ligado = discreto) {
  discreto = ligado;
  gravar(CHAVE_DISCRETO, ligado ? "1" : "0", "0");
  document.title = ligado ? "Notas" : "Afinidade";
  const icone = document.querySelector<HTMLLinkElement>("link[rel=icon]");
  if (icone) icone.href = ligado ? "/icon-neutro.svg" : "/icon.svg";
  ouvintes.forEach((fn) => fn());
}

export function useDiscreto(): boolean {
  return useSyncExternalStore((fn) => { ouvintes.add(fn); return () => { ouvintes.delete(fn); }; }, () => discreto);
}
