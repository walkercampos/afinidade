"""Contratos da API (entrada e saída). Um bloco por domínio, na mesma ordem das rotas."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, field_validator, model_validator


def _normalizar(valor):
    # Precisa rodar ANTES do pattern: o StringConstraints valida o texto como chegou,
    # então "Fulano_1" seria rejeitado em vez de virar "fulano_1".
    return valor.strip().lower() if isinstance(valor, str) else valor


Slug = Annotated[str, BeforeValidator(_normalizar), StringConstraints(pattern=r"^[a-z0-9-]{1,40}$")]
Handle = Annotated[str, BeforeValidator(_normalizar), StringConstraints(pattern=r"^[a-z0-9_]{3,30}$")]

IDADE_MINIMA = 18
MAX_TAGS_POR_NIVEL = 100


# ---------- autenticação ----------


class Registro(BaseModel):
    # Opcional: sem apelido, o sistema gera um aleatório (ex.: anon_k3v9x2mq).
    handle: Handle | None = None
    senha: str = Field(min_length=10, max_length=128)
    data_nascimento: date
    confirmo_maior_de_idade: bool
    consinto_dados_sensiveis: bool

    @model_validator(mode="after")
    def exigir_maioridade_e_consentimento(self):
        hoje = date.today()
        n = self.data_nascimento
        idade = hoje.year - n.year - ((hoje.month, hoje.day) < (n.month, n.day))
        if idade < IDADE_MINIMA or not self.confirmo_maior_de_idade:
            raise ValueError("A plataforma é exclusiva para maiores de 18 anos")
        if not self.consinto_dados_sensiveis:
            raise ValueError("É necessário consentir com o tratamento de dados sensíveis")
        return self


class Login(BaseModel):
    handle: Handle
    senha: str = Field(max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 (tipo do token, não é senha)
    handle: str


# ---------- perfil ----------


class TagsInteresses(BaseModel):
    quero: list[Slug] = Field(default_factory=list, max_length=MAX_TAGS_POR_NIVEL)
    curioso: list[Slug] = Field(default_factory=list, max_length=MAX_TAGS_POR_NIVEL)
    limite_absoluto: list[Slug] = Field(default_factory=list, max_length=MAX_TAGS_POR_NIVEL)

    @field_validator("quero", "curioso", "limite_absoluto")
    @classmethod
    def sem_duplicatas(cls, v):
        return sorted(set(v))

    @model_validator(mode="after")
    def niveis_disjuntos(self):
        repetidas = (
            (set(self.quero) & set(self.curioso))
            | (set(self.quero) & set(self.limite_absoluto))
            | (set(self.curioso) & set(self.limite_absoluto))
        )
        if repetidas:
            raise ValueError(f"Cada tag só pode estar em um nível: {sorted(repetidas)}")
        return self


class PerfilEntrada(BaseModel):
    nome_exibicao: str = Field(min_length=1, max_length=40)
    bio: str | None = Field(default=None, max_length=500)
    genero: Slug
    busca_por: list[Slug] = Field(min_length=1, max_length=20)
    tags_interesses: TagsInteresses = Field(default_factory=TagsInteresses)
    visivel: bool = True


class Localizacao(BaseModel):
    """Coordenadas do aparelho. São convertidas numa célula de ~5 km e descartadas."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    distancia_max_km: int | None = Field(default=None, ge=5, le=500)


class LocalizacaoSalva(BaseModel):
    regiao: str | None = None  # célula geohash (~5 km), nunca a coordenada
    distancia_max_km: int | None = None


class PerfilProprio(PerfilEntrada):
    id: UUID
    localizacao: LocalizacaoSalva = Field(default_factory=LocalizacaoSalva)


class PerfilPublico(BaseModel):
    """O que outras pessoas veem. Limites absolutos ficam de fora: servem só para filtrar."""

    id: UUID
    nome_exibicao: str
    bio: str | None
    genero: str
    quero: list[str]
    curioso: list[str]


# ---------- fotos ----------


class Foto(BaseModel):
    id: UUID
    hash: str  # SHA-256 da imagem processada (sem metadados)
    nitida: bool  # se quem pediu pode ver a versão sem blur
    url: str


class SolicitacaoAcesso(BaseModel):
    visualizador: PerfilPublico
    status: Literal["pendente", "aprovado", "negado"]
    criado_em: datetime


class RespostaSolicitacao(BaseModel):
    aprovar: bool


# ---------- descoberta ----------


class Compatibilidade(BaseModel):
    match_valido: bool
    score_porcentagem: int
    score_mutuo: int
    similaridade: int = 0  # 0-100: quão parecidos são os gostos
    tags_em_comum: list[str] = []
    tags_mesmo_nivel: list[str] = []  # ambos querem, ou ambos têm curiosidade
    distancia_km: int | None = None  # em faixas de 5 km ("até N km")
    motivo: str


class Candidato(BaseModel):
    perfil: PerfilPublico
    compatibilidade: Compatibilidade
    fotos: list[Foto] = []


Ordem = Literal["compatibilidade", "afinidade", "recentes"]


class ItemCatalogo(BaseModel):
    slug: str
    rotulo: str
    categoria: str | None = None


class ResultadoCurtida(BaseModel):
    conexao: bool


# Endpoint /match/simular: mesmo formato do script original, sem banco nem catálogo.
class PerfilSimulado(BaseModel):
    id: str | None = None
    nome: str | None = None
    genero: str
    busca_por: list[str]
    tags_interesses: dict[str, list[str]] = {}


class Simulacao(BaseModel):
    usuario_a: PerfilSimulado
    usuario_b: PerfilSimulado


# ---------- moderação ----------

MotivoDenuncia = Literal[
    "assedio", "menor_de_idade", "perfil_falso", "spam", "conteudo_ilegal", "discurso_de_odio", "outro"
]


class Denuncia(BaseModel):
    motivo: MotivoDenuncia
    detalhes: str | None = Field(default=None, max_length=1000)
    # Anexa as últimas mensagens da conversa como evidência (só moderadores veem).
    incluir_mensagens: bool = False


class DenunciaNaFila(BaseModel):
    id: int
    motivo: str
    detalhes: str | None
    criado_em: datetime
    evidencias: list[dict] | None = None


class ContaNaFila(BaseModel):
    conta_id: UUID
    handle: str
    situacao: str
    perfil: PerfilPublico | None
    denuncias: list[DenunciaNaFila]


class Decisao(BaseModel):
    acao: Literal["banir", "restaurar"]
    observacao: str | None = Field(default=None, max_length=1000)


# ---------- chat ----------


class NovaMensagem(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class Mensagem(BaseModel):
    id: int
    minha: bool
    texto: str
    criado_em: datetime
    lida_em: datetime | None
    # Quando a mensagem some para os dois lados (5 min após a leitura).
    expira_em: datetime | None


class Conversa(BaseModel):
    perfil: PerfilPublico
    nao_lidas: int
    ultima_em: datetime | None
