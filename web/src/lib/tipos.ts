// Contratos da API, espelhando app/schemas.py (mesmos nomes de campo).

export interface ItemCatalogo { slug: string; rotulo: string; categoria: string | null }

export interface Token { access_token: string; token_type: string; handle: string; novo: boolean }
export interface VerificacaoEnviada { verificacao_id: string }
export interface MinhaConta { handle: string; email: string | null; moderador: boolean }
export interface Preferencias { modo_discreto: boolean }

export interface OpcoesPasskey { desafio_id: string; opcoes: Record<string, unknown> }
export interface PasskeySalva { id: string; nome: string; sincronizada: boolean; criado_em: string; usado_em: string | null }

export interface TagsInteresses { quero: string[]; curioso: string[]; limite_absoluto: string[] }
export interface LocalizacaoSalva { regiao: string | null; distancia_max_km: number | null }
export interface PerfilEntrada {
  nome_exibicao: string;
  bio: string | null;
  genero: string;
  busca_por: string[];
  tags_interesses: TagsInteresses;
  visivel: boolean;
}
export interface PerfilProprio extends PerfilEntrada { id: string; localizacao: LocalizacaoSalva }
export interface PerfilPublico {
  id: string;
  nome_exibicao: string;
  bio: string | null;
  genero: string;
  quero: string[];
  curioso: string[];
}

export interface Foto { id: string; hash: string; nitida: boolean; url: string }
export interface SolicitacaoAcesso { visualizador: PerfilPublico; status: "pendente" | "aprovado" | "negado"; criado_em: string }

export interface Compatibilidade {
  match_valido: boolean;
  score_porcentagem: number;
  score_mutuo: number;
  similaridade: number;
  tags_em_comum: string[];
  tags_mesmo_nivel: string[];
  distancia_km: number | null;
  motivo: string;
}
export interface Candidato { perfil: PerfilPublico; compatibilidade: Compatibilidade; fotos: Foto[] }
export type Ordem = "compatibilidade" | "afinidade" | "recentes";
export interface ResultadoCurtida { conexao: boolean }

export type MotivoDenuncia =
  | "assedio" | "menor_de_idade" | "perfil_falso" | "spam" | "conteudo_ilegal" | "discurso_de_odio" | "outro";
export interface DenunciaNaFila {
  id: number;
  motivo: string;
  detalhes: string | null;
  criado_em: string;
  evidencias: { de: string; texto: string }[] | null;
}
export interface ContaNaFila {
  conta_id: string;
  handle: string;
  situacao: string;
  perfil: PerfilPublico | null;
  denuncias: DenunciaNaFila[];
}

export interface Mensagem {
  id: number;
  minha: boolean;
  texto: string;
  criado_em: string;
  lida_em: string | null;
  ttl_minutos: number | null;
  expira_em: string | null;
}
export interface Conversa { perfil: PerfilPublico; nao_lidas: number; ultima_em: string | null }
export interface PropostaPrazo { ttl_minutos: number | null; minha: boolean; expira_em: string }
export interface PrazoConversa {
  ttl_minutos: number | null;
  padrao: number;
  opcoes: (number | null)[];
  proposta: PropostaPrazo | null;
}

export interface Encontro {
  id: string;
  local: string;
  observacoes: string;
  como_te_conhecem: string;
  contato_email: string;
  inicio_em: string;
  checkin_ate: string;
  situacao: "agendado" | "confirmado_ok" | "alerta_enviado" | "cancelado" | string;
  com_nome: string | null;
  com_handle: string | null;
}

export interface VersaoTermos { versao: string; termos_url: string; privacidade_url: string }
export interface SituacaoTermos { versao_atual: string; aceita: boolean; versao_aceita: string | null; aceitos_em: string | null }
export interface SituacaoIdade { obrigatoria: boolean; verificada: boolean; verificada_em: string | null; pendente: boolean; disponivel: boolean }
