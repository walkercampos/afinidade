from . import repository as repo
from .schemas import PerfilPublico


class Catalogo:
    """Resolve IDs -> slugs de gêneros e tags para um lote de perfis com duas consultas."""

    def __init__(self, generos: dict[int, str], tags: dict[int, str]):
        self.generos, self.tags = generos, tags

    @classmethod
    async def para(cls, con, linhas):
        ids_genero = {g for linha in linhas for g in [linha["genero_id"], *linha["busca_por"]]}
        ids_tag = {t for linha in linhas for t in [*linha["tags_quero"], *linha["tags_curioso"], *linha["tags_limite"]]}
        return cls(await repo.slugs_por_id(con, "generos", ids_genero), await repo.slugs_por_id(con, "tags", ids_tag))

    def tags_de(self, ids) -> list[str]:
        return sorted(self.tags[i] for i in ids)

    def publico(self, linha) -> PerfilPublico:
        return PerfilPublico(
            id=linha["conta_id"],
            nome_exibicao=linha["nome_exibicao"],
            bio=linha["bio"],
            genero=self.generos[linha["genero_id"]],
            quero=self.tags_de(linha["tags_quero"]),
            curioso=self.tags_de(linha["tags_curioso"]),
        )
