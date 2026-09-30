// Testes unitários da lógica pura do protótipo (prototipos/formulario-identidade/index.html).
// A página é um arquivo único, então o teste recorta o trecho entre <logica-pura> e </logica-pura>
// e o roda no Node, sem DOM e sem navegador: `npm test`.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../../prototipos/formulario-identidade/index.html", import.meta.url), "utf8");
const trecho = html.match(/\/\/ <logica-pura>[^\n]*\n([\s\S]*?)\/\/ <\/logica-pura>/)?.[1];
assert.ok(trecho, "marcadores <logica-pura> não encontrados na página");

const NOMES = ["OPCOES", "OUTRO", "MINIMO_OUTRO", "MAXIMO_OUTRO", "limparOutro", "contarVisiveis", "montarIdentidade", "ladoDaDica"];
const contexto = vm.createContext({ Intl });
vm.runInContext(`"use strict";${trecho};globalThis.__exportar = { ${NOMES.join(", ")} };`, contexto);
const { OPCOES, OUTRO, MINIMO_OUTRO, MAXIMO_OUTRO, limparOutro, contarVisiveis, montarIdentidade, ladoDaDica } = contexto.__exportar;

// Objetos criados dentro do vm têm outro Object.prototype; normaliza antes do deepEqual.
const simples = (valor) => JSON.parse(JSON.stringify(valor));
const montar = (...args) => simples(montarIdentidade(OPCOES, ...args));

// ---------- dados ----------

test("OPCOES: três categorias com as quantidades combinadas", () => {
  assert.deepEqual(Object.keys(OPCOES), ["orientacao", "genero", "biologica"]);
  assert.deepEqual(Object.values(OPCOES).map((l) => l.length), [17, 10, 2]);
});

test("OPCOES: ids únicos em cada categoria, em minúsculas e sem colidir com 'outro'", () => {
  for (const [categoria, itens] of Object.entries(OPCOES)) {
    const ids = itens.map((o) => o.id);
    assert.equal(new Set(ids).size, ids.length, `id repetido em ${categoria}`);
    for (const id of ids) {
      assert.match(id, /^[a-z0-9]+(-[a-z0-9]+)*$/, `id fora do padrão: ${id}`);
      assert.notEqual(id, OUTRO.id);
    }
  }
});

test("OPCOES: todo item tem nome e descrição preenchidos, sem espaços sobrando", () => {
  for (const item of [...Object.values(OPCOES).flat(), OUTRO]) {
    assert.deepEqual(Object.keys(item).sort(), ["descricao", "id", "nome"]);
    for (const campo of ["nome", "descricao"]) {
      assert.ok(item[campo].length > 0, `${item.id}.${campo} vazio`);
      assert.equal(item[campo], item[campo].trim(), `${item.id}.${campo} com espaço sobrando`);
    }
  }
});

test("orientação: a lista fala só de orientação sexual (título pedido)", () => {
  assert.ok(OPCOES.orientacao.some((o) => o.id === "heterossexualidade"));
  assert.equal(OPCOES.orientacao.at(0).nome, "Heterossexualidade");
});

// ---------- limparOutro ----------

test("limparOutro: apara, junta espaços e quebras de linha, normaliza para NFC", () => {
  assert.equal(limparOutro("  não   binárie\n\nfluido  "), "não binárie fluido");
  assert.equal(limparOutro("é"), "é"); // e + acento combinante vira é
});

test("limparOutro: remove invisíveis (largura zero, hífen suave, marca de direção)", () => {
  assert.equal(limparOutro("a​​b"), "ab");
  assert.equal(limparOutro("a­­b"), "ab");
  assert.equal(limparOutro("‎abc‏﻿"), "abc");
});

test("limparOutro: preserva emoji composto (o ZWJ fica)", () => {
  assert.equal(limparOutro("👩🏽‍💻"), "👩🏽‍💻");
});

test("limparOutro: vazio, null e undefined viram texto vazio", () => {
  assert.equal(limparOutro(""), "");
  assert.equal(limparOutro(null), "");
  assert.equal(limparOutro(undefined), "");
});

test("limparOutro: corta em MAXIMO_OUTRO caracteres, sem partir emoji ao meio", () => {
  assert.equal(limparOutro("x".repeat(500)).length, MAXIMO_OUTRO);
  const emojis = limparOutro("🙂".repeat(MAXIMO_OUTRO + 5));
  assert.equal([...emojis].length, MAXIMO_OUTRO);
  assert.ok(!/[\ud800-\udbff]$/.test(emojis), "sobrou meio par substituto no fim");
});

test("limparOutro: texto com cara de HTML continua só texto (nada é interpretado)", () => {
  assert.equal(limparOutro("<img src=x onerror=alert(1)>"), "<img src=x onerror=alert(1)>");
});

// ---------- contarVisiveis ----------

test("contarVisiveis: conta o que a pessoa enxerga", () => {
  const casos = [
    ["abc", 3], ["  ab  ", 2], ["a b", 2], ["🙂🙂", 2], ["👩🏽‍💻👩🏽‍💻", 2],
    ["a​​b", 2], ["éé", 2], ["\n\n\n", 0], ["", 0],
  ];
  for (const [texto, esperado] of casos) assert.equal(contarVisiveis(texto), esperado, JSON.stringify(texto));
});

// ---------- montarIdentidade ----------

test("montarIdentidade: nada marcado devolve as três listas vazias", () => {
  assert.deepEqual(montar(), { resultado: { orientacao: [], genero: [], biologica: [] }, invalidas: [] });
});

test("montarIdentidade: devolve {id, nome} na ordem de OPCOES, não na dos cliques", () => {
  const { resultado } = montar({ orientacao: ["pansexualidade", "heterossexualidade"] });
  assert.deepEqual(resultado.orientacao.map((o) => o.id), ["heterossexualidade", "pansexualidade"]);
  assert.deepEqual(Object.keys(resultado.orientacao[0]), ["id", "nome"]); // descrição não vai junto
});

test("montarIdentidade: ignora ids desconhecidos e repetidos", () => {
  const { resultado } = montar({ genero: ["queer", "queer", "inventado", "__proto__"], extra: ["x"] });
  assert.deepEqual(resultado.genero, [{ id: "queer", nome: "Queer" }]);
  assert.deepEqual(Object.keys(resultado), ["orientacao", "genero", "biologica"]);
});

test("montarIdentidade: 'Outro' válido entra por último, com o texto limpo", () => {
  const { resultado, invalidas } = montar({ genero: ["outro", "queer"] }, { genero: "  demi​garoto  " });
  assert.deepEqual(invalidas, []);
  assert.deepEqual(resultado.genero, [{ id: "queer", nome: "Queer" }, { id: "outro", nome: "Outro", texto: "demigaroto" }]);
});

test(`montarIdentidade: 'Outro' com menos de ${MINIMO_OUTRO} caracteres visíveis é inválido`, () => {
  for (const texto of ["", "ab", "   ab  ", "a​​b", "a­­b", "🙂🙂", "\n\n\n", undefined]) {
    const { resultado, invalidas } = montar({ orientacao: ["outro"] }, { orientacao: texto });
    assert.deepEqual(invalidas, ["orientacao"], JSON.stringify(texto));
    assert.deepEqual(resultado.orientacao, []);
  }
});

test(`montarIdentidade: exatamente ${MINIMO_OUTRO} caracteres visíveis passa (limite)`, () => {
  for (const texto of ["abc", "🙂🙂🙂", "a b c"]) {
    assert.deepEqual(montar({ orientacao: ["outro"] }, { orientacao: texto }).invalidas, [], texto);
  }
});

test("montarIdentidade: texto do 'Outro' sem a caixa marcada é ignorado", () => {
  const { resultado, invalidas } = montar({}, { orientacao: "ab", genero: "texto longo o bastante" });
  assert.deepEqual(invalidas, []);
  assert.deepEqual(resultado, { orientacao: [], genero: [], biologica: [] });
});

test("montarIdentidade: aponta todas as categorias inválidas, na ordem do formulário", () => {
  const { invalidas } = montar({ biologica: ["outro"], orientacao: ["outro"], genero: ["outro"] }, { genero: "válido" });
  assert.deepEqual(invalidas, ["orientacao", "biologica"]);
});

// ---------- ladoDaDica ----------

test("ladoDaDica: centralizado no meio da tela; alinhado perto das bordas", () => {
  assert.equal(ladoDaDica(180, 360), null);
  assert.equal(ladoDaDica(20, 360), "a-direita");
  assert.equal(ladoDaDica(340, 360), "a-esquerda");
});

test("ladoDaDica: limites exatos da margem de 16 px", () => {
  // balão de 260 px: metade 130; cabe centralizado se 16 <= centro-130 e centro+130 <= largura-16
  assert.equal(ladoDaDica(146, 1000), null);
  assert.equal(ladoDaDica(145, 1000), "a-direita");
  assert.equal(ladoDaDica(854, 1000), null);
  assert.equal(ladoDaDica(855, 1000), "a-esquerda");
});

test("ladoDaDica: tela estreita (zoom de 200%): o balão encolhe e se alinha ao ícone", () => {
  assert.equal(ladoDaDica(160, 180), "a-esquerda");
  assert.equal(ladoDaDica(20, 180), "a-direita");
});
