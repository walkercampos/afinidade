// Avisos em tempo real ("algo novo na conversa X"). O canal nunca traz conteúdo: ao receber um
// aviso, a tela busca pela API normal. Se o canal cair, reconecta com espera crescente.
import { MODO_DEMO } from "./api";

export interface CanalDeAvisos { conectado: () => boolean; fechar: () => void }

export function conectarAvisos(aoAvisar: (aviso: { conversa?: string }) => void): CanalDeAvisos {
  if (MODO_DEMO) return { conectado: () => false, fechar: () => {} };
  let ws: WebSocket | null = null;
  let tentativas = 0;
  let encerrado = false;
  let temporizador: ReturnType<typeof setTimeout> | undefined;

  function abrir() {
    if (encerrado) return;
    const esquema = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${esquema}//${location.host}/api/ws`);
    ws.addEventListener("open", () => { tentativas = 0; });
    ws.addEventListener("message", (ev) => {
      try { aoAvisar(JSON.parse(ev.data)); } catch { /* aviso malformado: ignora */ }
    });
    ws.addEventListener("close", (ev) => {
      ws = null;
      // 4401: sessão encerrada; 4403: origem recusada. Não adianta tentar de novo.
      if (encerrado || ev.code === 4401 || ev.code === 4403) return;
      temporizador = setTimeout(abrir, Math.min(30_000, 1000 * 2 ** tentativas++));
    });
  }

  abrir();
  return {
    conectado: () => ws?.readyState === WebSocket.OPEN,
    fechar() {
      encerrado = true;
      clearTimeout(temporizador);
      ws?.close();
    },
  };
}
