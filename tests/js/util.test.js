// Testes unitários das funções puras do front: `npm test` (sem dependências).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DESTINO_PANICO, descreverDistancia, rotuloPrazo, descreverPrazo, executarPanico, formatarRestante, lerRota, mensagemDeErro, msAte,
  normalizarFilhos, b64urlParaBytes, bytesParaB64url, opcoesDeCriacao, opcoesDeLogin, credencialParaJSON,
  mensagemDeErroPasskey, PARADAS_DISTANCIA, indiceDaDistancia, distanciaDoIndice, rotuloDistancia,
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

test("base64url ida e volta, inclusive bytes que viram '-' e '_'", () => {
  const bytes = Uint8Array.from([0, 1, 250, 251, 252, 253, 254, 255, 62, 63]);
  const texto = bytesParaB64url(bytes.buffer);
  assert.doesNotMatch(texto, /[+/=]/);
  assert.deepEqual([...b64urlParaBytes(texto)], [...bytes]);
  assert.equal(bytesParaB64url(new Uint8Array([]).buffer), "");
});

test("opções do servidor viram bytes para o navegador", () => {
  const criar = opcoesDeCriacao({
    challenge: "AAEC", user: { id: "_-8", name: "anon_x" }, rp: { id: "x" },
    excludeCredentials: [{ id: "AQ", type: "public-key" }],
  });
  assert.deepEqual([...criar.challenge], [0, 1, 2]);
  assert.deepEqual([...criar.user.id], [255, 239]);
  assert.equal(criar.user.name, "anon_x");
  assert.deepEqual([...criar.excludeCredentials[0].id], [1]);
  const entrar = opcoesDeLogin({ challenge: "AAEC", userVerification: "required" });
  assert.deepEqual(entrar.allowCredentials, []);
  assert.equal(entrar.userVerification, "required");
});

test("credencial do navegador vira o JSON que o servidor espera", () => {
  const b = (...n) => Uint8Array.from(n).buffer;
  const criada = credencialParaJSON({
    id: "AQI", rawId: b(1, 2), type: "public-key", authenticatorAttachment: "platform",
    getClientExtensionResults: () => ({}),
    response: { clientDataJSON: b(3), attestationObject: b(4), getTransports: () => ["internal"] },
  });
  assert.deepEqual(criada.response, { clientDataJSON: "Aw", attestationObject: "BA", transports: ["internal"] });
  const assinada = credencialParaJSON({
    id: "AQI", rawId: b(1, 2), type: "public-key",
    response: { clientDataJSON: b(3), authenticatorData: b(5), signature: b(6), userHandle: null },
  });
  assert.deepEqual(assinada.response, { clientDataJSON: "Aw", authenticatorData: "BQ", signature: "Bg", userHandle: null });
  assert.equal(assinada.authenticatorAttachment, null);
});

test("erros do navegador viram mensagens em português", () => {
  assert.match(mensagemDeErroPasskey({ name: "NotAllowedError" }), /cancelada/);
  assert.match(mensagemDeErroPasskey({ name: "InvalidStateError" }), /já tem uma passkey/);
  assert.match(mensagemDeErroPasskey({ name: "SecurityError" }), /HTTPS/);
  assert.equal(mensagemDeErroPasskey({ name: "Outro", message: "x" }), "x");
  assert.equal(mensagemDeErroPasskey(undefined), "Não foi possível usar a passkey.");
});

test("barra de distância: ida e volta entre raio e posição, extremos e valores fora das paradas", () => {
  for (const km of PARADAS_DISTANCIA) assert.equal(distanciaDoIndice(indiceDaDistancia(km)), km);
  assert.equal(distanciaDoIndice(0), 5);
  assert.equal(distanciaDoIndice(PARADAS_DISTANCIA.length - 1), null); // última parada = qualquer distância
  assert.equal(distanciaDoIndice(-3), 5);
  assert.equal(distanciaDoIndice(999), null);
  assert.equal(distanciaDoIndice("2"), 15); // o valor do <input type=range> chega como texto
  // Raios salvos antes da barra (ex.: 60 km) caem na parada seguinte, nunca numa menor
  assert.equal(distanciaDoIndice(indiceDaDistancia(60)), 75);
  assert.equal(rotuloDistancia(25), "Até 25 km");
  assert.equal(rotuloDistancia(null), "Qualquer distância");
  // Toda parada numérica é aceita pela API (5 a 500 km)
  assert.ok(PARADAS_DISTANCIA.every((km) => km === null || (km >= 5 && km <= 500)));
});

test("erro 500 mostra o código da requisição para o suporte", () => {
  assert.equal(
    mensagemDeErro({ detail: "Algo deu errado do nosso lado.", requisicao: "a1b2c3d4e5f60718" }),
    "Algo deu errado do nosso lado. (código a1b2c3d4e5f60718)",
  );
  assert.equal(mensagemDeErro({ detail: "Perfil ainda não criado" }), "Perfil ainda não criado");
});

test("tempo restante: minutos, horas e dias", () => {
  assert.equal(formatarRestante(59 * 60_000), "59:00");
  assert.equal(formatarRestante(3_600_000), "1 h 00 min");
  assert.equal(formatarRestante(24 * 3_600_000 - 60_000), "23 h 59 min");
  assert.equal(formatarRestante(24 * 3_600_000), "1 d 0 h");
  assert.equal(formatarRestante((3 * 24 + 4) * 3_600_000), "3 d 4 h");
});

test("nomes dos prazos das mensagens", () => {
  const esperado = {
    5: "5 minutos", 15: "15 minutos", 30: "30 minutos", 60: "1 hora", 360: "6 horas", 720: "12 horas",
    1440: "24 horas", 4320: "3 dias", 10080: "1 semana", 20160: "14 dias", 40320: "4 semanas",
    43200: "1 mês", 129600: "3 meses", 259200: "6 meses",
  };
  for (const [min, texto] of Object.entries(esperado)) assert.equal(rotuloPrazo(Number(min)), texto);
  assert.equal(rotuloPrazo(null), "nunca");
  assert.match(descreverPrazo(1440), /24 horas depois de lidas/);
  assert.match(descreverPrazo(null), /não somem/);
  assert.doesNotMatch(descreverPrazo(60), /ponta a ponta/); // nunca prometer E2EE
});
