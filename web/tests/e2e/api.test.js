// Testes no navegador da nova interface ligada à API de verdade (cookie, CSRF, e-mail, banco).
//
//   API: uvicorn app.main:app --port 8000, com AMBIENTE=dev, EMAIL_PROVEDOR=arquivo,
//        IDADE_PROVEDOR=simulado e WEBAUTHN_ORIGENS=http://localhost:4173
//   Interface: cd web && npm run build && npm run preview  (porta 4173; o /api vai para :8000)
//   WEB_URL=http://localhost:4173 API_EMAILS=../emails-dev npm run e2e:api
//
// Sem API_EMAILS, os testes deste arquivo são pulados (o modo demonstração tem os seus).
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { after, before, test } from "node:test";

import { chromium } from "playwright";

const BASE = process.env.WEB_URL ?? "http://localhost:4173";
const EMAILS = process.env.API_EMAILS;
const pular = !EMAILS && "defina API_EMAILS (pasta dos e-mails de desenvolvimento) para testar com a API";
const sufixo = Date.now().toString(36);
let navegador;

before(async () => {
  if (pular) return;
  navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
});
after(() => navegador?.close());

async function codigoPara(email) {
  for (let i = 0; i < 50; i++) {
    for (const a of readdirSync(EMAILS).sort().reverse()) {
      const texto = readFileSync(join(EMAILS, a), "utf8");
      // \r\n no Windows, \n no Linux
      if (texto.split(/\r?\n/)[0] === `Para: ${email}`) return texto.match(/código de acesso é: (\d{6})/)[1];
    }
    await new Promise((ok) => setTimeout(ok, 100));
  }
  throw new Error(`nenhum e-mail para ${email}`);
}

/** Cadastro, perfil e verificação de idade pela interface, como uma pessoa faria. */
async function novaPessoa(apelido, genero, busca) {
  const ctx = await navegador.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  const email = `${apelido}@teste.invalid`;

  await pagina.goto(`${BASE}/#/entrar`);
  await pagina.getByRole("tab", { name: "Criar conta" }).click();
  await pagina.getByLabel("Data de nascimento").waitFor();
  await pagina.getByLabel("E-mail").fill(email);
  await pagina.getByLabel("Apelido (opcional)").fill(apelido);
  await pagina.getByLabel("Data de nascimento").fill("1991-02-03");
  for (const caixa of await pagina.getByRole("checkbox").all()) await caixa.check();
  await pagina.getByRole("button", { name: "Enviar código de confirmação" }).click();
  await pagina.getByText("Confira seu e-mail").waitFor();
  await pagina.getByLabel("Dígito 1").fill(await codigoPara(email));

  // Sem autenticador neste navegador: a biometria fica para depois.
  await pagina.getByRole("heading", { name: "Conta criada. Agora, a biometria" }).waitFor();
  await pagina.getByRole("button", { name: "Agora não" }).click();

  await pagina.getByRole("heading", { name: "Crie seu perfil" }).waitFor();
  await pagina.getByLabel("Nome de exibição").fill(apelido);
  await pagina.getByLabel("Seu gênero").selectOption(genero);
  await pagina.getByRole("button", { name: busca, exact: true }).click();
  await pagina.getByRole("group", { name: "Bondage" }).getByRole("button", { name: "Quero" }).click();
  await pagina.getByRole("button", { name: "Criar perfil" }).click();

  // A API exige idade verificada para descobrir: a interface leva para a verificação.
  await pagina.getByRole("heading", { name: "Confirme sua idade" }).waitFor();
  await pagina.getByRole("button", { name: "Verificar minha idade" }).click();
  await pagina.getByRole("heading", { name: "Provedor simulado" }).waitFor();
  await pagina.getByRole("button", { name: "Aprovar" }).click();
  await pagina.getByRole("heading", { name: "Idade verificada" }).waitFor();
  return { ctx, pagina, erros };
}

test("cadastro, conexão, chat em tempo real e pânico com a API real", { skip: pular }, async () => {
  const leo = await novaPessoa(`leo_${sufixo}`, "homem-cis", "Mulher Cis");
  const mar = await novaPessoa(`mar_${sufixo}`, "mulher-cis", "Homem Cis");

  // Interesses vindos do banco aparecem com o nome da categoria
  await leo.pagina.goto(`${BASE}/#/perfil`);
  await leo.pagina.getByRole("heading", { name: "Restrição" }).waitFor();

  // Leo curte Mar
  await leo.pagina.goto(`${BASE}/#/descobrir`);
  await leo.pagina.getByRole("article", { name: `Perfil de mar_${sufixo}` }).waitFor();
  await leo.pagina.getByRole("button", { name: "Curtir", exact: true }).click();
  await leo.pagina.getByText("Curtida enviada").waitFor();

  // Mar curte de volta: é uma conexão
  await mar.pagina.goto(`${BASE}/#/descobrir`);
  await mar.pagina.getByRole("article", { name: `Perfil de leo_${sufixo}` }).waitFor();
  await mar.pagina.getByRole("button", { name: "Curtir", exact: true }).click();
  await mar.pagina.getByRole("dialog", { name: "É uma conexão" }).waitFor();
  await mar.pagina.getByRole("button", { name: "Mandar mensagem" }).click();

  // Mar escreve; o texto aparece literal (sem HTML) para Leo, que vê o prazo começar
  await mar.pagina.getByLabel("Mensagem", { exact: true }).fill("Oi! <b>sem html</b>");
  await mar.pagina.getByRole("button", { name: "Enviar" }).click();
  await leo.pagina.goto(`${BASE}/#/conexoes`);
  await leo.pagina.getByRole("listitem").filter({ hasText: `mar_${sufixo}` }).getByRole("button").click();
  await leo.pagina.getByText("Oi! <b>sem html</b>").waitFor();
  assert.equal(await leo.pagina.locator("main li b").count(), 0);
  await leo.pagina.getByText(/some em/).first().waitFor();

  // Leo responde e Mar recebe sem recarregar (aviso em tempo real ou busca periódica)
  await leo.pagina.getByLabel("Mensagem", { exact: true }).fill("Oi, Mar!");
  await leo.pagina.getByRole("button", { name: "Enviar" }).click();
  await mar.pagina.getByText("Oi, Mar!").waitFor({ timeout: 10_000 });

  // Pânico: vai para o Google e a sessão morre no servidor
  await mar.ctx.route("https://www.google.com/**", (r) => r.fulfill({ body: "<title>Google</title>", contentType: "text/html" }));
  await mar.pagina.keyboard.press("Escape");
  await mar.pagina.waitForURL("https://www.google.com/**");
  await new Promise((ok) => setTimeout(ok, 500));
  assert.equal((await mar.ctx.request.get(`${BASE}/api/perfil`)).status(), 401);
  await mar.pagina.goto(`${BASE}/#/descobrir`);
  await mar.pagina.getByRole("heading", { name: /Conexões por afinidade/ }).waitFor();

  assert.deepEqual([...leo.erros, ...mar.erros], []);
  await leo.ctx.close();
  await mar.ctx.close();
});

test("sem sessão, a API recusa e a interface leva para entrar", { skip: pular }, async () => {
  const ctx = await navegador.newContext();
  const pagina = await ctx.newPage();
  await pagina.goto(`${BASE}/#/conta`);
  await pagina.getByRole("heading", { name: /Conexões por afinidade/ }).waitFor();
  assert.equal((await ctx.request.get(`${BASE}/api/conta`)).status(), 401);
  await ctx.close();
});
