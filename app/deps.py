"""Dependências compartilhadas pelas rotas (injetadas com Depends)."""
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from . import repository as repo
from .cripto import Cifrador
from .db import conexao


def cifrador(request: Request) -> Cifrador:
    return request.app.state.cifrador


async def exigir_perfil(con, conta_id: UUID):
    perfil = await repo.buscar_perfil(con, conta_id)
    if perfil is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Crie seu perfil em PUT /api/perfil primeiro")
    return perfil


async def exigir_perfil_visivel(con, eu: UUID, alvo: UUID):
    """Perfil de outra pessoa que eu posso ver. 404 também para bloqueios e contas em revisão,
    para não revelar nada sobre o motivo."""
    if alvo == eu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Operação inválida sobre o próprio perfil")
    perfil = await repo.buscar_perfil_visivel(con, eu, alvo)
    if perfil is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil não encontrado")
    return perfil


__all__ = ["Depends", "conexao", "cifrador", "exigir_perfil", "exigir_perfil_visivel"]
