import { irPara } from "./roteador.js";
import {
  credencialParaJSON, mensagemDeErro, mensagemDeErroPasskey, opcoesDeCriacao, opcoesDeLogin,
} from "./util.js";

export class ErroApi extends Error {
  constructor(status, detalhe) { super(detalhe); this.status = status; }
}

// Todo pedido que altera dados leva X-CSRF (o servidor recusa sem ele quando usa o cookie).
const CABECALHOS = { "X-CSRF": "1" };

async function tratar(r, caminho) {
  if (r.status === 401 && !caminho.startsWith("/auth/")) {
    irPara("entrar");
    throw new ErroApi(401, "Sessão expirada");
  }
  if (r.status === 204) return null;
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErroApi(r.status, mensagemDeErro(dados));
  return dados;
}

export async function api(caminho, { metodo = "GET", corpo } = {}) {
  const r = await fetch(`/api${caminho}`, {
    method: metodo,
    credentials: "same-origin",
    headers: { ...CABECALHOS, "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  return tratar(r, caminho);
}

/** Envia um arquivo cru (o servidor lê o corpo como bytes da imagem). */
export async function enviarArquivo(caminho, arquivo) {
  const r = await fetch(`/api${caminho}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { ...CABECALHOS, "Content-Type": arquivo.type },
    body: arquivo,
  });
  return tratar(r, caminho);
}

/** Usado pelo pânico: dispara e não espera (keepalive sobrevive à troca de página). */
export function encerrarSessaoSemEsperar() {
  fetch("/api/auth/sair", { method: "POST", credentials: "same-origin", headers: CABECALHOS, keepalive: true })
    .catch(() => {});
}

let catalogo = null;
export async function carregarCatalogo() {
  if (!catalogo) {
    const [generos, tags] = await Promise.all([api("/catalogo/generos"), api("/catalogo/tags")]);
    catalogo = { generos, tags, rotulo: new Map([...generos, ...tags].map((i) => [i.slug, i.rotulo])) };
  }
  return catalogo;
}

export const rotulo = (slug) => catalogo?.rotulo.get(slug) ?? slug;

// ---------- passkeys ----------

export const suportaPasskeys = () => Boolean(window.PublicKeyCredential && navigator.credentials?.create);

/** Roda a cerimônia no aparelho; erros do navegador viram mensagens amigáveis. */
async function noAparelho(acao) {
  try {
    return credencialParaJSON(await acao());
  } catch (e) {
    throw new Error(mensagemDeErroPasskey(e));
  }
}

/** Entra sem digitar nada: o aparelho mostra as passkeys que tem para este site. */
export async function entrarComPasskey() {
  const { desafio_id, opcoes } = await api("/auth/passkey/login/opcoes", { metodo: "POST" });
  const credencial = await noAparelho(() => navigator.credentials.get({ publicKey: opcoesDeLogin(opcoes) }));
  return api("/auth/passkey/login", { metodo: "POST", corpo: { desafio_id, credencial } });
}

export async function adicionarPasskey(nome) {
  const { desafio_id, opcoes } = await api("/passkeys/opcoes", { metodo: "POST" });
  const credencial = await noAparelho(() => navigator.credentials.create({ publicKey: opcoesDeCriacao(opcoes) }));
  return api("/passkeys", { metodo: "POST", corpo: { desafio_id, credencial, nome: nome || null } });
}

// ---------- e-mail (código de 6 dígitos ou link) ----------

export const pedirCodigoCadastro = (dados) => api("/auth/email/cadastro", { metodo: "POST", corpo: dados });
export const pedirCodigoEntrar = (email) => api("/auth/email/entrar", { metodo: "POST", corpo: { email } });
export const confirmarCodigo = (verificacao_id, codigo) =>
  api("/auth/email/confirmar", { metodo: "POST", corpo: { verificacao_id, codigo } });
export const confirmarLink = (token) => api("/auth/email/link", { metodo: "POST", corpo: { token } });
