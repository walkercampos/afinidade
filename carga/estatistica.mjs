// Estatística do gerador de carga (carga/online-node.mjs). Testada em tests/js/carga.test.js.

/** Percentil pelo método do "posto mais próximo" (o mesmo do k6). `ordenado` em ordem crescente. */
export function percentil(ordenado, p) {
  if (!ordenado.length) return 0;
  return ordenado[Math.min(ordenado.length - 1, Math.max(0, Math.ceil((p / 100) * ordenado.length) - 1))];
}

/** Resumo de uma lista de tempos (ms), com uma casa decimal. */
export function resumir(tempos) {
  const t = [...tempos].sort((a, b) => a - b);
  const r = (x) => Math.round(x * 10) / 10;
  return {
    n: t.length, med: r(percentil(t, 50)), p90: r(percentil(t, 90)), p95: r(percentil(t, 95)),
    p99: r(percentil(t, 99)), max: r(t.at(-1) ?? 0),
  };
}

/** Metas do teste (as mesmas de carga/online.js). Devolve { nome: passou }. */
export function avaliarMetas({ erro, p95, p99, descobrirP95, wsTaxa }) {
  return {
    "erro < 1% (pico)": erro < 0.01,
    "p95 < 500 ms (pico)": p95 < 500,
    "p99 < 1,5 s (pico)": p99 < 1500,
    "descobrir p95 < 800 ms (pico)": descobrirP95 < 800,
    "WebSockets que abrem > 99%": wsTaxa > 0.99,
  };
}

/** Espera antes de reconectar o WebSocket: 1, 2, 4... até 30 s, com sorteio de 50% a 100%. */
export function esperaReconexao(tentativas, sorteio = Math.random()) {
  return Math.min(30, 2 ** tentativas) * (0.5 + sorteio * 0.5);
}
