// Rotas no fragmento da URL (#/chat/<id>), sempre com location.replace: o app não empilha
// histórico, então depois do botão de pânico o "voltar" do navegador não reabre nenhuma tela.
import { useSyncExternalStore } from "react";

export interface Rota { rota: string; parametro: string | null }

export function lerRota(hash: string): Rota {
  const [rota = "", parametro = null] = hash.replace(/^#\/?/, "").split("/");
  return { rota: rota || "descobrir", parametro: parametro ? decodeURIComponent(parametro) : null };
}

const ouvintes = new Set<() => void>();
let versao = 0; // muda também quando a pessoa "navega" para a tela em que já está (recarrega)
let instantaneo = { hash: location.hash, versao };

function avisar() {
  instantaneo = { hash: location.hash, versao };
  ouvintes.forEach((fn) => fn());
}
window.addEventListener("hashchange", avisar);

export function irPara(rota: string) {
  const alvo = `#/${rota}`;
  versao++;
  if (location.hash === alvo) avisar();
  else location.replace(alvo);
}

function assinar(fn: () => void) {
  ouvintes.add(fn);
  return () => { ouvintes.delete(fn); };
}

export function useRota(): Rota & { chave: string } {
  const { hash, versao: v } = useSyncExternalStore(assinar, () => instantaneo);
  return { ...lerRota(hash), chave: `${hash}#${v}` };
}
