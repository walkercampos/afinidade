// Testes unitários das funções puras da nova interface (node --test, sem dependências).
//   cd web && npm test
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  descreverDistancia, distanciaDoIndice, formatarRestante, iniciais, indiceDaDistancia, juntarClasses, mensagemDeErro,
  msAte, nomeDaCategoria, PARADAS_DISTANCIA, quandoRelativo, rotuloDistancia, rotuloPrazo,
} from "../src/lib/util.ts";

test("formatarRestante: minutos, horas e dias", () => {
  assert.equal(formatarRestante(0), "0:00");
  assert.equal(formatarRestante(-5000), "0:00");
  assert.equal(formatarRestante(245_000), "4:05");
  assert.equal(formatarRestante(3_600_000), "1 h 00 min");
  assert.equal(formatarRestante(23 * 3_600_000 + 5 * 60_000), "23 h 05 min");
  assert.equal(formatarRestante((3 * 24 + 4) * 3_600_000), "3 d 4 h");
});

test("msAte: diferença até a data", () => {
  assert.equal(msAte("2026-01-01T00:00:10Z", Date.parse("2026-01-01T00:00:00Z")), 10_000);
  assert.ok(msAte("2020-01-01T00:00:00Z") < 0);
});

test("rotuloPrazo: nomes dos prazos das mensagens", () => {
  assert.equal(rotuloPrazo(null), "nunca");
  assert.equal(rotuloPrazo(5), "5 minutos");
  assert.equal(rotuloPrazo(1), "1 minuto");
  assert.equal(rotuloPrazo(60), "1 hora");
  assert.equal(rotuloPrazo(1440), "24 horas");
  assert.equal(rotuloPrazo(2880), "2 dias");
  assert.equal(rotuloPrazo(10080), "1 semana");
  assert.equal(rotuloPrazo(20160), "14 dias");
  assert.equal(rotuloPrazo(43200), "1 mês");
  assert.equal(rotuloPrazo(259200), "6 meses");
});

test("distância: índice e valor da barra vão e voltam", () => {
  for (let i = 0; i < PARADAS_DISTANCIA.length; i++) assert.equal(indiceDaDistancia(distanciaDoIndice(i)), i);
  assert.equal(distanciaDoIndice(PARADAS_DISTANCIA.length - 1), null);
  assert.equal(indiceDaDistancia(null), PARADAS_DISTANCIA.length - 1);
  assert.equal(indiceDaDistancia(12), indiceDaDistancia(15)); // arredonda para cima
  assert.equal(indiceDaDistancia(9999), PARADAS_DISTANCIA.length - 2);
  assert.equal(distanciaDoIndice(-3), 5);
  assert.equal(distanciaDoIndice(Number.NaN), 5);
  assert.equal(rotuloDistancia(null), "Qualquer distância");
  assert.equal(rotuloDistancia(25), "Até 25 km");
  assert.equal(descreverDistancia(undefined), null);
  assert.equal(descreverDistancia(10), "até 10 km");
});

test("mensagemDeErro: formatos de erro do FastAPI", () => {
  assert.equal(mensagemDeErro({ detail: "Código inválido" }), "Código inválido");
  assert.equal(mensagemDeErro({ detail: "Erro interno", requisicao: "abc" }), "Erro interno (código abc)");
  assert.equal(
    mensagemDeErro({ detail: [{ msg: "Value error, A plataforma é exclusiva para maiores de 18 anos" }, { msg: "outro" }] }),
    "A plataforma é exclusiva para maiores de 18 anos · outro",
  );
  assert.equal(mensagemDeErro(null), "Algo deu errado. Tente de novo.");
  assert.equal(mensagemDeErro({}), "Algo deu errado. Tente de novo.");
});

test("quandoRelativo: rótulos curtos para a lista de conversas", () => {
  const agora = Date.parse("2026-05-10T12:00:00Z");
  assert.equal(quandoRelativo(null, agora), "");
  assert.equal(quandoRelativo("2026-05-10T11:59:40Z", agora), "agora");
  assert.equal(quandoRelativo("2026-05-10T11:48:00Z", agora), "12 min");
  assert.equal(quandoRelativo("2026-05-10T09:00:00Z", agora), "3 h");
  assert.equal(quandoRelativo("2026-05-09T10:00:00Z", agora), "ontem");
  assert.match(quandoRelativo("2026-05-01T10:00:00Z", agora), /^\d{2}\/\d{2}$/);
});

test("iniciais e juntarClasses", () => {
  assert.equal(iniciais("Rafa & Bia"), "R&");
  assert.equal(iniciais("lia"), "L");
  assert.equal(iniciais("   "), "?");
  assert.equal(juntarClasses("a", false, null, undefined, "b"), "a b");
});

test("nomeDaCategoria: slugs do catálogo viram nomes com acento", () => {
  assert.equal(nomeDaCategoria("restricao"), "Restrição");
  assert.equal(nomeDaCategoria("sensacao"), "Sensação");
  assert.equal(nomeDaCategoria("nova-categoria"), "Nova categoria");
  assert.equal(nomeDaCategoria(null), "Outros");
});
