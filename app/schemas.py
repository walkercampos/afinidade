from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

Slug = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9-]{1,40}$")]
Handle = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9_]{3,30}$")]

IDADE_MINIMA = 18
MAX_TAGS_POR_NIVEL = 100


class Registro(BaseModel):
    handle: Handle
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
    token_type: str = "bearer"


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
        repetidas = (set(self.quero) & set(self.curioso)) | (set(self.quero) & set(self.limite_absoluto)) \
            | (set(self.curioso) & set(self.limite_absoluto))
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


class PerfilProprio(PerfilEntrada):
    id: UUID


class PerfilPublico(BaseModel):
    """O que outras pessoas veem. Limites absolutos ficam de fora: servem só para filtrar."""
    id: UUID
    nome_exibicao: str
    bio: str | None
    genero: str
    quero: list[str]
    curioso: list[str]


class Compatibilidade(BaseModel):
    match_valido: bool
    score_porcentagem: int
    score_mutuo: int
    tags_em_comum: list[str] = []
    motivo: str


class Candidato(BaseModel):
    perfil: PerfilPublico
    compatibilidade: Compatibilidade


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
