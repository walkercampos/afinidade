// Testes unitários das funções puras do front: `npm test` (sem dependências).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DESTINO_PANICO, descreverDistancia, executarPanico, formatarRestante, lerRota, mensagemDeErro, msAte,
  normalizarFilhos,
} from "../../static/js/util.js";

test("pânico: apaga tela, limpa armazenamentos, encerra sessão e troca a página, nessa ordem", () => {
  const passos = [];
  const armazenamento = (nome) => ({ clear: () => passos.push(`limpa ${nome}`) });
  executarPanico({
    armazenamentos: [armazenamento("local"), armazenamento("session")],
    limparTela: () => passos.push("tela"),
    encerrarSessao: () => passos.push("sessão"),
    navegar: (url) => passos.push(`vai ${url}`),
  });
  assert.deepEqual(passos, ["tela", "limpa local", "limpa session", "sessão", `vai ${DESTINO_PANICO}`]);
});

test("pânico: navega mesmo se tudo antes falhar (modo privado, rede fora)", () => {
  let destino = null;
  const falha = () => { throw new Error("bloqueado"); };
  executarPanico({
    armazenamentos: [{ clear: falha }], limparTela: falha, encerrarSessao: falha, navegar: (url) => { destino = url; },
  });
  assert.equal(destino, "https://www.google.com/");
});

test("contagem regressiva das mensagens", () => {
  assert.equal(formatarRestante(300_000), "5:00");
  assert.equal(formatarRestante(61_001), "1:02");
  assert.equal(formatarRestante(999), "0:01");
  assert.equal(formatarRestante(-5), "0:00");
  assert.equal(msAte("2026-01-01T00:05:00Z", Date.parse("2026-01-01T00:00:00Z")), 300_000);
});

test("rotas com parâmetro", () => {
  assert.deepEqual(lerRota("#/chat/abc-123"), { rota: "chat", parametro: "abc-123" });
  assert.deepEqual(lerRota(""), { rota: "descobrir", parametro: null });
  assert.deepEqual(lerRota("#/perfil"), { rota: "perfil", parametro: null });
});

test("mensagens de erro da API", () => {
  assert.equal(mensagemDeErro({ detail: "Apelido já em uso" }), "Apelido já em uso");
  assert.equal(mensagemDeErro({ detail: [{ msg: "Value error, Mínimo 18" }, { msg: "outro" }] }), "Mínimo 18 · outro");
  assert.equal(mensagemDeErro(null), "Algo deu errado. Tente de novo.");
});

test("distância em faixas", () => {
  assert.equal(descreverDistancia(10), "até 10 km");
  assert.equal(descreverDistancia(null), null);
});

test("regressão: listas e vazios não viram texto na tela", () => {
  // A tela de Conexões mostrava "[object HTMLElement]" (array não achatado) e seções
  // vazias apareceriam como "null".
  const a = { no: "a" }, b = { no: "b" };
  assert.deepEqual(normalizarFilhos(["t", [a, [b]], null, undefined, false, 0, ""]), ["t", a, b, 0, ""]);
});
