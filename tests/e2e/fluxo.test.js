// Testes no navegador (Chromium): os fluxos principais como uma pessoa usaria.
//
//   E2E_URL=http://localhost:8000 E2E_EMAILS=./emails-dev npm run e2e
//
// O servidor precisa estar rodando com AMBIENTE=dev, EMAIL_PROVEDOR=arquivo (E2E_EMAILS aponta
// para a mesma pasta de EMAIL_PASTA) e um LIMITE_AUTH_POR_MIN alto.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const BASE = process.env.E2E_URL ?? "http://localhost:8000";
const FOTO = fileURLToPath(new URL("./foto.jpg", import.meta.url));
const PASTA_EMAILS = process.env.E2E_EMAILS ?? "emails-dev";
const sufixo = Date.now().toString(36);
let navegador;

before(async () => {
  navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
});
after(() => navegador?.close());

/** Lê a "caixa de entrada" (pasta de e-mails de desenvolvimento) e devolve o código e o link. */
async function emailPara(email) {
  for (let i = 0; i < 50; i++) {
    const arquivos = readdirSync(PASTA_EMAILS).sort().reverse();
    for (const a of arquivos) {
      const texto = readFileSync(join(PASTA_EMAILS, a), "utf8");
      if (texto.startsWith(`Para: ${email}\n`)) {
        return { codigo: texto.match(/código de acesso é: (\d{6})/)[1], link: texto.match(/(http\S+#\/verificar\/\S+)/)[1] };
      }
    }
    await new Promise((ok) => setTimeout(ok, 100));
  }
  throw new Error(`nenhum e-mail para ${email}`);
}

/** Cadastro pela interface: e-mail + código. Termina logado, na tela de biometria ou de perfil. */
async function cadastrarPorEmail(pagina, email, apelido) {
  await pagina.click("button[role=tab]:has-text('Criar conta')");
  await pagina.fill("#email", email);
  if (apelido) await pagina.fill("#handle", apelido);
  await pagina.fill("#nascimento", "1991-02-03");
  await pagina.check("input[name=maior]");
  await pagina.check("input[name=consinto]");
  await pagina.click("button:has-text('Enviar código de confirmação')");
  await pagina.waitForSelector("#codigo");
  await pagina.fill("#codigo", (await emailPara(email)).codigo);
  await pagina.click("button:has-text('Confirmar')");
}

async function novaPessoa(apelido, genero, busca) {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 }, reducedMotion: "reduce" });
  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  await pagina.goto(`${BASE}/#/entrar`);
  await cadastrarPorEmail(pagina, `${apelido}@teste.invalid`, apelido);
  // Sem autenticador neste contexto: a biometria fica para depois.
  await esperarTitulo(pagina, "Conta criada. Agora, a biometria");
  await pagina.click("button:has-text('Agora não')");
  await esperarTitulo(pagina, "Crie seu perfil");
  await pagina.fill("#nome", apelido);
  await pagina.selectOption("#genero", genero);
  await pagina.check(`input[name=busca_por][value=${busca}]`);
  await pagina.click(".tag-linha:has-text('Bondage') button[data-nivel=quero]");
  await pagina.click("form button[type=submit]");
  await esperarTitulo(pagina, "Seu perfil");
  await verificarIdade(pagina);
  await pagina.goto(`${BASE}/#/perfil`);
  await esperarTitulo(pagina, "Seu perfil");
  return { ctx, pagina, erros };
}

/** Verificação de idade pelo provedor simulado (o servidor de testes roda com ela obrigatória). */
async function verificarIdade(pagina) {
  await pagina.goto(`${BASE}/#/idade`);
  await esperarTitulo(pagina, "Confirme sua idade");
  await pagina.click("button:has-text('Verificar minha idade')");
  await esperarTitulo(pagina, "Provedor simulado");
  await pagina.click("button:has-text('Aprovar')");
  await esperarTitulo(pagina, "Idade verificada");
}

/** Espera o título EXATO (":has-text" casaria "Crie seu perfil" com "Seu perfil"). */
async function esperarTitulo(pagina, titulo) {
  await pagina.waitForFunction((t) => document.querySelector("main h1")?.textContent === t, titulo);
}

async function semRolagemHorizontal(pagina) {
  const [conteudo, janela] = await pagina.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  assert.ok(conteudo <= janela, `a página rola na horizontal (${conteudo}px > ${janela}px)`);
}

/** Regressão: o botão de pânico (fixo) não pode cobrir botões quando a página rola até o fim. */
async function panicoNaoCobreBotoes(pagina) {
  await pagina.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const cobertos = await pagina.evaluate(() => {
    const p = document.querySelector("#panico").getBoundingClientRect();
    return [...document.querySelectorAll("main button")].filter((b) => {
      const r = b.getBoundingClientRect();
      return r.width && !(r.right < p.left || r.left > p.right || r.bottom < p.top || r.top > p.bottom);
    }).map((b) => b.textContent);
  });
  assert.deepEqual(cobertos, [], `o botão de pânico cobre: ${cobertos.join(", ")}`);
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
  await panicoNaoCobreBotoes(leo.pagina);
  await cartaoMar.locator("text=Pedir para ver as fotos").click();
  await leo.pagina.waitForSelector("text=Pedido enviado");
  await cartaoMar.locator("button:has-text('Curtir')").click();

  // Mar aprova o pedido e curte de volta
  await mar.pagina.reload();
  await mar.pagina.click("button:has-text('Aprovar')");
  await mar.pagina.goto(`${BASE}/#/descobrir`);
  await mar.pagina.locator(".cartao", { hasText: `leo_${sufixo}` }).locator("button:has-text('Curtir')").click();
  await mar.pagina.waitForSelector("text=É uma conexão");

  // Chat: o texto aparece literal (sem HTML) e começa a contagem do prazo ao ser lido
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
  await panicoNaoCobreBotoes(leo.pagina);

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

/** Simula um celular com biometria (autenticador de plataforma do Chrome via DevTools). */
async function autenticadorVirtual(ctx, pagina) {
  const cdp = await ctx.newCDPSession(pagina);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2", transport: "internal", hasResidentKey: true,
      hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true,
    },
  });
  return { credenciais: async () => (await cdp.send("WebAuthn.getCredentials", { authenticatorId })).credentials };
}

test("conta pelo e-mail, depois biometria; sair e entrar só com a digital", async () => {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 } });
  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  await pagina.goto(`${BASE}/#/entrar`);
  const aparelho = await autenticadorVirtual(ctx, pagina);

  await cadastrarPorEmail(pagina, `bio_${sufixo}@teste.invalid`, `bio_${sufixo}`);
  await esperarTitulo(pagina, "Conta criada. Agora, a biometria");
  await pagina.click("button:has-text('Ativar biometria')");
  await esperarTitulo(pagina, "Crie seu perfil");
  const [credencial] = await aparelho.credenciais();
  assert.equal(credencial.isResidentCredential, true); // passkey descobrível: entra sem digitar nada

  await pagina.goto(`${BASE}/#/conta`);
  await pagina.waitForSelector(".lista-passkeys li");
  await pagina.click("button:has-text('Sair de todos os dispositivos')");
  await esperarTitulo(pagina, "Conexões por afinidade, sem expor quem você é");
  assert.equal((await ctx.request.get(`${BASE}/api/passkeys`)).status(), 401);

  await pagina.click("button:has-text('Entrar com biometria')");
  await esperarTitulo(pagina, "Crie seu perfil"); // entrou: ainda não tem perfil
  assert.deepEqual(erros, []);
  await ctx.close();
});

test("link do e-mail entra no app e some do histórico", async () => {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 } });
  const pagina = await ctx.newPage();
  await pagina.goto(`${BASE}/#/entrar`);
  const email = `link_${sufixo}@teste.invalid`;
  await pagina.click("button[role=tab]:has-text('Criar conta')");
  await pagina.fill("#email", email);
  await pagina.fill("#nascimento", "1991-02-03");
  await pagina.check("input[name=maior]");
  await pagina.check("input[name=consinto]");
  await pagina.click("button:has-text('Enviar código de confirmação')");
  await pagina.waitForSelector("#codigo");
  const { link } = await emailPara(email);
  const destino = new URL(link);
  await pagina.goto(`${BASE}/${destino.hash}`);
  await esperarTitulo(pagina, "Conta criada. Agora, a biometria"); // conta nova: oferece a biometria
  assert.ok(!pagina.url().includes("verificar"), "o token ficou na URL");
  await ctx.close();
});

async function localizacaoSimulada(pessoa, posicao = { latitude: -23.5505, longitude: -46.6333 }) {
  await pessoa.ctx.grantPermissions(["geolocation"]);
  await pessoa.ctx.setGeolocation(posicao);
}

test("barra de distância: liga com a localização, salva ao soltar e o Descobrir avisa quando acaba", async () => {
  const pessoa = await novaPessoa(`geo_${sufixo}`, "travesti", "travesti");
  await localizacaoSimulada(pessoa);
  const barra = pessoa.pagina.locator("#distancia");
  assert.ok(await barra.isDisabled(), "sem localização a barra fica desligada");

  await pessoa.pagina.click("button:has-text('Usar minha localização')");
  await pessoa.pagina.waitForSelector("button:has-text('Atualizar minha região')");
  assert.ok(await barra.isEnabled());
  await barra.fill("7"); // 7ª parada = 50 km; fill dispara input + change, como soltar a barra
  await pessoa.pagina.waitForSelector("text=Distância salva: até 50 km");
  assert.equal(await pessoa.pagina.textContent("output.valor-barra"), "Até 50 km");
  const salvo = await (await pessoa.ctx.request.get(`${BASE}/api/perfil`)).json();
  assert.equal(salvo.localizacao.distancia_max_km, 50);
  await semRolagemHorizontal(pessoa.pagina);

  // Uma pessoa compatível por perto (com um raio definido, quem não tem localização não aparece)
  const vizinha = await novaPessoa(`viz_${sufixo}`, "travesti", "travesti");
  await localizacaoSimulada(vizinha, { latitude: -23.5610, longitude: -46.6560 });
  await vizinha.pagina.click("button:has-text('Usar minha localização')");
  await vizinha.pagina.waitForSelector("button:has-text('Atualizar minha região')");
  await vizinha.ctx.close();
  await pessoa.pagina.goto(`${BASE}/#/descobrir`);
  await pessoa.pagina.locator(".cartao", { hasText: `viz_${sufixo}` }).waitFor();
  // Pula todos (o banco pode ter pessoas de execuções anteriores); depois do último, o aviso
  const vazio = pessoa.pagina.locator("p.vazio");
  while (await pessoa.pagina.locator("main .cartao").count()) {
    assert.ok(await vazio.isHidden(), "o aviso não pode aparecer enquanto ainda há cartões");
    await pessoa.pagina.locator("main .cartao button:has-text('Pular')").first().click();
  }
  await pessoa.pagina.waitForSelector("text=Você viu todo mundo por enquanto");
  assert.deepEqual(pessoa.erros, []);
  await pessoa.ctx.close();
});

test("prazo das mensagens: uma pessoa propõe, a outra recebe o aviso na hora e aceita", async () => {
  const ana = await novaPessoa(`pa_${sufixo}`, "homem-trans", "mulher-trans");
  const bia = await novaPessoa(`pb_${sufixo}`, "mulher-trans", "homem-trans");
  for (const [quem, alvo] of [[ana, `pb_${sufixo}`], [bia, `pa_${sufixo}`]]) {
    await quem.pagina.goto(`${BASE}/#/descobrir`);
    await quem.pagina.locator(".cartao", { hasText: alvo }).locator("button:has-text('Curtir')").click();
  }
  await bia.pagina.waitForSelector("text=É uma conexão");

  async function abrirConversa(quem, alvo) {
    await quem.pagina.goto(`${BASE}/#/conexoes`);
    await quem.pagina.locator(".cartao", { hasText: alvo }).locator("button:has-text('Conversar')").click();
    await quem.pagina.waitForSelector("text=apagadas 24 horas depois de lidas");
  }
  await abrirConversa(ana, `pb_${sufixo}`);
  await abrirConversa(bia, `pa_${sufixo}`);

  // Ana propõe 1 hora
  await ana.pagina.click("details.prazo summary");
  await ana.pagina.selectOption("details.prazo select", "60");
  await ana.pagina.click("details.prazo button:has-text('Propor')");
  await ana.pagina.waitForSelector("text=Esperando");

  // Bia recebe pelo canal em tempo real (bem antes da busca de reserva de 20 s) e aceita
  await bia.pagina.click("details.prazo summary");
  await bia.pagina.waitForSelector("text=propôs mudar para: 1 hora", { timeout: 8000 });
  await bia.pagina.click("details.prazo button:has-text('Aceitar')");
  await bia.pagina.waitForSelector("text=apagadas 1 hora depois de lidas");
  await ana.pagina.waitForSelector("text=apagadas 1 hora depois de lidas", { timeout: 8000 });

  // A próxima mensagem já usa o prazo novo e chega para Bia pelo aviso em tempo real
  await ana.pagina.fill("textarea[name=texto]", "vale o prazo novo");
  await ana.pagina.click("button:has-text('Enviar')");
  await bia.pagina.waitForSelector(".msg:has-text('vale o prazo novo') .expira:has-text('some em 59:')", { timeout: 8000 });
  await semRolagemHorizontal(bia.pagina);

  assert.deepEqual([...ana.erros, ...bia.erros], []);
  await ana.ctx.close();
  await bia.ctx.close();
});

test("sem idade verificada, Descobrir leva para a verificação; recusada continua pendente", async () => {
  const ctx = await navegador.newContext({ viewport: { width: 360, height: 780 } });
  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  await pagina.goto(`${BASE}/#/entrar`);
  await cadastrarPorEmail(pagina, `idade_${sufixo}@teste.invalid`, `idade_${sufixo}`);
  await esperarTitulo(pagina, "Conta criada. Agora, a biometria");
  await pagina.click("button:has-text('Agora não')");
  await esperarTitulo(pagina, "Crie seu perfil");
  // Sem perfil, Descobrir leva primeiro para o perfil; com perfil, para a verificação de idade
  await pagina.goto(`${BASE}/#/descobrir`);
  await esperarTitulo(pagina, "Crie seu perfil");
  await pagina.fill("#nome", "Ida");
  await pagina.selectOption("#genero", "outro");
  await pagina.check("input[name=busca_por][value=outro]");
  await pagina.click("form button[type=submit]");
  await esperarTitulo(pagina, "Seu perfil");

  await pagina.goto(`${BASE}/#/descobrir`);
  await esperarTitulo(pagina, "Confirme sua idade");
  assert.ok(await pagina.isVisible("text=Nenhuma foto, documento ou CPF fica guardado aqui"));
  await pagina.click("button:has-text('Verificar minha idade')");
  await esperarTitulo(pagina, "Provedor simulado");
  await pagina.click("button:has-text('Recusar')");
  await esperarTitulo(pagina, "Confirme sua idade");
  await semRolagemHorizontal(pagina);
  assert.deepEqual(erros, []);
  await ctx.close();
});
