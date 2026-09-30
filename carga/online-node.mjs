// Gerador leve do cenário "online" (mesmo roteiro e metas de carga/online.js), em Node puro.
//
// Por que existe: o k6 reserva ~330 KB por usuário virtual logo no início (30 mil = ~10 GB só
// para o gerador). Numa máquina só, com API e banco juntos, isso não cabe. Aqui cada pessoa é um
// WebSocket nativo + timers (~20 KB). O k6 continua sendo o teste oficial para máquinas maiores.
//
//   BASE=http://127.0.0.1:8000 USUARIOS=30000 FATIA=0/2 SUBIDA_S=300 PICO_S=600 \
//     node carga/online-node.mjs carga/resultados/30k-0.json
//
// Diferença consciente: as requisições HTTP compartilham conexões keep-alive (o agente padrão do
// Node), enquanto cada navegador teria as suas. Os WebSockets (a parte que "segura" conexões)
// são um por pessoa, como no app.
import { readFileSync, writeFileSync } from "node:fs";

import { avaliarMetas, esperaReconexao, percentil as pct, resumir as resumo } from "./estatistica.mjs";

const BASE = process.env.BASE || "http://127.0.0.1:8000";
const WS_URL = BASE.replace(/^http/, "ws") + "/api/ws";
const USUARIOS = Number(process.env.USUARIOS || 30000);
const [FATIA, FATIAS] = (process.env.FATIA || "0/1").split("/").map(Number);
const SUBIDA_S = Number(process.env.SUBIDA_S || 300);
const PICO_S = Number(process.env.PICO_S || 600);
const PENSAR_S = Number(process.env.PENSAR_S || 30);
const TIMEOUT_MS = 60_000;
const SAIDA = process.argv[2] || "carga/resultados/node.json";

const todos = JSON.parse(readFileSync(new URL("./.tokens.json", import.meta.url))).usuarios;
const meus = todos.filter((_, i) => i % FATIAS === FATIA).slice(0, Math.floor(USUARIOS / FATIAS));

// ---------- métricas ----------
const inicio = Date.now();
const fimSubida = inicio + SUBIDA_S * 1000;
const fimPico = fimSubida + PICO_S * 1000;
const fase = () => (Date.now() < fimSubida ? "subida" : "pico");
const m = {
  subida: novaFase(), pico: novaFase(),
  ws: { tentativas: 0, abertos: 0, falhas: 0, caiu: 0, abertosAgora: 0 },
  avisos: 0, mensagens: 0, serie: [],
};
function novaFase() {
  return { tempos: [], porRota: {}, ok: 0, erro: 0, erros: {} };
}
let janela = { req: 0, erro: 0, tempos: [] };

function registrar(rota, ms, ok, motivo) {
  const f = m[fase()];
  f.tempos.push(ms);
  (f.porRota[rota] ??= []).push(ms);
  if (ok) f.ok++;
  else {
    f.erro++;
    f.erros[motivo] = (f.erros[motivo] || 0) + 1;
  }
  janela.req++;
  if (!ok) janela.erro++;
  janela.tempos.push(ms);
}

// ---------- ações ----------
async function pedir(rota, url, opcoes, esperado) {
  const t = performance.now();
  try {
    const r = await fetch(BASE + url, { ...opcoes, signal: AbortSignal.timeout(TIMEOUT_MS) });
    await r.arrayBuffer();
    const ok = r.status === esperado;
    registrar(rota, performance.now() - t, ok, ok ? null : `HTTP ${r.status}`);
    return ok;
  } catch (e) {
    registrar(rota, performance.now() - t, false, e.name === "TimeoutError" ? "timeout" : e.cause?.code || e.name);
    return false;
  }
}

async function acao(u) {
  const h = { Authorization: `Bearer ${u.token}` };
  const s = Math.random();
  if (s < 0.45) await pedir("descobrir", "/api/descobrir?limite=20", { headers: h }, 200);
  else if (s < 0.6) await pedir("conversas", "/api/conversas", { headers: h }, 200);
  else if (s < 0.75 && u.par) await pedir("ler", `/api/conversas/${u.par}/mensagens`, { headers: h }, 200);
  else if (s < 0.85 && u.par) {
    const ok = await pedir("enviar", `/api/conversas/${u.par}/mensagens`, {
      method: "POST", headers: { ...h, "Content-Type": "application/json" }, body: JSON.stringify({ texto: "oi, tudo bem?" }),
    }, 201);
    if (ok) m.mensagens++;
  } else if (s < 0.95) await pedir("conta", "/api/conta", { headers: h }, 200);
  else await pedir("conexoes", "/api/conexoes", { headers: h }, 200);
}

// ---------- uma pessoa online ----------
let encerrando = false;
function pessoa(u) {
  let tentativas = 0;
  let timers = [];
  const limpar = () => { timers.forEach(clearTimeout); timers.forEach(clearInterval); timers = []; };

  function conectar() {
    if (encerrando) return;
    m.ws.tentativas++;
    let abriu = false;
    const ws = new WebSocket(WS_URL, { headers: { Authorization: `Bearer ${u.token}` } });
    u.ws = ws;
    ws.onopen = () => {
      abriu = true; tentativas = 0; m.ws.abertos++; m.ws.abertosAgora++;
      timers.push(setTimeout(() => acao(u), Math.random() * PENSAR_S * 1000));
      timers.push(setInterval(() => acao(u), PENSAR_S * (0.7 + Math.random() * 0.6) * 1000));
      timers.push(setInterval(() => ws.readyState === 1 && ws.send("."), 25_000));
    };
    ws.onmessage = () => { m.avisos++; };
    ws.onerror = () => {};
    ws.onclose = () => {
      limpar();
      if (abriu) m.ws.abertosAgora--;
      if (encerrando) return;
      if (abriu) m.ws.caiu++;
      else m.ws.falhas++;
      // Mesma espera crescente do app (static/js/tempo_real.js)
      timers.push(setTimeout(conectar, esperaReconexao(tentativas++) * 1000));
    };
  }
  conectar();
}

// ---------- execução ----------
const intervaloEntrada = (SUBIDA_S * 1000) / meus.length;
meus.forEach((u, i) => setTimeout(() => pessoa(u), i * intervaloEntrada));

const serie = setInterval(() => {
  const t = [...janela.tempos].sort((a, b) => a - b);
  m.serie.push({
    s: Math.round((Date.now() - inicio) / 1000), ws: m.ws.abertosAgora,
    rps: +(janela.req / 10).toFixed(1), erros: janela.erro, p95: Math.round(pct(t, 95)),
  });
  janela = { req: 0, erro: 0, tempos: [] };
}, 10_000);

setTimeout(encerrar, fimPico - inicio);

function resumoFase(f) {
  const total = f.ok + f.erro;
  return {
    requisicoes: total, erro: total ? +(f.erro / total).toFixed(4) : 0, motivos: f.erros,
    tempo: resumo(f.tempos), porRota: Object.fromEntries(Object.entries(f.porRota).map(([k, v]) => [k, resumo(v)])),
  };
}

function encerrar() {
  encerrando = true;
  clearInterval(serie);
  const pico = resumoFase(m.pico);
  const subida = resumoFase(m.subida);
  const wsTaxa = m.ws.tentativas ? m.ws.abertos / m.ws.tentativas : 0;
  const metas = avaliarMetas({
    erro: pico.erro, p95: pico.tempo.p95, p99: pico.tempo.p99, descobrirP95: pico.porRota.descobrir?.p95 ?? 0, wsTaxa,
  });
  const saida = {
    fatia: `${FATIA}/${FATIAS}`, usuarios: meus.length, subida_s: SUBIDA_S, pico_s: PICO_S, pensar_s: PENSAR_S,
    ws: { ...m.ws, taxa_abertura: +wsTaxa.toFixed(4), abertos_no_fim: m.ws.abertosAgora },
    avisos: m.avisos, mensagens: m.mensagens, pico, subida, metas, serie: m.serie,
  };
  writeFileSync(SAIDA, JSON.stringify(saida, null, 1));
  console.log(JSON.stringify({ fatia: saida.fatia, usuarios: saida.usuarios, ws: saida.ws, pico: { ...pico, porRota: undefined }, metas }, null, 1));
  for (const u of meus) u.ws?.close(1000);
  setTimeout(() => process.exit(Object.values(metas).every(Boolean) ? 0 : 99), 2000);
}
