import os

from fastapi import APIRouter, Depends

from ..db import conexao

router = APIRouter(tags=["operação"])


@router.get("/saude")
async def saude(con=Depends(conexao)):
    """Usado pelo healthcheck do Render e pela pipeline de deploy.

    `versao` é o commit em produção (o Render define RENDER_GIT_COMMIT sozinho), para a
    pipeline confirmar que a versão nova realmente entrou no ar.
    """
    await con.fetchval("SELECT 1")
    return {"status": "ok", "versao": os.environ.get("RENDER_GIT_COMMIT", "dev")}
