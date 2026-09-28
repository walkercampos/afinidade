"""Consulta de candidatos: as três camadas do algoritmo + distância, tudo no Postgres.

Camadas 1 e 2 e distância -> WHERE (com índices GIN / lat_aprox).
Camada 3 e similaridade  -> expressões com intarray, usadas no ORDER BY.

As fórmulas aqui espelham `matcher.calcular_match`, `matcher.score_mutuo` e
`matcher.similaridade` exatamente (inclusive arredondamento); `tests/test_paridade.py`
compara os dois lados em perfis aleatórios.
"""

import base64
import json
from datetime import datetime
from uuid import UUID

# ordem -> (critério principal, desempate); depois sempre atividade recente e id.
# Os nomes de coluna vêm só desta tabela, nunca do usuário. None = só atividade recente.
ORDENS = {
    "compatibilidade": ("score_mutuo", "similaridade"),
    "afinidade": ("similaridade", "score_mutuo"),
    "recentes": (None, None),
}
KM_POR_GRAU_LAT = 111.0


class CursorInvalido(ValueError):
    pass


def codificar_cursor(linha, ordem: str) -> str:
    k1, k2 = ORDENS[ordem]
    bruto = [linha[k1] if k1 else 0, linha[k2] if k2 else 0, linha["ativo_em"].isoformat(), str(linha["conta_id"])]
    return base64.urlsafe_b64encode(json.dumps(bruto).encode()).decode().rstrip("=")


def decodificar_cursor(cursor: str) -> tuple[int, int, datetime, UUID]:
    try:
        k1, k2, ativo_em, conta_id = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if not (isinstance(k1, int) and isinstance(k2, int)):
            raise TypeError
        return k1, k2, datetime.fromisoformat(ativo_em), UUID(conta_id)
    except (ValueError, TypeError) as e:
        raise CursorInvalido("Cursor inválido") from e


class _Params:
    """Acumula parâmetros e devolve o placeholder ($n) correspondente."""

    def __init__(self):
        self.valores = []

    def __call__(self, valor, tipo: str) -> str:
        self.valores.append(valor)
        return f"${len(self.valores)}::{tipo}"


def _consulta(
    eu,
    *,
    alvo: UUID | None = None,
    ordem: str = "compatibilidade",
    limite: int = 20,
    cursor: tuple | None = None,
    inatividade_dias: int | None = None,
    excluir_curtidos: bool = True,
) -> tuple[str, list]:
    p = _Params()
    eu_id = p(eu["conta_id"], "uuid")
    quero, curioso = p(eu["tags_quero"], "int[]"), p(eu["tags_curioso"], "int[]")
    limites = p(eu["tags_limite"], "int[]")
    lat, lon = p(eu["lat_aprox"], "float8"), p(eu["lon_aprox"], "float8")
    dist_max = p(eu["distancia_max_km"], "int")

    filtros = [
        "p.visivel",
        f"p.conta_id <> {eu_id}",
        "ct.situacao = 'ativa'",
        # Camada 1: eu busco o gênero da pessoa e ela busca o meu.
        f"p.genero_id = ANY({p(eu['busca_por'], 'smallint[]')})",
        # OPERATOR(pg_catalog.@>): com a extensão intarray instalada, `@>` puro fica ambíguo
        # para smallint[]; o operador nativo é o que usa o índice GIN de busca_por.
        f"p.busca_por OPERATOR(pg_catalog.@>) ARRAY[{p(eu['genero_id'], 'smallint')}]",
        # Camada 2: ela não quer nada que é limite meu, e não tem limite em nada que eu quero.
        f"NOT (p.tags_quero && {limites})",
        f"NOT (p.tags_limite && {quero})",
        f"""NOT EXISTS (
            SELECT 1 FROM bloqueios b
            WHERE (b.bloqueador_id = {eu_id} AND b.bloqueado_id = p.conta_id)
               OR (b.bloqueador_id = p.conta_id AND b.bloqueado_id = {eu_id}))""",
        # Pré-filtro barato por faixa de latitude quando EU tenho distância máxima.
        f"({dist_max} IS NULL OR p.lat_aprox BETWEEN {lat} - {dist_max} / {KM_POR_GRAU_LAT}"
        f" AND {lat} + {dist_max} / {KM_POR_GRAU_LAT})",
    ]
    if alvo is not None:
        filtros.append(f"p.conta_id = {p(alvo, 'uuid')}")
    if excluir_curtidos:
        filtros.append(f"NOT EXISTS (SELECT 1 FROM curtidas c WHERE c.de_id = {eu_id} AND c.para_id = p.conta_id)")
    if inatividade_dias is not None:
        filtros.append(f"p.ativo_em > now() - make_interval(days => {p(inatividade_dias, 'int')})")

    k1, k2 = (f"n.{k}" if k else "0" for k in ORDENS[ordem])
    filtro_cursor = "true"
    if cursor is not None:
        c1, c2, c_ativo, c_id = cursor
        filtro_cursor = (
            f"({k1}, {k2}, n.ativo_em, n.conta_id) < "
            f"({p(c1, 'int')}, {p(c2, 'int')}, {p(c_ativo, 'timestamptz')}, {p(c_id, 'uuid')})"
        )

    sql = f"""
    WITH base AS (
        SELECT p.*,
               -- Camada 3: pesos 3 / 2 / 2 / 1 (a soma é a mesma dos dois pontos de vista)
               3 * icount(p.tags_quero & {quero}) + 2 * icount(p.tags_curioso & {quero})
                 + 2 * icount(p.tags_quero & {curioso}) + icount(p.tags_curioso & {curioso}) AS pontos,
               3 * cardinality({quero}) + cardinality({curioso})             AS max_eu,
               3 * cardinality(p.tags_quero) + cardinality(p.tags_curioso)   AS max_outro,
               -- Similaridade (cosseno; quero = 2, curioso = 1)
               4 * icount(p.tags_quero & {quero}) + icount(p.tags_curioso & {curioso})
                 + 2 * (icount(p.tags_curioso & {quero}) + icount(p.tags_quero & {curioso})) AS produto,
               4 * cardinality({quero}) + cardinality({curioso})             AS norma_eu,
               4 * cardinality(p.tags_quero) + cardinality(p.tags_curioso)   AS norma_outro,
               CASE WHEN {lat} IS NOT NULL AND p.lat_aprox IS NOT NULL
                    THEN distancia_km({lat}, {lon}, p.lat_aprox, p.lon_aprox) END AS distancia
        FROM perfis p
        JOIN contas ct ON ct.id = p.conta_id
        WHERE {" AND ".join(filtros)}
    ), notas AS (
        SELECT base.*,
               -- porcentagem com arredondamento "meio para cima" em inteiros (= matcher._porcentagem)
               CASE WHEN max_eu = 0 THEN 0
                    ELSE LEAST(100, (pontos * 200 + max_eu) / (2 * max_eu)) END AS score_eu,
               CASE WHEN max_outro = 0 THEN 0
                    ELSE LEAST(100, (pontos * 200 + max_outro) / (2 * max_outro)) END AS score_outro,
               CASE WHEN produto = 0 THEN 0
                    ELSE floor(100 * produto / sqrt(norma_eu::float8 * norma_outro) + 0.5)::int END AS similaridade
        FROM base
        WHERE ({dist_max} IS NULL OR distancia <= {dist_max})
          AND (base.distancia_max_km IS NULL OR distancia <= base.distancia_max_km)
    ), final AS (
        SELECT notas.*, (score_eu + score_outro + 1) / 2 AS score_mutuo FROM notas
    )
    SELECT * FROM final n
    WHERE {filtro_cursor}
    ORDER BY {k1} DESC, {k2} DESC, n.ativo_em DESC, n.conta_id DESC
    LIMIT {p(limite, "int")}
    """
    return sql, p.valores


async def buscar_candidatos(con, eu, *, ordem: str, limite: int, cursor: tuple | None, inatividade_dias: int):
    sql, params = _consulta(eu, ordem=ordem, limite=limite, cursor=cursor, inatividade_dias=inatividade_dias)
    return await con.fetch(sql, *params)


async def buscar_elegivel(con, eu, alvo: UUID):
    """O perfil `alvo`, se ele passa por todos os filtros para `eu` (usado antes de curtir)."""
    sql, params = _consulta(eu, alvo=alvo, limite=1, excluir_curtidos=False)
    return await con.fetchrow(sql, *params)
