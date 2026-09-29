"""Termos de uso e política de privacidade versionados (Parte 10 do plano; LGPD).

A versão é a data da última mudança relevante. Quando ela muda, todo mundo precisa aceitar de
novo antes de ver perfis, curtir ou conversar (o próprio perfil e a conta continuam acessíveis,
inclusive para excluir tudo). Guardamos só QUAL versão foi aceita e QUANDO.
"""

from uuid import UUID

# Ao mudar os textos em static/termos.html ou static/privacidade.html de forma relevante,
# atualize esta data (e a data dentro das páginas). Um teste confere que as três batem.
VERSAO_ATUAL = "2026-09-29"
DETALHE_PENDENTE = "Aceite dos termos pendente"


class VersaoDesatualizada(Exception):
    pass


async def aceitar(con, conta: UUID, versao: str) -> None:
    if versao != VERSAO_ATUAL:
        raise VersaoDesatualizada("Esta não é a versão atual dos termos. Recarregue a página.")
    await con.execute(
        "UPDATE contas SET termos_versao = $2, termos_aceitos_em = now() WHERE id = $1", conta, VERSAO_ATUAL
    )


async def situacao(con, conta: UUID) -> dict:
    linha = await con.fetchrow("SELECT termos_versao, termos_aceitos_em FROM contas WHERE id = $1", conta)
    return {
        "versao_atual": VERSAO_ATUAL,
        "aceita": linha["termos_versao"] == VERSAO_ATUAL,
        "versao_aceita": linha["termos_versao"],
        "aceitos_em": linha["termos_aceitos_em"],
    }
