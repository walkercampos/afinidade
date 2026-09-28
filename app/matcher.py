"""Núcleo do matchmaking: porta fiel do algoritmo original, sem dependência de banco.

Os perfis usam conjuntos (frozenset) para que as operações de interseção sejam O(min(n, m)).
Os elementos podem ser slugs (str) ou IDs numéricos do catálogo (int) — o algoritmo não se importa.
"""
from dataclasses import dataclass, field
from typing import Hashable, Iterable

PESO_QUERO_MUTUO = 3
PESO_QUERO_CURIOSO = 2
PESO_CURIOSO_MUTUO = 1

MOTIVO_GENERO = "Incompatibilidade de gênero ou busca"
MOTIVO_LIMITES = "Conflito severo de limites absolutos"
MOTIVO_OK = "Compatibilidade calculada com sucesso"


@dataclass(frozen=True)
class PerfilMatch:
    id: Hashable
    genero: Hashable
    busca_por: frozenset = field(default_factory=frozenset)
    quero: frozenset = field(default_factory=frozenset)
    curioso: frozenset = field(default_factory=frozenset)
    limite_absoluto: frozenset = field(default_factory=frozenset)

    @classmethod
    def criar(cls, id, genero, busca_por: Iterable, quero: Iterable = (),
              curioso: Iterable = (), limite_absoluto: Iterable = ()):
        return cls(id, genero, frozenset(busca_por), frozenset(quero),
                   frozenset(curioso), frozenset(limite_absoluto))

    @classmethod
    def de_dict(cls, dados: dict):
        """Aceita o mesmo payload do script original."""
        tags = dados.get("tags_interesses", {})
        return cls.criar(
            dados.get("id"), dados["genero"], dados["busca_por"],
            tags.get("quero", []), tags.get("curioso", []), tags.get("limite_absoluto", []),
        )


@dataclass(frozen=True)
class ResultadoMatch:
    match_valido: bool
    score_porcentagem: int
    motivo: str
    tags_em_comum: tuple = ()

    def to_dict(self):
        resultado = {"match_valido": self.match_valido, "score_porcentagem": self.score_porcentagem}
        if self.match_valido:
            resultado["tags_em_comum"] = sorted(self.tags_em_comum, key=str)
        resultado["motivo"] = self.motivo
        return resultado


def generos_compativeis(a: PerfilMatch, b: PerfilMatch) -> bool:
    """Camada 1 — A busca o gênero de B **e** B busca o gênero de A."""
    return b.genero in a.busca_por and a.genero in b.busca_por


def limites_conflitam(a: PerfilMatch, b: PerfilMatch) -> bool:
    """Camada 2 — algum limite absoluto de um é algo que o outro QUER praticar."""
    return bool(a.limite_absoluto & b.quero) or bool(b.limite_absoluto & a.quero)


def calcular_match(a: PerfilMatch, b: PerfilMatch) -> ResultadoMatch:
    """Compatibilidade de B **do ponto de vista de A** (normalizada pelos desejos de A)."""
    if not generos_compativeis(a, b):
        return ResultadoMatch(False, 0, MOTIVO_GENERO)

    if limites_conflitam(a, b):
        return ResultadoMatch(False, 0, MOTIVO_LIMITES)

    # Camada 3 — afinidade ponderada
    mutual_quero = a.quero & b.quero
    quero_a_curioso_b = a.quero & b.curioso
    quero_b_curioso_a = b.quero & a.curioso
    mutual_curioso = a.curioso & b.curioso

    score = (
        len(mutual_quero) * PESO_QUERO_MUTUO
        + (len(quero_a_curioso_b) + len(quero_b_curioso_a)) * PESO_QUERO_CURIOSO
        + len(mutual_curioso) * PESO_CURIOSO_MUTUO
    )

    # Cenário ideal: B atende perfeitamente a todos os desejos de A
    max_possivel = len(a.quero) * PESO_QUERO_MUTUO + len(a.curioso) * PESO_CURIOSO_MUTUO
    percentual = 0 if max_possivel == 0 else min(100, round(score / max_possivel * 100))

    tags_comuns = tuple(mutual_quero | quero_a_curioso_b | quero_b_curioso_a)
    return ResultadoMatch(True, percentual, MOTIVO_OK, tags_comuns)


def score_mutuo(a: PerfilMatch, b: PerfilMatch) -> int:
    """Média dos dois pontos de vista.

    O score original é assimétrico (normaliza só pelos desejos de A): quem tem 1 tag
    "quero" pode ver 100% com alguém que vê 10% de volta. Para ranquear o feed, a média
    dos dois lados evita empurrar conexões desequilibradas para o topo.
    """
    ab = calcular_match(a, b)
    if not ab.match_valido:
        return 0
    ba = calcular_match(b, a)
    return round((ab.score_porcentagem + ba.score_porcentagem) / 2)
