// Teste de carga: N pessoas online AO MESMO TEMPO (k6).
//
// "Online" aqui é o que o app faz de verdade com a tela aberta: um WebSocket aberto o tempo todo
// (avisos de mensagem nova) e, a cada ~30 s, uma ação pela API: descobrir perfis, abrir as
// conversas, ler e mandar mensagem, ver a conta. Veja carga/README.md.
//
//   k6 run -e BASE=http://127.0.0.1:8000 -e USUARIOS=30000 carga/online.js
//
// Variáveis: BASE (URL da API), USUARIOS (pico), SUBIDA (ex.: 5m), PICO (tempo no pico),
// PENSAR_S (intervalo médio entre ações), FATIA="i/n" (este processo usa a fatia i de n dos
// tokens; para passar do limite de arquivos abertos de um processo, rode n processos).
import http from "k6/http";
import ws from "k6/ws";
import { check, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Rate, Trend } from "k6/metrics";
import exec from "k6/execution";

const BASE = __ENV.BASE || "http://127.0.0.1:8000";
const WS_BASE = BASE.replace(/^http/, "ws");
const USUARIOS = Number(__ENV.USUARIOS || 30000);
const SUBIDA = __ENV.SUBIDA || "5m";
const PICO = __ENV.PICO || "10m";
const PENSAR_S = Number(__ENV.PENSAR_S || 30);
const [FATIA, FATIAS] = (__ENV.FATIA || "0/1").split("/").map(Number);

const usuarios = new SharedArray("usuarios", () => {
  const todos = JSON.parse(open("./.tokens.json")).usuarios;
  return todos.filter((_, i) => i % FATIAS === FATIA);
});

const avisosRecebidos = new Counter("avisos_ws_recebidos");
const mensagensEnviadas = new Counter("mensagens_enviadas");
const wsConectou = new Rate("ws_conectou");
const wsCaiu = new Counter("ws_caiu_antes_da_hora");
const tempoDescobrir = new Trend("tempo_descobrir", true);
const tempoMensagens = new Trend("tempo_mensagens", true);

const porProcesso = Math.floor(USUARIOS / FATIAS);
// Como static/js/tempo_real.js: se o canal cai, espera 1 s, 2 s, 4 s... até 30 s antes de tentar
// de novo. Sem isso, cada falha vira uma rajada de reconexões que o app real nunca faria.
let tentativas = 0;

export const options = {
  scenarios: {
    online: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: SUBIDA, target: porProcesso },
        { duration: PICO, target: porProcesso },
        { duration: "1m", target: 0 },
      ],
      gracefulRampDown: "90s",
    },
  },
  // Metas (SLO) para "aguenta": abaixo disso o teste falha.
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500", "p(99)<1500"],
    tempo_descobrir: ["p(95)<800"],
    ws_conectou: ["rate>0.99"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  discardResponseBodies: true,
};

function acao(u, cabecalhos) {
  const sorteio = Math.random();
  if (sorteio < 0.45) {
    const r = http.get(`${BASE}/api/descobrir?limite=20`, { headers: cabecalhos, tags: { nome: "descobrir" } });
    tempoDescobrir.add(r.timings.duration);
    check(r, { "descobrir 200": (x) => x.status === 200 });
  } else if (sorteio < 0.60) {
    check(http.get(`${BASE}/api/conversas`, { headers: cabecalhos, tags: { nome: "conversas" } }),
      { "conversas 200": (x) => x.status === 200 });
  } else if (sorteio < 0.75 && u.par) {
    const r = http.get(`${BASE}/api/conversas/${u.par}/mensagens`, { headers: cabecalhos, tags: { nome: "ler" } });
    tempoMensagens.add(r.timings.duration);
    check(r, { "ler 200": (x) => x.status === 200 });
  } else if (sorteio < 0.85 && u.par) {
    const r = http.post(`${BASE}/api/conversas/${u.par}/mensagens`, JSON.stringify({ texto: "oi, tudo bem?" }),
      { headers: { ...cabecalhos, "Content-Type": "application/json" }, tags: { nome: "enviar" } });
    tempoMensagens.add(r.timings.duration);
    if (check(r, { "enviar 201": (x) => x.status === 201 })) mensagensEnviadas.add(1);
  } else if (sorteio < 0.95) {
    check(http.get(`${BASE}/api/conta`, { headers: cabecalhos, tags: { nome: "conta" } }),
      { "conta 200": (x) => x.status === 200 });
  } else {
    check(http.get(`${BASE}/api/conexoes`, { headers: cabecalhos, tags: { nome: "conexoes" } }),
      { "conexoes 200": (x) => x.status === 200 });
  }
}

export default function () {
  // Cada VU é uma pessoa fixa (um token): o mesmo VU nunca abre dois canais com a mesma conta.
  const u = usuarios[(exec.vu.idInTest - 1) % usuarios.length];
  const cabecalhos = { Authorization: `Bearer ${u.token}` };
  // Fica online até o fim do pico; a descida do k6 encerra a sessão.
  const sessaoMs = 60 * 60 * 1000;
  let encerradoPorNos = false;

  const res = ws.connect(`${WS_BASE}/api/ws`, { headers: cabecalhos, tags: { nome: "ws" } }, (socket) => {
    socket.on("open", () => {
      wsConectou.add(true);
      tentativas = 0;
      // Primeira ação logo ao entrar, espalhada para não sincronizar todo mundo
      socket.setTimeout(() => acao(u, cabecalhos), Math.random() * PENSAR_S * 1000);
      socket.setInterval(() => acao(u, cabecalhos), PENSAR_S * (0.7 + Math.random() * 0.6) * 1000);
      socket.setInterval(() => socket.send("."), 25_000); // "ping" do cliente, como o app
      socket.setTimeout(() => { encerradoPorNos = true; socket.close(); }, sessaoMs);
    });
    socket.on("message", () => avisosRecebidos.add(1));
    socket.on("close", () => { if (!encerradoPorNos && exec.scenario.progress < 1) wsCaiu.add(1); });
    socket.on("error", () => {});
  });
  // ws.connect só retorna quando o canal fecha; se nem chegou a abrir, conta como falha.
  if (!res || res.status !== 101) wsConectou.add(false);
  if (!encerradoPorNos) {
    const espera = Math.min(30, 2 ** tentativas++);
    sleep(espera * (0.5 + Math.random() * 0.5));
  }
}
