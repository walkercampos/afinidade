// Biometria (WebAuthn). O servidor fala JSON (bytes em base64url); o navegador, ArrayBuffer.
import { api, MODO_DEMO } from "./api";
import type { OpcoesPasskey, PasskeySalva, Token } from "./tipos";

type Json = Record<string, any>;

export const suportaPasskeys = () =>
  MODO_DEMO || Boolean(window.PublicKeyCredential && navigator.credentials?.create);

function b64urlParaBytes(texto: string): Uint8Array<ArrayBuffer> {
  const b64 = texto.replace(/-/g, "+").replace(/_/g, "/");
  const binario = atob(b64 + "===".slice((b64.length + 3) % 4));
  return Uint8Array.from(binario, (c) => c.charCodeAt(0));
}

function bytesParaB64url(buffer: ArrayBuffer): string {
  let binario = "";
  for (const byte of new Uint8Array(buffer)) binario += String.fromCharCode(byte);
  return btoa(binario).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const comIdsEmBytes = (lista?: Json[]) => (lista ?? []).map((c) => ({ ...c, id: b64urlParaBytes(c.id) }));

function opcoesDeCriacao(json: Json): PublicKeyCredentialCreationOptions {
  return {
    ...json,
    challenge: b64urlParaBytes(json.challenge),
    user: { ...json.user, id: b64urlParaBytes(json.user.id) },
    excludeCredentials: comIdsEmBytes(json.excludeCredentials),
  } as unknown as PublicKeyCredentialCreationOptions;
}

function opcoesDeLogin(json: Json): PublicKeyCredentialRequestOptions {
  return {
    ...json, challenge: b64urlParaBytes(json.challenge), allowCredentials: comIdsEmBytes(json.allowCredentials),
  } as unknown as PublicKeyCredentialRequestOptions;
}

function credencialParaJSON(credencial: PublicKeyCredential): Json {
  const r = credencial.response as AuthenticatorAttestationResponse & AuthenticatorAssertionResponse;
  const json: Json = {
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

function mensagemDeErroPasskey(erro: unknown): string {
  const e = erro as { name?: string; message?: string };
  switch (e?.name) {
    case "NotAllowedError": return "Operação cancelada ou tempo esgotado. Tente de novo.";
    case "InvalidStateError": return "Este aparelho já tem uma passkey desta conta.";
    case "SecurityError": return "A biometria só funciona em HTTPS (ou em localhost).";
    case "NotSupportedError": return "Este navegador ou aparelho não suporta biometria.";
    case "AbortError": return "Operação cancelada.";
    default: return e?.message || "Não foi possível usar a biometria.";
  }
}

async function noAparelho(acao: () => Promise<Credential | null>): Promise<Json> {
  if (MODO_DEMO) return { demo: true };
  try {
    return credencialParaJSON((await acao()) as PublicKeyCredential);
  } catch (e) {
    throw new Error(mensagemDeErroPasskey(e));
  }
}

/** Entra sem digitar nada: o aparelho mostra as passkeys que tem para este site. */
export async function entrarComPasskey(): Promise<Token> {
  const { desafio_id, opcoes } = await api<OpcoesPasskey>("/auth/passkey/login/opcoes", { metodo: "POST" });
  const credencial = await noAparelho(() => navigator.credentials.get({ publicKey: opcoesDeLogin(opcoes) }));
  return api<Token>("/auth/passkey/login", { metodo: "POST", corpo: { desafio_id, credencial } });
}

export async function adicionarPasskey(nome: string): Promise<PasskeySalva> {
  const { desafio_id, opcoes } = await api<OpcoesPasskey>("/passkeys/opcoes", { metodo: "POST" });
  const credencial = await noAparelho(() => navigator.credentials.create({ publicKey: opcoesDeCriacao(opcoes) }));
  return api<PasskeySalva>("/passkeys", { metodo: "POST", corpo: { desafio_id, credencial, nome: nome || null } });
}
