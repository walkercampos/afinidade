// Modo demonstração (npm run demo): responde às mesmas rotas da API com dados de exemplo,
// em memória. Serve para ver e ajustar a interface sem subir o back-end e o banco.
import { ErroApi, type Resposta } from "./api";
import type {
  Candidato, ContaNaFila, Conversa, Encontro, Foto, ItemCatalogo, Mensagem, PasskeySalva, PerfilProprio,
  PerfilPublico, PrazoConversa, SolicitacaoAcesso,
} from "./tipos";

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));
const agora = () => new Date().toISOString();
const minutosAtras = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

function imagem(cor1: string, cor2: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${cor1}"/><stop offset="1" stop-color="${cor2}"/></linearGradient></defs>
<rect width="400" height="500" fill="url(#g)"/>
<circle cx="200" cy="200" r="78" fill="#fff" fill-opacity=".28"/>
<path d="M60 500c10-110 70-170 140-170s130 60 140 170z" fill="#fff" fill-opacity=".28"/></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const generos: ItemCatalogo[] = [
  { slug: "mulher", rotulo: "Mulher", categoria: null },
  { slug: "homem", rotulo: "Homem", categoria: null },
  { slug: "nao-binarie", rotulo: "Pessoa não binária", categoria: null },
  { slug: "mulher-trans", rotulo: "Mulher trans", categoria: null },
  { slug: "homem-trans", rotulo: "Homem trans", categoria: null },
  { slug: "casal", rotulo: "Casal", categoria: null },
];

const tags: ItemCatalogo[] = [
  ["massagem", "Massagem", "sensacao"], ["vendas", "Vendas nos olhos", "sensacao"], ["temperatura", "Brincar com temperatura", "sensacao"],
  ["dominacao", "Dominação", "dinamica"], ["submissao", "Submissão", "dinamica"], ["switch", "Alternar papéis", "dinamica"],
  ["roleplay", "Roleplay", "fantasia"], ["fantasias", "Contar fantasias", "fantasia"], ["fantasias-publicas", "Lugares inusitados", "fantasia"],
  ["exibicionismo", "Exibicionismo", "exposicao"], ["voyeurismo", "Voyeurismo", "exposicao"], ["fotos", "Trocar fotos", "exposicao"],
  ["poliamor", "Poliamor", "relacao"], ["swing", "Swing", "relacao"], ["casual", "Algo casual", "relacao"],
].map(([slug, rotulo, categoria]) => ({ slug, rotulo, categoria }));

const pessoas: (PerfilPublico & { fotos: Foto[]; compat: Candidato["compatibilidade"] })[] = [
  {
    id: "leo", nome_exibicao: "Leo", genero: "homem",
    bio: "Gosto de conversa boa antes de qualquer coisa. Café, vinil e viagens de última hora.",
    quero: ["massagem", "roleplay", "vendas"], curioso: ["switch", "temperatura"],
    fotos: [{ id: "f-leo", hash: "x", nitida: false, url: imagem("#f43f5e", "#7c3aed") }],
    compat: { match_valido: true, score_porcentagem: 92, score_mutuo: 88, similaridade: 74, tags_em_comum: ["massagem", "roleplay", "vendas"], tags_mesmo_nivel: ["massagem", "roleplay"], distancia_km: 10, motivo: "" },
  },
  {
    id: "mar", nome_exibicao: "Mar", genero: "nao-binarie",
    bio: "Artista, noturna e curiosa. Respeito e combinados claros acima de tudo.",
    quero: ["fantasias", "fotos", "poliamor"], curioso: ["exibicionismo", "massagem"],
    fotos: [{ id: "f-mar", hash: "x", nitida: true, url: imagem("#06b6d4", "#8b5cf6") }],
    compat: { match_valido: true, score_porcentagem: 81, score_mutuo: 76, similaridade: 61, tags_em_comum: ["fantasias", "massagem"], tags_mesmo_nivel: ["fantasias"], distancia_km: 25, motivo: "" },
  },
  {
    id: "lia", nome_exibicao: "Lia", genero: "mulher",
    bio: "Recém-chegada na cidade. Quero conhecer gente que topa sair do óbvio.",
    quero: ["dominacao", "vendas", "casual"], curioso: ["roleplay"],
    fotos: [{ id: "f-lia", hash: "x", nitida: false, url: imagem("#f59e0b", "#e11d48") }],
    compat: { match_valido: true, score_porcentagem: 73, score_mutuo: 69, similaridade: 52, tags_em_comum: ["vendas", "roleplay"], tags_mesmo_nivel: ["vendas"], distancia_km: 5, motivo: "" },
  },
  {
    id: "rafa", nome_exibicao: "Rafa & Bia", genero: "casal",
    bio: "Casal leve, bem resolvido, procurando amizades com química.",
    quero: ["swing", "fantasias"], curioso: ["voyeurismo", "massagem"],
    fotos: [],
    compat: { match_valido: true, score_porcentagem: 64, score_mutuo: 58, similaridade: 40, tags_em_comum: ["massagem"], tags_mesmo_nivel: [], distancia_km: 40, motivo: "" },
  },
];

const publico = ({ id, nome_exibicao, bio, genero, quero, curioso }: PerfilPublico): PerfilPublico =>
  ({ id, nome_exibicao, bio, genero, quero, curioso });

// ---------- estado em memória ----------
let logado = false;
let termosAceitos = true;
let perfil: PerfilProprio | null = {
  id: "eu", nome_exibicao: "Você", bio: "Perfil de demonstração.", genero: "mulher", busca_por: ["homem", "nao-binarie"],
  tags_interesses: { quero: ["massagem", "roleplay"], curioso: ["fantasias", "vendas"], limite_absoluto: ["swing"] },
  visivel: true, localizacao: { regiao: "6gkz", distancia_max_km: 25 },
};
let minhasFotos: Foto[] = [{ id: "minha-1", hash: "x", nitida: true, url: imagem("#e11d48", "#8b5cf6") }];
let solicitacoes: SolicitacaoAcesso[] = [
  { visualizador: publico(pessoas[1]), status: "pendente", criado_em: minutosAtras(30) },
];
let passkeys: PasskeySalva[] = [
  { id: "pk1", nome: "Celular", sincronizada: true, criado_em: minutosAtras(60 * 24 * 10), usado_em: minutosAtras(5) },
];
let discreto = false;
const conexoes = new Set(["mar", "leo"]);
const vistos = new Set<string>();
let proximoId = 100;
const conversas: Record<string, Mensagem[]> = {
  mar: [
    { id: 1, minha: false, texto: "Oi! Vi que a gente curte várias coisas em comum 😊", criado_em: minutosAtras(50), lida_em: minutosAtras(45), ttl_minutos: 1440, expira_em: new Date(Date.now() + 23 * 3600_000).toISOString() },
    { id: 2, minha: true, texto: "Oi, Mar! Vi sim. Adorei sua bio, que tipo de arte você faz?", criado_em: minutosAtras(40), lida_em: minutosAtras(38), ttl_minutos: 1440, expira_em: new Date(Date.now() + 23.5 * 3600_000).toISOString() },
    { id: 3, minha: false, texto: "Ilustração e um pouco de fotografia. Te mostro um dia, se rolar 📷", criado_em: minutosAtras(3), lida_em: null, ttl_minutos: 1440, expira_em: null },
  ],
  leo: [],
};
const naoLidas: Record<string, number> = { mar: 1, leo: 0 };
const prazos: Record<string, PrazoConversa> = {};
const prazoDe = (id: string): PrazoConversa =>
  (prazos[id] ??= { ttl_minutos: 1440, padrao: 1440, opcoes: [5, 60, 1440, 10080, 43200, 259200, null], proposta: null });
let encontros: Encontro[] = [];
const fila: ContaNaFila[] = [
  {
    conta_id: "c1", handle: "anon_k3v9x2mq", situacao: "em_revisao", perfil: publico(pessoas[3]),
    denuncias: [{ id: 1, motivo: "perfil_falso", detalhes: "Fotos parecem de banco de imagens.", criado_em: minutosAtras(120), evidencias: null }],
  },
];

function ok<T>(dados: T, cabecalhos: Record<string, string> = {}): Resposta<T> {
  // Cópia, como numa resposta de rede: a tela nunca recebe (nem altera) o estado interno.
  return { dados: structuredClone(dados), cabecalhos: new Headers(cabecalhos) };
}

function exigirLogin() {
  if (!logado) throw new ErroApi(401, "Sessão expirada");
}

const token = { access_token: "demo", token_type: "bearer", handle: "voce_demo", novo: false };

export async function responderDemo<T>(metodo: string, caminhoCompleto: string, corpo?: unknown): Promise<Resposta<T>> {
  await espera(250 + Math.random() * 250);
  const [caminho, busca = ""] = caminhoCompleto.split("?");
  const params = new URLSearchParams(busca);
  const c = corpo as Record<string, any>;
  const r = (dados: unknown, cab?: Record<string, string>) => ok(dados as T, cab);
  const m = (padrao: RegExp) => caminho.match(padrao);
  let p: RegExpMatchArray | null;

  // ----- sem sessão -----
  if (caminho === "/catalogo/generos") return r(generos);
  if (caminho === "/catalogo/tags") return r(tags);
  if (caminho === "/termos") return r({ versao: "2026-05-01", termos_url: "#/termos", privacidade_url: "#/termos" });
  if (caminho === "/auth/email/entrar" || caminho === "/auth/email/cadastro") return r({ verificacao_id: "demo" });
  if (caminho === "/auth/email/confirmar") {
    if (c?.codigo !== "123456") throw new ErroApi(400, "Código inválido ou expirado. No modo demonstração, use 123456.");
    logado = true;
    return r({ ...token, novo: false });
  }
  if (caminho === "/auth/email/link" || caminho === "/auth/passkey/login") { logado = true; return r(token); }
  if (caminho === "/auth/passkey/login/opcoes" || caminho === "/passkeys/opcoes") return r({ desafio_id: "demo", opcoes: {} });
  if (caminho === "/auth/sair") { logado = false; return r(null); }

  exigirLogin();

  // ----- conta -----
  if (caminho === "/conta" && metodo === "GET") return r({ handle: "voce_demo", email: "v****@exemplo.com", moderador: true });
  if (caminho === "/conta" && metodo === "DELETE") { logado = false; return r(null); }
  if (caminho === "/conta/preferencias") {
    if (metodo === "PUT") discreto = Boolean(c.modo_discreto);
    return r({ modo_discreto: discreto });
  }
  if (caminho === "/termos/situacao") return r({ versao_atual: "2026-05-01", aceita: termosAceitos, versao_aceita: null, aceitos_em: null });
  if (caminho === "/termos/aceitar") { termosAceitos = true; return r({ versao_atual: "2026-05-01", aceita: true, versao_aceita: "2026-05-01", aceitos_em: agora() }); }
  if (caminho === "/idade") return r({ obrigatoria: false, verificada: true, verificada_em: minutosAtras(9000), pendente: false, disponivel: true });
  if (caminho === "/idade/iniciar") return r({ url: "#/idade-simulada/demo" });
  if ((p = m(/^\/idade\/simulado\//))) return r(null);

  // ----- passkeys -----
  if (caminho === "/passkeys" && metodo === "GET") return r(passkeys);
  if (caminho === "/passkeys" && metodo === "POST") {
    const nova = { id: `pk${proximoId++}`, nome: c.nome || "Este aparelho", sincronizada: true, criado_em: agora(), usado_em: null };
    passkeys = [...passkeys, nova];
    return r(nova);
  }
  if ((p = m(/^\/passkeys\/(.+)$/))) { passkeys = passkeys.filter((k) => k.id !== p![1]); return r(null); }

  // ----- perfil -----
  if (caminho === "/perfil") {
    if (metodo === "PUT") perfil = { ...(perfil ?? { id: "eu", localizacao: { regiao: null, distancia_max_km: null } }), ...c } as PerfilProprio;
    if (!perfil) throw new ErroApi(404, "Perfil não encontrado");
    return r(perfil);
  }
  if (caminho === "/perfil/localizacao" && perfil) {
    perfil.localizacao = metodo === "DELETE"
      ? { regiao: null, distancia_max_km: null }
      : { regiao: "6gkz", distancia_max_km: c.distancia_max_km ?? null };
    return r(metodo === "DELETE" ? null : perfil.localizacao);
  }
  if (caminho === "/perfil/distancia" && perfil) {
    perfil.localizacao.distancia_max_km = c.distancia_max_km ?? null;
    return r(perfil.localizacao);
  }

  // ----- fotos -----
  if (caminho === "/fotos" && metodo === "GET") return r(minhasFotos);
  if (caminho === "/fotos" && metodo === "POST") {
    const arquivo = corpo as File;
    const nova = { id: `minha-${proximoId++}`, hash: "x", nitida: true, url: URL.createObjectURL(arquivo) };
    minhasFotos = [...minhasFotos, nova];
    return r(nova);
  }
  if (caminho === "/fotos/solicitacoes") return r(solicitacoes.filter((s) => s.status === "pendente"));
  if ((p = m(/^\/fotos\/solicitacoes\/(.+)$/))) {
    solicitacoes = solicitacoes.filter((s) => s.visualizador.id !== p![1]);
    return r(null);
  }
  if ((p = m(/^\/fotos\/([^/]+)$/)) && metodo === "DELETE") { minhasFotos = minhasFotos.filter((f) => f.id !== p![1]); return r(null); }
  if ((p = m(/^\/perfis\/([^/]+)\/fotos\/solicitar$/))) return r({ status: "pendente" });

  // ----- descoberta -----
  if (caminho === "/descobrir" || caminho === "/afins") {
    const ordem = params.get("ordem");
    let lista = pessoas.filter((x) => !vistos.has(x.id));
    if (params.get("com_foto")) lista = lista.filter((x) => x.fotos.length);
    if (ordem === "afinidade") lista = [...lista].sort((a, b) => b.compat.similaridade - a.compat.similaridade);
    if (ordem === "recentes") lista = [...lista].reverse();
    return r(lista.map((x) => ({ perfil: publico(x), compatibilidade: x.compat, fotos: x.fotos })));
  }
  if ((p = m(/^\/perfis\/([^/]+)\/curtir$/))) {
    vistos.add(p[1]);
    const conexao = p[1] !== "lia";
    if (conexao) { conexoes.add(p[1]); conversas[p[1]] ??= []; naoLidas[p[1]] ??= 0; }
    return r({ conexao });
  }
  if ((p = m(/^\/perfis\/([^/]+)\/(bloquear|denunciar)$/))) {
    vistos.add(p[1]);
    conexoes.delete(p[1]);
    return r(null);
  }
  if (caminho === "/conexoes") return r(pessoas.filter((x) => conexoes.has(x.id)).map(publico));

  // ----- chat -----
  if (caminho === "/conversas") {
    const lista: Conversa[] = pessoas.filter((x) => conexoes.has(x.id)).map((x) => ({
      perfil: publico(x), nao_lidas: naoLidas[x.id] ?? 0, ultima_em: conversas[x.id]?.at(-1)?.criado_em ?? null,
    }));
    return r(lista.sort((a, b) => (b.ultima_em ?? "").localeCompare(a.ultima_em ?? "")));
  }
  if ((p = m(/^\/conversas\/([^/]+)\/mensagens$/))) {
    const id = p[1];
    const lista = (conversas[id] ??= []);
    if (metodo === "POST") {
      const ttl = prazoDe(id).ttl_minutos;
      const nova: Mensagem = { id: proximoId++, minha: true, texto: c.texto, criado_em: agora(), lida_em: null, ttl_minutos: ttl, expira_em: null };
      lista.push(nova);
      // a outra pessoa "lê" um pouco depois, e o relógio começa a correr
      setTimeout(() => {
        nova.lida_em = agora();
        nova.expira_em = ttl == null ? null : new Date(Date.now() + ttl * 60_000).toISOString();
      }, 4000);
      return r(nova);
    }
    if (metodo === "DELETE") { conversas[id] = lista.filter((x) => !x.minha); return r(null); }
    naoLidas[id] = 0;
    for (const x of lista) {
      if (!x.minha && !x.lida_em) {
        x.lida_em = agora();
        x.expira_em = x.ttl_minutos == null ? null : new Date(Date.now() + x.ttl_minutos * 60_000).toISOString();
      }
    }
    return r(lista.filter((x) => !x.expira_em || Date.parse(x.expira_em) > Date.now()));
  }
  if ((p = m(/^\/conversas\/([^/]+)\/prazo$/))) {
    const prazo = prazoDe(p[1]);
    if (metodo === "POST") {
      prazo.proposta = { ttl_minutos: c.ttl_minutos, minha: true, expira_em: new Date(Date.now() + 86400_000).toISOString() };
    }
    return r(prazo);
  }
  if ((p = m(/^\/conversas\/([^/]+)\/prazo\/confirmar$/))) {
    const prazo = prazoDe(p[1]);
    if (prazo.proposta) prazo.ttl_minutos = prazo.proposta.ttl_minutos;
    prazo.proposta = null;
    return r(prazo);
  }
  if ((p = m(/^\/conversas\/([^/]+)\/prazo\/proposta$/))) { prazoDe(p[1]).proposta = null; return r(null); }

  // ----- encontros -----
  if (caminho === "/encontros" && metodo === "GET") return r(encontros);
  if (caminho === "/encontros" && metodo === "POST") {
    const com = pessoas.find((x) => x.id === c.com);
    const novo: Encontro = {
      id: `e${proximoId++}`, local: c.local, observacoes: c.observacoes, como_te_conhecem: c.como_te_conhecem,
      contato_email: c.contato_email, inicio_em: c.inicio_em, checkin_ate: c.checkin_ate, situacao: "agendado",
      com_nome: com?.nome_exibicao ?? null, com_handle: com ? com.id : null,
    };
    encontros = [novo, ...encontros];
    return r(novo);
  }
  if ((p = m(/^\/encontros\/([^/]+)\/(checkin|cancelar)$/))) {
    const situacao = p[2] === "checkin" ? "confirmado_ok" : "cancelado";
    encontros = encontros.map((e) => (e.id === p![1] ? { ...e, situacao } : e));
    return r(null);
  }

  // ----- moderação -----
  if (caminho === "/moderacao/fila") return r(fila);
  if ((p = m(/^\/moderacao\/contas\/([^/]+)\/decisao$/))) {
    const i = fila.findIndex((x) => x.conta_id === p![1]);
    if (i >= 0) fila.splice(i, 1);
    return r(null);
  }
  if (m(/^\/moderacao\/contas\/([^/]+)\/aviso$/)) return r(null);

  throw new ErroApi(404, `Rota de demonstração não encontrada: ${metodo} ${caminho}`);
}
