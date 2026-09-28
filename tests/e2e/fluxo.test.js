// Testes no navegador (Chromium): os fluxos principais como uma pessoa usaria.
//
//   E2E_URL=http://localhost:8000 npm run e2e
//
// O servidor precisa estar rodando com AMBIENTE=dev e um LIMITE_AUTH_POR_MIN alto.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const BASE = process.env.E2E_URL ?? "http://localhost:8000";
const FOTO = fileURLToPath(new URL("./foto.jpg", import.meta.url));
const SENHA = "senha-forte-123";
const sufixo = Date.now().toString(36);
let navegador;

before(async () => {
  navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
});
after(() => navegador?.close());

async function novaPessoa(apelido, genero, busca) {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 }, reducedMotion: "reduce" });
  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  await pagina.goto(`${BASE}/#/entrar`);
  await pagina.click("button[role=tab]:has-text('Criar conta')");
  await pagina.fill("#handle", apelido);
  await pagina.fill("#senha", SENHA);
  await pagina.fill("#nascimento", "1991-02-03");
  await pagina.check("input[name=maior]");
  await pagina.check("input[name=consinto]");
  await pagina.click("button[type=submit]");
  await pagina.waitForSelector("text=Crie seu perfil");
  await pagina.fill("#nome", apelido);
  await pagina.selectOption("#genero", genero);
  await pagina.check(`input[name=busca_por][value=${busca}]`);
  await pagina.click(".tag-linha:has-text('Bondage') button[data-nivel=quero]");
  await pagina.click("form button[type=submit]");
  await esperarTitulo(pagina, "Seu perfil");
  return { ctx, pagina, erros };
}

/** Espera o título EXATO (":has-text" casaria "Crie seu perfil" com "Seu perfil"). */
async function esperarTitulo(pagina, titulo) {
  await pagina.waitForFunction((t) => document.querySelector("main h1")?.textContent === t, titulo);
}

async function semRolagemHorizontal(pagina) {
  const [conteudo, janela] = await pagina.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  assert.ok(conteudo <= janela, `a página rola na horizontal (${conteudo}px > ${janela}px)`);
}

test("fotos borradas, pedido de acesso, conexão, chat efêmero e pânico", async () => {
  const leo = await novaPessoa(`leo_${sufixo}`, "homem-cis", "mulher-cis");
  const mar = await novaPessoa(`mar_${sufixo}`, "mulher-cis", "homem-cis");

  // Mar envia uma foto; Leo a vê borrada e pede acesso
  await mar.pagina.setInputFiles("input[type=file]", FOTO);
  await mar.pagina.waitForSelector(".moldura img");
  await leo.pagina.goto(`${BASE}/#/descobrir`);
  const cartaoMar = leo.pagina.locator(".cartao", { hasText: `mar_${sufixo}` });
  await cartaoMar.locator(".foto.borrada").waitFor();
  await semRolagemHorizontal(leo.pagina);
  await cartaoMar.locator("text=Pedir para ver as fotos").click();
  await leo.pagina.waitForSelector("text=Pedido enviado");
  await cartaoMar.locator("button:has-text('Curtir')").click();

  // Mar aprova o pedido e curte de volta
  await mar.pagina.reload();
  await mar.pagina.click("button:has-text('Aprovar')");
  await mar.pagina.goto(`${BASE}/#/descobrir`);
  await mar.pagina.locator(".cartao", { hasText: `leo_${sufixo}` }).locator("button:has-text('Curtir')").click();
  await mar.pagina.waitForSelector("text=É uma conexão");

  // Chat: o texto aparece literal (sem HTML) e começa a contagem de 5 minutos ao ser lido
  await leo.pagina.goto(`${BASE}/#/conexoes`);
  await semRolagemHorizontal(leo.pagina);
  await leo.pagina.locator(".cartao", { hasText: `mar_${sufixo}` }).locator("button:has-text('Conversar')").click();
  await leo.pagina.fill("textarea[name=texto]", "Oi! <b>sem html</b>");
  await leo.pagina.click("button:has-text('Enviar')");
  await mar.pagina.goto(`${BASE}/#/conexoes`);
  await mar.pagina.locator(".cartao", { hasText: `leo_${sufixo}` }).locator("button:has-text('Conversar')").click();
  await mar.pagina.waitForSelector(".msg .expira:has-text('some em')");
  assert.equal(await mar.pagina.textContent(".msg p"), "Oi! <b>sem html</b>");
  assert.equal(await mar.pagina.locator(".msg b").count(), 0);
  await leo.pagina.waitForSelector(".msg.minha .expira:has-text('some em')", { timeout: 10_000 });

  // Pânico (ESC): some a tela, limpa o armazenamento, derruba a sessão e vai para o Google
  await mar.pagina.route("https://www.google.com/**", (r) => r.fulfill({ body: "<title>Google</title>", contentType: "text/html" }));
  await mar.pagina.evaluate(() => { localStorage.setItem("x", "1"); sessionStorage.setItem("y", "2"); });
  await mar.pagina.keyboard.press("Escape");
  await mar.pagina.waitForURL("https://www.google.com/**");
  assert.equal((await mar.ctx.request.get(`${BASE}/api/perfil`)).status(), 401);
  await mar.pagina.goto(BASE);
  assert.equal(await mar.pagina.evaluate(() => localStorage.length + sessionStorage.length), 0);
  await mar.pagina.waitForSelector("text=Criar conta");

  assert.deepEqual([...leo.erros, ...mar.erros], []);
  await leo.ctx.close();
  await mar.ctx.close();
});

test("trocar de tela rápido não deixa a tela antiga sobrescrever a nova", async () => {
  const pessoa = await novaPessoa(`ana_${sufixo}`, "agenero", "agenero");
  // Deixa a descoberta lenta de propósito e troca de tela antes de ela terminar
  await pessoa.pagina.route("**/api/descobrir**", async (r) => {
    await new Promise((ok) => setTimeout(ok, 1200));
    await r.continue();
  });
  await pessoa.pagina.goto(`${BASE}/#/descobrir`);
  await pessoa.pagina.goto(`${BASE}/#/conta`);
  await esperarTitulo(pessoa.pagina, "Conta");
  await pessoa.pagina.waitForTimeout(2000); // a descoberta termina aqui e não pode desenhar
  assert.equal(await pessoa.pagina.textContent("main h1"), "Conta");
  await pessoa.ctx.close();
});

test("botão de pânico visível e com rótulo acessível em todas as telas", async () => {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 } });
  const pagina = await ctx.newPage();
  await pagina.goto(`${BASE}/#/entrar`);
  const botao = pagina.locator("#panico");
  assert.ok(await botao.isVisible());
  assert.equal(await botao.getAttribute("aria-label"), "Saída rápida (ESC)");
  await ctx.close();
});
