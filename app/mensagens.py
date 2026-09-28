"""Chat entre conexões com mensagens efêmeras e cifradas em repouso."""
from datetime import timedelta
from uuid import UUID

from .cripto import Cifrador

# Tempo de vida depois da leitura. Constante (e não configuração) porque é uma promessa
# de produto: "a mensagem some 5 minutos depois de lida".
EXPIRA_APOS_LEITURA = timedelta(minutes=5)

_VISIVEL = "(m.lida_em IS NULL OR m.lida_em > now() - $3::interval)"
_DA_CONVERSA = "((m.de_id = $1 AND m.para_id = $2) OR (m.de_id = $2 AND m.para_id = $1))"


def _contexto(a: UUID, b: UUID) -> bytes:
    menor, maior = sorted((a, b))
    return b"mensagem|" + menor.bytes + maior.bytes


def _para_dict(linha, eu: UUID, cifrador: Cifrador) -> dict:
    lida_em = linha["lida_em"]
    return {
        "id": linha["id"],
        "minha": linha["de_id"] == eu,
        "texto": cifrador.decifrar(linha["conteudo"], _contexto(linha["de_id"], linha["para_id"])),
        "criado_em": linha["criado_em"],
        "lida_em": lida_em,
        "expira_em": lida_em + EXPIRA_APOS_LEITURA if lida_em else None,
    }


async def enviar(con, cifrador: Cifrador, de: UUID, para: UUID, texto: str) -> dict:
    linha = await con.fetchrow(
        "INSERT INTO mensagens (de_id, para_id, conteudo) VALUES ($1, $2, $3) RETURNING *",
        de, para, cifrador.cifrar(texto, _contexto(de, para)),
    )
    return _para_dict(linha, de, cifrador)


async def listar(con, cifrador: Cifrador, eu: UUID, outro: UUID, *, apos: int = 0, limite: int = 50) -> list[dict]:
    """Mensagens ainda não expiradas, em ordem. As recebidas e não lidas passam a lidas
    agora — e começam a contar os 5 minutos."""
    async with con.transaction():
        linhas = await con.fetch(
            f"""SELECT m.* FROM mensagens m
                WHERE {_DA_CONVERSA} AND {_VISIVEL} AND m.id > $4
                ORDER BY m.id LIMIT $5""",
            eu, outro, EXPIRA_APOS_LEITURA, apos, limite,
        )
        recebidas = [l["id"] for l in linhas if l["para_id"] == eu and l["lida_em"] is None]
        lidas_agora = {}
        if recebidas:
            lidas_agora = dict(await con.fetch(
                "UPDATE mensagens SET lida_em = now() WHERE id = ANY($1::bigint[]) RETURNING id, lida_em", recebidas
            ))
    resultado = []
    for l in linhas:
        d = _para_dict(l, eu, cifrador)
        if l["id"] in lidas_agora:
            d["lida_em"] = lidas_agora[l["id"]]
            d["expira_em"] = d["lida_em"] + EXPIRA_APOS_LEITURA
        resultado.append(d)
    return resultado


async def ultimas_da_conversa(con, cifrador: Cifrador, eu: UUID, outro: UUID, n: int = 20) -> list[dict]:
    """Para anexar como evidência numa denúncia (sem marcar nada como lido)."""
    linhas = await con.fetch(
        f"""SELECT m.* FROM mensagens m WHERE {_DA_CONVERSA} AND {_VISIVEL}
            ORDER BY m.id DESC LIMIT $4""",
        eu, outro, EXPIRA_APOS_LEITURA, n,
    )
    return [
        {"de": "denunciante" if l["de_id"] == eu else "denunciado",
         "texto": cifrador.decifrar(l["conteudo"], _contexto(l["de_id"], l["para_id"])),
         "criado_em": l["criado_em"].isoformat()}
        for l in reversed(linhas)
    ]


async def resumo_conversas(con, eu: UUID) -> dict[UUID, tuple[int, object]]:
    """{outra_pessoa: (não lidas, horário da última mensagem visível)}"""
    linhas = await con.fetch(
        """SELECT CASE WHEN m.de_id = $1 THEN m.para_id ELSE m.de_id END AS outro,
                  count(*) FILTER (WHERE m.para_id = $1 AND m.lida_em IS NULL) AS nao_lidas,
                  max(m.criado_em) AS ultima_em
           FROM mensagens m
           WHERE (m.de_id = $1 OR m.para_id = $1) AND (m.lida_em IS NULL OR m.lida_em > now() - $2::interval)
           GROUP BY 1""",
        eu, EXPIRA_APOS_LEITURA,
    )
    return {l["outro"]: (l["nao_lidas"], l["ultima_em"]) for l in linhas}


async def apagar_minhas(con, eu: UUID, outro: UUID) -> None:
    await con.execute("DELETE FROM mensagens WHERE de_id = $1 AND para_id = $2", eu, outro)


async def apagar_expiradas(con, retencao_dias: int) -> int:
    """Chamada periodicamente pela aplicação (ver main.py)."""
    status = await con.execute(
        """DELETE FROM mensagens
           WHERE lida_em <= now() - $1::interval
              OR (lida_em IS NULL AND criado_em <= now() - make_interval(days => $2))""",
        EXPIRA_APOS_LEITURA, retencao_dias,
    )
    return int(status.split()[-1])
