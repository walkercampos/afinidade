// Funções puras (sem DOM nem rede): testadas com `node --test` em tests/js/.

export const DESTINO_PANICO = "https://www.google.com/";

/** Executa o botão de pânico. O ambiente é injetado para poder ser testado. */
export function executarPanico({ armazenamentos, limparTela, encerrarSessao, navegar }) {
  // 1) apaga a tela primeiro: nada fica visível nem por um quadro
  try { limparTela(); } catch { /* segue */ }
  // 2) limpa tudo o que o navegador guardou para este site
  for (const a of armazenamentos) {
    try { a.clear(); } catch { /* modo privado ou bloqueado: segue */ }
  }
  // 3) derruba a sessão no servidor sem esperar a resposta
  try { encerrarSessao(); } catch { /* segue */ }
  // 4) troca a página atual (replace: o "voltar" não retorna para o app)
  navegar(DESTINO_PANICO);
}

/** Milissegundos até `iso` (negativo se já passou). */
export function msAte(iso, agora = Date.now()) {
  return Date.parse(iso) - agora;
}

/** "4:05" a partir de milissegundos; nunca negativo. */
export function formatarRestante(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function descreverDistancia(km) {
  return km == null ? null : `até ${km} km`;
}

/** Texto amigável a partir do corpo de erro do FastAPI. */
export function mensagemDeErro(dados) {
  const d = dados?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((e) => String(e.msg).replace(/^Value error, /, "")).join(" · ");
  return "Algo deu errado. Tente de novo.";
}

/** Separa "#/chat/<id>" em { rota: "chat", parametro: "<id>" }. */
export function lerRota(hash) {
  const [rota = "", parametro = null] = hash.replace(/^#\/?/, "").split("/");
  return { rota: rota || "descobrir", parametro };
}

/**
 * Achata listas e descarta vazios (null, undefined, false) antes de inserir no DOM.
 * Sem isso, um array vira o texto "[object HTMLElement]" e um null vira "null".
 */
export function normalizarFilhos(filhos) {
  return filhos.flat(Infinity).filter((f) => f != null && f !== false);
}

// ---------- passkeys (WebAuthn) ----------
// O servidor fala JSON (bytes em base64url); a API do navegador fala ArrayBuffer.

export function b64urlParaBytes(texto) {
  const b64 = texto.replace(/-/g, "+").replace(/_/g, "/");
  const binario = atob(b64 + "===".slice((b64.length + 3) % 4));
  return Uint8Array.from(binario, (c) => c.charCodeAt(0));
}

export function bytesParaB64url(buffer) {
  let binario = "";
  for (const byte of new Uint8Array(buffer)) binario += String.fromCharCode(byte);
  return btoa(binario).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const comIdsEmBytes = (lista) => (lista ?? []).map((c) => ({ ...c, id: b64urlParaBytes(c.id) }));

/** Opções do servidor → formato de navigator.credentials.create({ publicKey }). */
export function opcoesDeCriacao(json) {
  return {
    ...json,
    challenge: b64urlParaBytes(json.challenge),
    user: { ...json.user, id: b64urlParaBytes(json.user.id) },
    excludeCredentials: comIdsEmBytes(json.excludeCredentials),
  };
}

/** Opções do servidor → formato de navigator.credentials.get({ publicKey }). */
export function opcoesDeLogin(json) {
  return { ...json, challenge: b64urlParaBytes(json.challenge), allowCredentials: comIdsEmBytes(json.allowCredentials) };
}

/** PublicKeyCredential → JSON que o servidor entende (serve para criação e para login). */
export function credencialParaJSON(credencial) {
  const r = credencial.response;
  const json = {
    id: credencial.id,
    rawId: bytesParaB64url(credencial.rawId),
    type: credencial.type,
    authenticatorAttachment: credencial.authenticatorAttachment ?? null,
    clientExtensionResults: credencial.getClientExtensionResults?.() ?? {},
    response: { clientDataJSON: bytesParaB64url(r.clientDataJSON) },
  };
  if (r.attestationObject) {
    json.response.attestationObject = bytesParaB64url(r.attestationObject);
    json.response.transports = r.getTransports?.() ?? [];
  } else {
    json.response.authenticatorData = bytesParaB64url(r.authenticatorData);
    json.response.signature = bytesParaB64url(r.signature);
    json.response.userHandle = r.userHandle ? bytesParaB64url(r.userHandle) : null;
  }
  return json;
}

/** Mensagem amigável para os erros que o navegador lança nas cerimônias de passkey. */
export function mensagemDeErroPasskey(erro) {
  switch (erro?.name) {
    case "NotAllowedError": return "Operação cancelada ou tempo esgotado. Tente de novo.";
    case "InvalidStateError": return "Este aparelho já tem uma passkey desta conta.";
    case "SecurityError": return "Passkeys só funcionam em HTTPS (ou em localhost).";
    case "NotSupportedError": return "Este navegador ou aparelho não suporta passkeys.";
    case "AbortError": return "Operação cancelada.";
    default: return erro?.message || "Não foi possível usar a passkey.";
  }
}
