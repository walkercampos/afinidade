"""Chat entre conexões: mensagens cifradas em repouso, com prazo de vida acordado por conversa.

Regras (Parte 6 do plano):
- Cada conversa tem um prazo: quanto tempo a mensagem dura DEPOIS DE LIDA. Padrão: 24 h.
- O prazo é gravado em cada mensagem no envio. Mudar o prazo da conversa vale só para as
  mensagens enviadas depois; as anteriores seguem com o prazo com que foram enviadas.
- `expira_em = lida_em + prazo`. Mensagem não lida não expira. Prazo `None` = nunca expira.
- Mudar o prazo exige as duas pessoas: uma propõe, a outra confirma (ver `propor`/`confirmar`).
"""

from uuid import UUID

from .cripto import Cifrador

# Prazos permitidos, em minutos (None = nunca). A MESMA lista está na função SQL
# ttl_mensagem_valido (migração 0010); um teste garante que as duas concordam.
PRAZOS_PERMITIDOS: tuple[int | None, ...] = (
    5, 15, 30, 60,  # minutos
    360, 720, 1440,  # 6, 12 e 24 horas
    4320, 10080, 20160,  # 3, 7 e 14 dias
    40320,  # 4 semanas
    43200, 129600, 259200,  # 1, 3 e 6 meses
    None,  # nunca
)  # fmt: skip
PRAZO_PADRAO = 1440  # 24 h depois de lida
PROPOSTA_VALE_DIAS = 7

_EXPIRA_EM = "m.lida_em + make_interval(mins => m.ttl_minutos)"
_VISIVEL = f"(m.lida_em IS NULL OR m.ttl_minutos IS NULL OR {_EXPIRA_EM} > now())"
# O par sem ordem, escrito do jeito que o índice mensagens_conversa_idx (LEAST, GREATEST, id) entende.
# Com "(de = $1 AND para = $2) OR (de = $2 AND para = $1)" o banco lia a tabela inteira a cada
# conversa aberta (teste de carga, docs/carga/): o custo crescia com o total de mensagens do app.
_DA_CONVERSA = (
    "(LEAST(m.de_id, m.para_id) = LEAST($1::uuid, $2::uuid)"
    " AND GREATEST(m.de_id, m.para_id) = GREATEST($1::uuid, $2::uuid))"
)


class PropostaInvalida(Exception):
    """Pedido de mudança de prazo que não pode ser atendido (mensagem pronta para a pessoa)."""


def _par(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if a < b else (b, a)


def _contexto(a: UUID, b: UUID) -> bytes:
    menor, maior = _par(a, b)
    return b"mensagem|" + menor.bytes + maior.bytes


def _para_dict(linha, eu: UUID, cifrador: Cifrador) -> dict:
    lida_em, prazo = linha["lida_em"], linha["ttl_minutos"]
    return {
        "id": linha["id"],
        "minha": linha["de_id"] == eu,
        "texto": cifrador.decifrar(linha["conteudo"], _contexto(linha["de_id"], linha["para_id"])),
        "criado_em": linha["criado_em"],
        "lida_em": lida_em,
        "ttl_minutos": prazo,
        "expira_em": linha["expira_em"] if lida_em and prazo is not None else None,
    }


async def prazo_da_conversa(con, a: UUID, b: UUID) -> int | None:
    linha = await con.fetchrow(
        "SELECT ttl_minutos FROM conversas_config WHERE conta_a = $1 AND conta_b = $2", *_par(a, b)
    )
    return PRAZO_PADRAO if linha is None else linha["ttl_minutos"]


async def enviar(con, cifrador: Cifrador, de: UUID, para: UUID, texto: str) -> dict:
    prazo = await prazo_da_conversa(con, de, para)
    linha = await con.fetchrow(
        f"""INSERT INTO mensagens AS m (de_id, para_id, conteudo, ttl_minutos) VALUES ($1, $2, $3, $4)
            RETURNING m.*, {_EXPIRA_EM} AS expira_em""",
        de,
        para,
        cifrador.cifrar(texto, _contexto(de, para)),
        prazo,
    )
    return _para_dict(linha, de, cifrador)


async def listar(
    con, cifrador: Cifrador, eu: UUID, outro: UUID, *, apos: int = 0, limite: int = 50
) -> tuple[list[dict], bool]:
    """Mensagens ainda não expiradas, em ordem. As recebidas e não lidas passam a lidas
    agora, e o prazo de cada uma começa a contar. Devolve também se alguma foi lida agora
    (para avisar quem enviou que a contagem começou)."""
    async with con.transaction():
        linhas = await con.fetch(
            f"""SELECT m.id, m.para_id, m.lida_em FROM mensagens m
                WHERE {_DA_CONVERSA} AND {_VISIVEL} AND m.id > $3
                ORDER BY m.id LIMIT $4""",
            eu,
            outro,
            apos,
            limite,
        )
        recebidas = [linha["id"] for linha in linhas if linha["para_id"] == eu and linha["lida_em"] is None]
        if recebidas:
            await con.execute("UPDATE mensagens SET lida_em = now() WHERE id = ANY($1::bigint[])", recebidas)
        linhas = await con.fetch(
            f"SELECT m.*, {_EXPIRA_EM} AS expira_em FROM mensagens m WHERE m.id = ANY($1::bigint[]) ORDER BY m.id",
            [linha["id"] for linha in linhas],
        )
    return [_para_dict(linha, eu, cifrador) for linha in linhas], bool(recebidas)


async def ultimas_da_conversa(con, cifrador: Cifrador, eu: UUID, outro: UUID, n: int = 20) -> list[dict]:
    """Para anexar como evidência numa denúncia (sem marcar nada como lido)."""
    linhas = await con.fetch(
        f"""SELECT m.* FROM mensagens m WHERE {_DA_CONVERSA} AND {_VISIVEL}
            ORDER BY m.id DESC LIMIT $3""",
        eu,
        outro,
        n,
    )
    return [
        {
            "de": "denunciante" if linha["de_id"] == eu else "denunciado",
            "texto": cifrador.decifrar(linha["conteudo"], _contexto(linha["de_id"], linha["para_id"])),
            "criado_em": linha["criado_em"].isoformat(),
        }
        for linha in reversed(linhas)
    ]


async def resumo_conversas(con, eu: UUID) -> dict[UUID, tuple[int, object]]:
    """{outra_pessoa: (não lidas, horário da última mensagem visível)}"""
    linhas = await con.fetch(
        f"""SELECT CASE WHEN m.de_id = $1 THEN m.para_id ELSE m.de_id END AS outro,
                   count(*) FILTER (WHERE m.para_id = $1 AND m.lida_em IS NULL) AS nao_lidas,
                   max(m.criado_em) AS ultima_em
            FROM mensagens m
            WHERE (m.de_id = $1 OR m.para_id = $1) AND {_VISIVEL}
            GROUP BY 1""",
        eu,
    )
    return {linha["outro"]: (linha["nao_lidas"], linha["ultima_em"]) for linha in linhas}


async def apagar_minhas(con, eu: UUID, outro: UUID) -> None:
    await con.execute("DELETE FROM mensagens WHERE de_id = $1 AND para_id = $2", eu, outro)


async def apagar_expiradas(con) -> int:
    """Remove fisicamente as mensagens já expiradas e as propostas de prazo vencidas.
    Chamada periodicamente pela aplicação (ver main.py). Não lidas nunca são apagadas aqui."""
    status = await con.execute(
        f"DELETE FROM mensagens m WHERE m.lida_em IS NOT NULL AND m.ttl_minutos IS NOT NULL AND {_EXPIRA_EM} <= now()"
    )
    await con.execute("DELETE FROM propostas_ttl WHERE expira_em <= now()")
    return int(status.split()[-1])


# ---------- prazo da conversa: propor e confirmar ----------


async def situacao_do_prazo(con, eu: UUID, outro: UUID) -> dict:
    """Prazo atual da conversa e a proposta pendente (se houver e não tiver vencido)."""
    a, b = _par(eu, outro)
    proposta = await con.fetchrow(
        """SELECT proposto_por, ttl_minutos, expira_em FROM propostas_ttl
           WHERE conta_a = $1 AND conta_b = $2 AND expira_em > now()""",
        a,
        b,
    )
    return {
        "ttl_minutos": await prazo_da_conversa(con, eu, outro),
        "padrao": PRAZO_PADRAO,
        "opcoes": list(PRAZOS_PERMITIDOS),
        "proposta": None
        if proposta is None
        else {
            "ttl_minutos": proposta["ttl_minutos"],
            "minha": proposta["proposto_por"] == eu,
            "expira_em": proposta["expira_em"],
        },
    }


async def propor(con, eu: UUID, outro: UUID, prazo: int | None) -> dict:
    """Propõe um prazo novo. Substitui uma proposta anterior (de qualquer das duas pessoas)."""
    if prazo not in PRAZOS_PERMITIDOS:
        raise PropostaInvalida("Prazo não permitido.")
    if prazo == await prazo_da_conversa(con, eu, outro):
        raise PropostaInvalida("Esse já é o prazo desta conversa.")
    a, b = _par(eu, outro)
    await con.execute(
        """INSERT INTO propostas_ttl (conta_a, conta_b, proposto_por, ttl_minutos, expira_em)
           VALUES ($1, $2, $3, $4, now() + make_interval(days => $5))
           ON CONFLICT (conta_a, conta_b) DO UPDATE
           SET proposto_por = EXCLUDED.proposto_por, ttl_minutos = EXCLUDED.ttl_minutos,
               criado_em = now(), expira_em = EXCLUDED.expira_em""",
        a,
        b,
        eu,
        prazo,
        PROPOSTA_VALE_DIAS,
    )
    return await situacao_do_prazo(con, eu, outro)


async def confirmar(con, eu: UUID, outro: UUID) -> dict:
    """A outra pessoa aceita a proposta: o prazo novo vale para as próximas mensagens."""
    a, b = _par(eu, outro)
    async with con.transaction():
        proposta = await con.fetchrow(
            """DELETE FROM propostas_ttl
               WHERE conta_a = $1 AND conta_b = $2 AND expira_em > now() AND proposto_por <> $3
               RETURNING ttl_minutos""",
            a,
            b,
            eu,
        )
        if proposta is None:
            raise PropostaInvalida("Não há proposta da outra pessoa para confirmar.")
        await con.execute(
            """INSERT INTO conversas_config (conta_a, conta_b, ttl_minutos) VALUES ($1, $2, $3)
               ON CONFLICT (conta_a, conta_b) DO UPDATE
               SET ttl_minutos = EXCLUDED.ttl_minutos, atualizado_em = now()""",
            a,
            b,
            proposta["ttl_minutos"],
        )
    return await situacao_do_prazo(con, eu, outro)


async def descartar_proposta(con, eu: UUID, outro: UUID) -> None:
    """Quem propôs desiste, ou a outra pessoa recusa: nos dois casos a proposta some."""
    await con.execute("DELETE FROM propostas_ttl WHERE conta_a = $1 AND conta_b = $2", *_par(eu, outro))
