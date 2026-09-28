"""Denúncias, revisão automática e decisões de moderação."""

import json
from uuid import UUID

from . import mensagens
from . import repository as repo
from .cripto import Cifrador

# Uma única denúncia por estes motivos já oculta o perfil até a revisão humana.
MOTIVOS_GRAVES = {"menor_de_idade", "conteudo_ilegal"}
# Contas mais novas que isso não contam para a revisão automática por volume,
# para dificultar que alguém crie contas só para derrubar outra pessoa.
IDADE_MIN_DENUNCIANTE = "24 hours"


def _contexto_evidencia(denunciado: UUID) -> bytes:
    return b"evidencia|" + denunciado.bytes


async def denunciar(
    con,
    cifrador: Cifrador,
    *,
    denunciante: UUID,
    denunciado: UUID,
    motivo: str,
    detalhes: str | None,
    incluir_mensagens: bool,
    limiar: int,
) -> None:
    """Registra a denúncia, bloqueia automaticamente e avalia a revisão automática.

    As evidências são copiadas ANTES do bloqueio, porque bloquear apaga a conversa.
    """
    async with con.transaction():
        evidencias = None
        if incluir_mensagens:
            ultimas = await mensagens.ultimas_da_conversa(con, cifrador, denunciante, denunciado)
            if ultimas:
                evidencias = cifrador.cifrar(json.dumps(ultimas), _contexto_evidencia(denunciado))
        await con.execute(
            """INSERT INTO denuncias (denunciante_id, denunciado_id, motivo, detalhes, evidencias)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (denunciante_id, denunciado_id) WHERE status = 'aberta' DO NOTHING""",
            denunciante,
            denunciado,
            motivo,
            detalhes,
            evidencias,
        )
        await repo.bloquear(con, denunciante, denunciado)
        await _avaliar_revisao(con, denunciado, motivo, limiar)


async def _avaliar_revisao(con, conta: UUID, motivo: str, limiar: int) -> None:
    if motivo not in MOTIVOS_GRAVES:
        denunciantes = await con.fetchval(
            f"""SELECT count(DISTINCT d.denunciante_id) FROM denuncias d
                JOIN contas c ON c.id = d.denunciante_id
                WHERE d.denunciado_id = $1 AND d.status = 'aberta'
                  AND c.criado_em <= now() - interval '{IDADE_MIN_DENUNCIANTE}'""",
            conta,
        )
        if denunciantes < limiar:
            return
    movida = await con.fetchval(
        "UPDATE contas SET situacao = 'em_revisao' WHERE id = $1 AND situacao = 'ativa' RETURNING true", conta
    )
    if movida:
        await con.execute(
            "INSERT INTO moderacao_log (conta_id, acao, observacao) VALUES ($1, 'revisao_automatica', $2)",
            conta,
            f"motivo: {motivo}",
        )


async def fila(con, cifrador: Cifrador) -> list[dict]:
    """Contas com denúncias abertas ou em revisão. Casos graves primeiro, depois volume."""
    contas = await con.fetch(
        """SELECT c.id, c.handle, c.situacao,
                  bool_or(d.motivo = ANY($1::text[])) AS grave,
                  count(d.id) AS total, min(d.criado_em) AS primeira
           FROM contas c
           LEFT JOIN denuncias d ON d.denunciado_id = c.id AND d.status = 'aberta'
           WHERE c.situacao = 'em_revisao' OR d.id IS NOT NULL
           GROUP BY c.id
           ORDER BY grave DESC NULLS LAST, total DESC, primeira""",
        list(MOTIVOS_GRAVES),
    )
    resultado = []
    for c in contas:
        denuncias = await con.fetch(
            """SELECT id, motivo, detalhes, criado_em, evidencias FROM denuncias
               WHERE denunciado_id = $1 AND status = 'aberta' ORDER BY criado_em""",
            c["id"],
        )
        resultado.append(
            {
                "conta_id": c["id"],
                "handle": c["handle"],
                "situacao": c["situacao"],
                "perfil": await repo.buscar_perfil(con, c["id"]),
                "denuncias": [
                    {
                        **{k: d[k] for k in ("id", "motivo", "detalhes", "criado_em")},
                        "evidencias": json.loads(cifrador.decifrar(d["evidencias"], _contexto_evidencia(c["id"])))
                        if d["evidencias"]
                        else None,
                    }
                    for d in denuncias
                ],
            }
        )
    return resultado


async def decidir(con, *, moderador: UUID, conta: UUID, acao: str, observacao: str | None) -> bool:
    """`banir`: a conta não entra mais e todas as sessões caem. `restaurar`: volta a ativa.
    Resolve todas as denúncias abertas contra a conta e registra no log."""
    async with con.transaction():
        if acao == "banir":
            ok = await con.fetchval(
                "UPDATE contas SET situacao = 'banida', token_versao = token_versao + 1 WHERE id = $1 RETURNING true",
                conta,
            )
            status = "procedente"
        else:
            ok = await con.fetchval("UPDATE contas SET situacao = 'ativa' WHERE id = $1 RETURNING true", conta)
            status = "improcedente"
        if not ok:
            return False
        await con.execute(
            """UPDATE denuncias SET status = $2, resolvido_em = now()
               WHERE denunciado_id = $1 AND status = 'aberta'""",
            conta,
            status,
        )
        await con.execute(
            "INSERT INTO moderacao_log (moderador_id, conta_id, acao, observacao) VALUES ($1, $2, $3, $4)",
            moderador,
            conta,
            acao,
            observacao,
        )
        return True
