// Estatística do gerador de carga (carga/estatistica.mjs): se o cálculo errar, o relatório mente.
import assert from "node:assert/strict";
import { test } from "node:test";

import { avaliarMetas, esperaReconexao, percentil, resumir } from "../../carga/estatistica.mjs";

test("percentil: posto mais próximo, como o k6", () => {
  const cem = Array.from({ length: 100 }, (_, i) => i + 1); // 1..100
  assert.equal(percentil(cem, 50), 50);
  assert.equal(percentil(cem, 95), 95);
  assert.equal(percentil(cem, 99), 99);
  assert.equal(percentil(cem, 100), 100);
  assert.equal(percentil(cem, 0), 1);
});

test("percentil: listas pequenas e vazias", () => {
  assert.equal(percentil([], 95), 0);
  assert.equal(percentil([7], 95), 7);
  assert.equal(percentil([1, 2], 50), 1);
  assert.equal(percentil([1, 2], 51), 2);
});

test("resumir: ordena sem alterar a lista original e arredonda", () => {
  const tempos = [30.04, 10, 20.06];
  assert.deepEqual(resumir(tempos), { n: 3, med: 20.1, p90: 30, p95: 30, p99: 30, max: 30 });
  assert.deepEqual(tempos, [30.04, 10, 20.06]);
  assert.deepEqual(resumir([]), { n: 0, med: 0, p90: 0, p95: 0, p99: 0, max: 0 });
});

test("metas: passam dentro dos limites e falham exatamente no limite", () => {
  const ok = { erro: 0.0099, p95: 499, p99: 1499, descobrirP95: 799, wsTaxa: 0.991 };
  assert.ok(Object.values(avaliarMetas(ok)).every(Boolean));
  const noLimite = avaliarMetas({ erro: 0.01, p95: 500, p99: 1500, descobrirP95: 800, wsTaxa: 0.99 });
  assert.ok(Object.values(noLimite).every((v) => v === false));
});

test("reconexão: espera cresce 1, 2, 4... até 30 s, com sorteio entre 50% e 100%", () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6, 10].map((t) => esperaReconexao(t, 1)), [1, 2, 4, 8, 16, 30, 30, 30]);
  assert.equal(esperaReconexao(3, 0), 4);
  for (let t = 0; t < 8; t++) {
    const e = esperaReconexao(t);
    assert.ok(e >= Math.min(30, 2 ** t) / 2 && e <= Math.min(30, 2 ** t));
  }
});
