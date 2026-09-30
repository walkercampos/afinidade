// Protótipo do formulário de identidade (prototipos/formulario-identidade/index.html).
// Abre o arquivo direto (file://), sem servidor: é assim que ele é usado.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "playwright";

const ARQUIVO = pathToFileURL(fileURLToPath(new URL("../../prototipos/formulario-identidade/index.html", import.meta.url))).href;
let navegador;

before(async () => {
  navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
});
after(() => navegador?.close());

async function abrir(opcoes = {}) {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 }, ...opcoes });
  const pagina = await ctx.newPage();
  const erros = [];
  const logs = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  pagina.on("console", async (m) => { if (m.type() === "log") logs.push(await m.args()[0].jsonValue()); });
  await pagina.goto(ARQUIVO);
  return { ctx, pagina, erros, logs };
}

test("renderiza as três categorias a partir de OPCOES, com 'Outro' por último", async () => {
  const { ctx, pagina, erros } = await abrir();
  const contagem = await pagina.evaluate(() => Object.fromEntries(Object.entries(OPCOES).map(([k, v]) => [k, v.length])));
  assert.deepEqual(contagem, { orientacao: 17, genero: 10, biologica: 2 });
  for (const [categoria, total] of Object.entries(contagem)) {
    const nomes = await pagina.locator(`fieldset[data-categoria=${categoria}] .opcao label`).allTextContents();
    assert.equal(nomes.length, total + 1);
    assert.equal(nomes.at(-1), "Outro (descreva)");
    assert.ok(await pagina.isHidden(`#${categoria}-outro-texto`));
  }
  assert.deepEqual(await pagina.locator("fieldset h2").allTextContents(), [
    "Orientação sexual", "Identidade de gênero", "Características biológicas e de expressão",
  ]);
  // A label é clicável: clicar no nome marca a caixa
  await pagina.click("label[for=genero-queer]");
  assert.ok(await pagina.isChecked("#genero-queer"));
  assert.deepEqual(erros, []);
  await ctx.close();
});

test("ícone ⓘ mostra a descrição no balão ao passar o mouse, sem rolagem lateral", async () => {
  const { ctx, pagina } = await abrir();
  const icone = pagina.locator("label[for=orientacao-pansexualidade] + .info");
  assert.equal(await icone.textContent(), "i");
  const balao = () => icone.evaluate((el) => {
    const s = getComputedStyle(el, "::after");
    return { conteudo: s.content, visivel: s.display !== "none", fundo: s.backgroundColor };
  });
  assert.equal((await balao()).visivel, false);
  await icone.hover();
  await pagina.waitForTimeout(200);
  const b = await balao();
  assert.equal(b.visivel, true);
  assert.match(b.conteudo, /Atração por pessoas, independentemente de seu sexo biológico/);
  // Em todos os ícones (inclusive o do nome mais longo, perto da borda) o balão fica dentro da tela
  for (const outro of await pagina.locator(".info").all()) {
    await outro.hover();
    const { esquerda, direita } = await outro.evaluate((el) => {
      // O ::after não tem caixa própria na API; mede pela posição calculada em relação ao ícone.
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el, "::after");
      const largura = parseFloat(s.width) + parseFloat(s.paddingLeft) + parseFloat(s.paddingRight);
      let x;
      if (s.left !== "auto" && s.transform === "none") x = r.left + parseFloat(s.left);
      else if (s.left === "auto") x = r.right - parseFloat(s.right) - largura;
      else x = r.left + r.width / 2 - largura / 2;
      return { esquerda: x, direita: x + largura };
    });
    assert.ok(esquerda >= 0 && direita <= 360, `balão fora da tela: ${esquerda}..${direita}`);
  }
  const [largura, janela] = await pagina.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  assert.ok(largura <= janela, "a página rola na horizontal");
  // Pelo teclado (e no toque) o foco também mostra o balão
  await pagina.locator("label[for=genero-travesti] + .info").focus();
  assert.notEqual(await pagina.locator("label[for=genero-travesti] + .info").evaluate(
    (el) => getComputedStyle(el, "::after").display), "none");
  await ctx.close();
});

test("Outro revela o campo, exige 3 caracteres e o JSON final sai no console", async () => {
  const { ctx, pagina, logs, erros } = await abrir();
  await pagina.check("#orientacao-bissexualidade");
  await pagina.check("#orientacao-outro");
  assert.ok(await pagina.isVisible("#orientacao-outro-texto"));
  await pagina.check("#genero-nao-binario");
  await pagina.check("#biologica-intersexo");

  // Menos de 3 caracteres: alerta e não envia
  await pagina.fill("#orientacao-outro-texto", " ab ");
  let mensagem = null;
  pagina.once("dialog", (d) => { mensagem = d.message(); d.accept(); });
  await pagina.click("button[type=submit]");
  await pagina.waitForFunction(() => document.activeElement?.id === "orientacao-outro-texto");
  assert.match(mensagem, /pelo menos 3 letras, números ou símbolos/);
  assert.equal(logs.length, 0);
  assert.equal(await pagina.getAttribute("#orientacao-outro-texto", "aria-invalid"), "true");

  await pagina.fill("#orientacao-outro-texto", "Pansexual demi");
  await pagina.click("button[type=submit]");
  await pagina.waitForTimeout(100);
  assert.deepEqual(logs.at(-1), {
    orientacao: [
      { id: "bissexualidade", nome: "Bissexualidade" },
      { id: "outro", nome: "Outro", texto: "Pansexual demi" },
    ],
    genero: [{ id: "nao-binario", nome: "Não-Binário" }],
    biologica: [{ id: "intersexo", nome: "Intersexo" }],
  });

  // Desmarcar "Outro" esconde o campo e ele deixa de contar
  await pagina.uncheck("#orientacao-outro");
  assert.ok(await pagina.isHidden("#orientacao-outro-texto"));
  assert.deepEqual(erros, []);
  await ctx.close();
});

test("regressão (teste exploratório): invisíveis e emojis não burlam o mínimo do 'Outro'", async () => {
  const { ctx, pagina, logs } = await abrir();
  await pagina.check("#genero-outro");
  for (const texto of ["a\u200b\u200bb", "🙂🙂"]) {
    await pagina.fill("#genero-outro-texto", texto);
    let alertou = false;
    pagina.once("dialog", (d) => { alertou = true; d.accept(); });
    await pagina.click("button[type=submit]");
    await pagina.waitForFunction(() => document.activeElement?.id === "genero-outro-texto");
    assert.ok(alertou, `deveria bloquear ${JSON.stringify(texto)}`);
  }
  await pagina.fill("#genero-outro-texto", "demi\u200bgaroto");
  await pagina.click("button[type=submit]");
  await pagina.waitForTimeout(100);
  assert.deepEqual(logs.at(-1).genero, [{ id: "outro", nome: "Outro", texto: "demigaroto" }]);
  await ctx.close();
});

test("regressão (teste exploratório): com zoom de 200% (180 px) nada rola na horizontal", async () => {
  const { ctx, pagina } = await abrir({ viewport: { width: 180, height: 400 } });
  const rolaSemBalao = await pagina.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  assert.equal(rolaSemBalao, false, "nomes longos como 'Cisheteronormatividade' precisam quebrar");
  for (const icone of await pagina.locator(".info").all()) {
    await icone.focus();
    assert.equal(await pagina.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  }
  await ctx.close();
});

test("segue o tema escuro do aparelho", async () => {
  const { ctx, pagina } = await abrir({ colorScheme: "dark" });
  const fundo = await pagina.evaluate(() => getComputedStyle(document.body).backgroundColor);
  assert.equal(fundo, "rgb(11, 11, 15)");
  await ctx.close();
});
