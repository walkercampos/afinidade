// Cliente da API. A sessão vive num cookie HttpOnly no mesmo domínio (o JavaScript nunca vê o
// token); todo pedido leva o header X-CSRF, que o servidor exige quando usa o cookie.
import { responderDemo } from "./demo";
import { irPara } from "./roteador";
import type { ItemCatalogo } from "./tipos";
import { mensagemDeErro } from "./util";

export const MODO_DEMO = import.meta.env.VITE_DEMO === "1";

export class ErroApi extends Error {
  status: number;
  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

const CABECALHOS = { "X-CSRF": "1" };
const IDADE_PENDENTE = "Verificação de idade pendente"; // igual a app/idade.py
const TERMOS_PENDENTE = "Aceite dos termos pendente"; // igual a app/termos.py

interface Opcoes {
  metodo?: "GET" | "POST" | "PUT" | "DELETE";
  corpo?: unknown;
  arquivo?: File;
  /** Não leva para outra tela em 401/403 (ex.: consultas silenciosas antes do login). */
  silencioso?: boolean;
}

export interface Resposta<T> { dados: T; cabecalhos: Headers }

async function tratar<T>(r: Response, caminho: string, silencioso: boolean): Promise<Resposta<T>> {
  if (r.status === 401 && !caminho.startsWith("/auth/") && !silencioso) {
    irPara("entrar");
    throw new ErroApi(401, "Sessão expirada");
  }
  if (r.status === 204) return { dados: null as T, cabecalhos: r.headers };
  const dados = await r.json().catch(() => ({}));
  if (r.status === 403 && !silencioso) {
    if (dados.detail === IDADE_PENDENTE) irPara("idade");
    if (dados.detail === TERMOS_PENDENTE) irPara("termos");
  }
  if (!r.ok) throw new ErroApi(r.status, mensagemDeErro(dados));
  return { dados: dados as T, cabecalhos: r.headers };
}

export async function apiCompleta<T>(caminho: string, op: Opcoes = {}): Promise<Resposta<T>> {
  const metodo = op.metodo ?? "GET";
  if (MODO_DEMO) {
    try {
      return await responderDemo<T>(metodo, caminho, op.corpo ?? op.arquivo);
    } catch (e) {
      if (e instanceof ErroApi && e.status === 401 && !op.silencioso) irPara("entrar");
      throw e;
    }
  }
  const r = await fetch(`/api${caminho}`, {
    method: metodo,
    credentials: "same-origin",
    headers: op.arquivo
      ? { ...CABECALHOS, "Content-Type": op.arquivo.type }
      : { ...CABECALHOS, "Content-Type": "application/json" },
    body: op.arquivo ?? (op.corpo === undefined ? undefined : JSON.stringify(op.corpo)),
  });
  return tratar<T>(r, caminho, Boolean(op.silencioso));
}

export async function api<T = unknown>(caminho: string, op: Opcoes = {}): Promise<T> {
  return (await apiCompleta<T>(caminho, op)).dados;
}

/** Usado pelo pânico: dispara e não espera (keepalive sobrevive à troca de página). */
export function encerrarSessaoSemEsperar() {
  if (MODO_DEMO) return;
  fetch("/api/auth/sair", { method: "POST", credentials: "same-origin", headers: CABECALHOS, keepalive: true })
    .catch(() => {});
}

// ---------- catálogo (gêneros e interesses) ----------

export interface Catalogo { generos: ItemCatalogo[]; tags: ItemCatalogo[]; rotulo: Map<string, string> }
let catalogo: Promise<Catalogo> | null = null;

export function carregarCatalogo(): Promise<Catalogo> {
  catalogo ??= Promise.all([api<ItemCatalogo[]>("/catalogo/generos"), api<ItemCatalogo[]>("/catalogo/tags")])
    .then(([generos, tags]) => ({
      generos, tags, rotulo: new Map([...generos, ...tags].map((i) => [i.slug, i.rotulo])),
    }))
    .catch((e) => { catalogo = null; throw e; });
  return catalogo;
}
