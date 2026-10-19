// Testes no navegador (Chromium) da nova interface, no modo demonstração (sem back-end):
//
//   cd web && npm run build:demo && npm run preview:demo &
//   WEB_URL=http://localhost:4173 npm run e2e:demo
//
// Percorre as telas como uma pessoa usaria e confere, em cada uma, que não há erro no console
// nem rolagem horizontal em 360 px.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import { chromium } from "playwright";

const BASE = process.env.WEB_URL ?? "http://localhost:4173";
let navegador;

before(async () => {
  navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
});
after(() => navegador?.close());

async function novaPagina({ largura = 390, altura = 844, tema = "light" } = {}) {
  const contexto = await navegador.newContext({ viewport: { width: largura, height: altura }, colorScheme: tema, locale: "pt-BR" });
  const pagina = await contexto.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(e.message));
  pagina.on("console", (m) => { if (m.type() === "error") erros.push(m.text()); });
  // O pânico leva ao Google: responde localmente para o teste não depender da rede.
  await contexto.route("https://www.google.com/**", (r) => r.fulfill({ body: "<title>Google</title>google", contentType: "text/html" }));
  return { pagina, erros, contexto };
}

async function semRolagemLateral(pagina, onde) {
  const { sw, cw } = await pagina.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  assert.ok(sw <= cw, `rolagem horizontal em ${onde}: ${sw} > ${cw}`);
}

async function entrar(pagina) {
  await pagina.goto(`${BASE}/#/entrar`);
  await pagina.getByLabel("E-mail").fill("pessoa@exemplo.com");
  await pagina.getByRole("button", { name: "Receber código por e-mail" }).click();
  await pagina.getByText("Confira seu e-mail").waitFor();
  // colar o código inteiro na primeira caixa preenche as seis e confirma sozinho
  await pagina.getByLabel("Dígito 1").fill("123456");
  await pagina.getByRole("heading", { name: "Descobrir" }).waitFor();
}

test("entrar: código errado mostra erro; o certo leva ao Descobrir", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await pagina.goto(`${BASE}/`);
  // sem sessão, qualquer tela leva para entrar
  await pagina.getByRole("heading", { name: /Conexões por afinidade/ }).waitFor();
  await semRolagemLateral(pagina, "entrar");
  await pagina.getByLabel("E-mail").fill("pessoa@exemplo.com");
  await pagina.getByRole("button", { name: "Receber código por e-mail" }).click();
  await pagina.getByLabel("Dígito 1").fill("999999");
  await pagina.getByRole("alert").filter({ hasText: "Código inválido" }).waitFor();
  await pagina.getByLabel("Dígito 1").fill("123456");
  await pagina.getByRole("heading", { name: "Descobrir" }).waitFor();
  assert.deepEqual(erros.filter((e) => !e.includes("401")), []);
  await contexto.close();
});

test("criar conta exige as três confirmações", async () => {
  const { pagina, contexto } = await novaPagina();
  await pagina.goto(`${BASE}/#/entrar`);
  await pagina.getByRole("tab", { name: "Criar conta" }).click();
  await pagina.getByLabel("Data de nascimento").waitFor(); // espera a troca de aba terminar
  await pagina.getByLabel("E-mail").fill("nova@exemplo.com");
  await pagina.getByLabel("Data de nascimento").fill("1990-04-05");
  await pagina.getByRole("button", { name: "Enviar código de confirmação" }).click();
  await pagina.getByRole("alert").filter({ hasText: "Marque as três confirmações" }).waitFor();
  for (const caixa of await pagina.getByRole("checkbox").all()) await caixa.check();
  await pagina.getByRole("button", { name: "Enviar código de confirmação" }).click();
  await pagina.getByText("Confira seu e-mail").waitFor();
  await contexto.close();
});

test("descobrir: curtir vira conexão e abre o chat; mensagem enviada aparece", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.getByRole("article", { name: "Perfil de Leo" }).waitFor();
  await semRolagemLateral(pagina, "descobrir");
  // foto de quem não liberou chega borrada
  await pagina.getByText("Foto protegida").first().waitFor();
  await pagina.getByRole("button", { name: "Curtir", exact: true }).click();
  await pagina.getByRole("dialog", { name: "É uma conexão" }).waitFor();
  await pagina.getByRole("button", { name: "Mandar mensagem" }).click();
  await pagina.getByText("Comece a conversa com Leo").waitFor();
  await semRolagemLateral(pagina, "chat");
  await pagina.getByLabel("Mensagem", { exact: true }).fill("Oi, Leo!");
  await pagina.getByRole("button", { name: "Enviar" }).click();
  await pagina.getByText("Oi, Leo!").waitFor();
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("descobrir: pular e bloquear tiram o perfil da fila", async () => {
  const { pagina, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.getByRole("article", { name: "Perfil de Leo" }).waitFor();
  await pagina.getByRole("button", { name: "Pular" }).click();
  await pagina.getByRole("article", { name: "Perfil de Mar" }).waitFor();
  await pagina.getByRole("button", { name: "Mais opções" }).last().click();
  await pagina.getByRole("button", { name: "Bloquear" }).click();
  await pagina.getByRole("dialog", { name: "Bloquear Mar?" }).getByRole("button", { name: "Bloquear" }).click();
  await pagina.getByText("Perfil bloqueado").waitFor();
  await pagina.getByRole("article", { name: "Perfil de Lia" }).waitFor();
  await contexto.close();
});

test("descobrir: passa de uma página de 20 e continua mostrando gente da massa", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  const vistos = [];
  for (let i = 0; i < 25; i++) {
    // espera a animação do cartão anterior terminar (por um instante há dois no topo)
    await pagina.waitForFunction(() => document.querySelectorAll("[data-topo]").length === 1);
    const atual = await pagina.locator("[data-topo]").getAttribute("data-perfil");
    vistos.push(atual);
    await pagina.getByRole("button", { name: "Pular" }).click();
    await pagina.waitForFunction(
      (anterior) => [...document.querySelectorAll("[data-topo]")].at(-1)?.getAttribute("data-perfil") !== anterior,
      atual,
    );
  }
  assert.equal(new Set(vistos).size, 25, "cada cartão é um perfil diferente (a próxima página não repete)");
  await pagina.locator("[data-topo] article").last().waitFor(); // ainda há cartões depois da 1ª página
  assert.equal(await pagina.getByText("Você viu todo mundo").count(), 0);
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("conexões e chat: não lidas, prazo combinado e apagar as minhas", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.getByRole("link", { name: "Conexões" }).click();
  await pagina.getByRole("heading", { name: "Conexões" }).waitFor();
  await pagina.getByText("1 mensagem nova").waitFor();
  await semRolagemLateral(pagina, "conexões");
  await pagina.getByRole("button", { name: /Mar.*mensagem nova/ }).click();
  await pagina.getByText("Ilustração e um pouco de fotografia").waitFor();
  // cada mensagem lida mostra quanto falta para sumir
  await pagina.getByText(/some em \d+ h/).first().waitFor();
  await pagina.getByRole("button", { name: /somem 24 horas após lidas/ }).click();
  await pagina.getByRole("button", { name: "1 semana" }).click();
  await pagina.getByRole("button", { name: "Propor a Mar" }).click();
  await pagina.getByText("Proposta enviada").waitFor();
  await pagina.getByText(/Você propôs/).waitFor();
  await pagina.getByRole("button", { name: "Desistir" }).click();
  await pagina.getByRole("button", { name: "Propor a Mar" }).waitFor();
  await pagina.getByRole("button", { name: "Fechar" }).click();
  await pagina.getByRole("button", { name: "Opções da conversa" }).click();
  await pagina.getByRole("button", { name: "Apagar as minhas mensagens" }).click();
  await pagina.getByRole("dialog", { name: "Apagar suas mensagens?" }).getByRole("button", { name: "Apagar" }).click();
  await pagina.getByText("Suas mensagens foram apagadas").waitFor();
  await pagina.getByText("Adorei sua bio").waitFor({ state: "detached", timeout: 3000 });
  // regressão: uma busca periódica antiga não pode trazer a mensagem apagada de volta
  await pagina.waitForTimeout(4000);
  assert.equal(await pagina.getByText("Adorei sua bio").count(), 0);
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("perfil: pedidos de fotos, interesses e salvar", async () => {
  const { pagina, erros, contexto } = await novaPagina({ largura: 360, altura: 780 });
  await entrar(pagina);
  await pagina.getByRole("link", { name: "Perfil" }).click();
  await pagina.getByText("Pedidos para ver suas fotos").waitFor();
  await semRolagemLateral(pagina, "perfil (360 px)");
  await pagina.getByRole("button", { name: "Aprovar" }).click();
  await pagina.getByText("Acesso liberado").waitFor();
  const massagem = pagina.getByRole("group", { name: "Massagem" });
  assert.equal(await massagem.getByRole("button", { name: "Quero" }).getAttribute("aria-pressed"), "true");
  await massagem.getByRole("button", { name: "Curioso" }).click();
  assert.equal(await massagem.getByRole("button", { name: "Curioso" }).getAttribute("aria-pressed"), "true");
  assert.equal(await massagem.getByRole("button", { name: "Quero" }).getAttribute("aria-pressed"), "false");
  await pagina.getByRole("button", { name: "Salvar perfil" }).click();
  await pagina.getByText("Perfil salvo").waitFor();
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("conta: tema escuro e modo discreto", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.getByRole("link", { name: "Conta" }).click();
  await pagina.getByText("@voce_demo").waitFor();
  await semRolagemLateral(pagina, "conta");
  await pagina.getByRole("tab", { name: "Escuro" }).click();
  assert.equal(await pagina.evaluate(() => document.documentElement.dataset.tema), "escuro");
  const fundo = await pagina.evaluate(() => getComputedStyle(document.body).backgroundColor);
  assert.equal(fundo, "rgb(11, 11, 15)");
  await pagina.getByRole("switch", { name: /Modo discreto/ }).click();
  await pagina.getByText("Modo discreto ligado").waitFor();
  assert.equal(await pagina.title(), "Notas");
  await pagina.getByRole("tab", { name: "Automático" }).click();
  assert.equal(await pagina.evaluate(() => document.documentElement.dataset.tema), undefined);
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("encontros: registrar, fazer check-in", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.getByRole("link", { name: "Encontros" }).click();
  await pagina.getByText("Nenhum encontro registrado").waitFor();
  await semRolagemLateral(pagina, "encontros");
  await pagina.getByRole("button", { name: "Registrar encontro" }).click();
  const folha = pagina.getByRole("dialog", { name: "Novo encontro" });
  await folha.getByLabel("Onde").fill("Café Central, Rua das Flores 100");
  await folha.getByLabel("E-mail do contato de confiança").fill("amiga@exemplo.com");
  await folha.getByRole("button", { name: "Registrar encontro" }).click();
  await pagina.getByText("Aguardando seu check-in").waitFor();
  await pagina.getByRole("button", { name: "Estou bem" }).click();
  await pagina.getByText("Check-in feito: tudo bem").waitFor();
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("moderação: banir tira o caso da fila", async () => {
  const { pagina, erros, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.goto(`${BASE}/#/moderacao`);
  await pagina.getByText("@anon_k3v9x2mq").waitFor();
  await semRolagemLateral(pagina, "moderação");
  await pagina.getByRole("button", { name: "Banir" }).click();
  await pagina.getByRole("dialog").getByRole("button", { name: "Confirmar" }).click();
  await pagina.getByText("Nenhum caso na fila").waitFor();
  assert.deepEqual(erros, []);
  await contexto.close();
});

test("pânico: ESC apaga a tela, limpa o armazenamento e vai para o Google sem deixar histórico", async () => {
  const { pagina, contexto } = await novaPagina();
  await entrar(pagina);
  await pagina.evaluate(() => { localStorage.setItem("x", "1"); sessionStorage.setItem("y", "2"); });
  await pagina.keyboard.press("Escape");
  await pagina.waitForURL("https://www.google.com/");
  assert.equal(await pagina.title(), "Google");
  // replace: voltar não reabre o app
  const voltou = await pagina.goBack().catch(() => null);
  assert.ok(!voltou || !voltou.url().startsWith(BASE) || !(await pagina.getByRole("heading", { name: "Descobrir" }).count()));
  await contexto.close();
});

test("pânico: botão vermelho funciona até na tela de entrar", async () => {
  const { pagina, contexto } = await novaPagina();
  await pagina.goto(`${BASE}/#/entrar`);
  await pagina.getByRole("button", { name: "Saída rápida (ESC)" }).click();
  await pagina.waitForURL("https://www.google.com/");
  await contexto.close();
});

test("computador: abas no topo e tema escuro do sistema", async () => {
  const { pagina, erros, contexto } = await novaPagina({ largura: 1280, altura: 800, tema: "dark" });
  await entrar(pagina);
  const nav = pagina.getByRole("navigation", { name: "Navegação principal" });
  assert.equal(await nav.count(), 1);
  const caixa = await nav.boundingBox();
  assert.ok(caixa && caixa.y < 100, "no computador as abas ficam no topo");
  const fundo = await pagina.evaluate(() => getComputedStyle(document.body).backgroundColor);
  assert.equal(fundo, "rgb(11, 11, 15)");
  await semRolagemLateral(pagina, "descobrir (computador)");
  assert.deepEqual(erros, []);
  await contexto.close();
});
