"""Verificação de idade (Parte 3 do plano; ECA Digital, Lei 15.211/2025).

Quem verifica é um provedor externo (selfie + prova de vida, e CPF se o provedor exigir). Este
módulo guarda SÓ o resultado: "verificada em tal data, por tal provedor". Nenhuma imagem,
documento, CPF ou data de nascimento passa por aqui ou é gravado.

Fluxo:
1. `iniciar`: cria uma tentativa e devolve a URL do provedor para onde a pessoa vai.
2. A pessoa faz a verificação no provedor.
3. O provedor avisa o resultado (webhook assinado) e `concluir` grava aprovada/recusada.

Provedores:
- "simulado": só fora de produção. A "página do provedor" é uma tela do próprio app com os
  botões Aprovar/Recusar; serve para desenvolver e testar o fluxo inteiro sem contrato.
- Provedores reais (Unico, FlagCheck, Didit...) exigem contrato e chave de API. Cada um entra
  como uma classe com `iniciar` (cria a sessão na API dele) e uma rota de retorno que confere a
  assinatura do webhook antes de chamar `concluir`. Veja docs/plano/parte-03-verificacao-de-idade.md.
"""

import hashlib
import hmac
import secrets
from typing import Protocol
from uuid import UUID

from .config import config

# Uma tentativa vale por 1 hora; depois disso o retorno do provedor é ignorado.
VALIDADE_TENTATIVA_MIN = 60
# Tentativas concluídas ficam guardadas por este tempo (auditoria) e depois são apagadas.
GUARDAR_TENTATIVAS_DIAS = 30
DETALHE_PENDENTE = "Verificação de idade pendente"


class Provedor(Protocol):
    nome: str

    async def iniciar(self, sessao: str) -> str:
        """Cria a sessão no provedor e devolve a URL para onde a pessoa deve ir."""


class ProvedorSimulado:
    """Provedor de mentira, para desenvolvimento e testes. Nunca é aceito em produção."""

    nome = "simulado"

    async def iniciar(self, sessao: str) -> str:
        return f"/#/idade-simulada/{sessao}"


PROVEDORES: dict[str, type] = {"simulado": ProvedorSimulado}


def obrigatoria() -> bool:
    """Se a verificação é exigida para descobrir, curtir e conversar."""
    return config().idade_obrigatoria


def criar_provedor() -> Provedor | None:
    nome = config().idade_provedor
    return PROVEDORES[nome]() if nome in PROVEDORES else None


def validar_configuracao(producao: bool, obrigatoria: bool, provedor: str) -> None:
    """Chamada na inicialização: o app nunca sobe fingindo que verifica idade."""
    if provedor not in (*PROVEDORES, "desativado"):
        raise RuntimeError(f"IDADE_PROVEDOR desconhecido: {provedor!r}.")
    if producao and provedor == "simulado":
        raise RuntimeError("IDADE_PROVEDOR=simulado não é permitido em produção.")
    if producao and obrigatoria and provedor == "desativado":
        raise RuntimeError(
            "A verificação de idade é obrigatória em produção (IDADE_OBRIGATORIA), mas nenhum provedor "
            "real está configurado (IDADE_PROVEDOR). Contrate e configure um provedor, ou defina "
            "IDADE_OBRIGATORIA=false conscientemente (o app NÃO pode abrir ao público assim). "
            "Veja docs/plano/parte-03-verificacao-de-idade.md."
        )


def _hash_sessao(sessao: str) -> bytes:
    # Chave derivada do JWT_SECRET: só o servidor consegue ligar um id de sessão a uma tentativa.
    chave = hmac.new(config().jwt_secret.encode(), b"afinidade/idade/sessao/v1", hashlib.sha256).digest()
    return hmac.new(chave, sessao.encode(), hashlib.sha256).digest()


async def situacao(con, conta: UUID) -> dict:
    linha = await con.fetchrow(
        """SELECT c.idade_verificada_em,
                  EXISTS (SELECT 1 FROM verificacoes_idade v
                          WHERE v.conta_id = c.id AND v.situacao = 'pendente'
                            AND v.criado_em > now() - make_interval(mins => $2)) AS pendente
           FROM contas c WHERE c.id = $1""",
        conta,
        VALIDADE_TENTATIVA_MIN,
    )
    return {
        "obrigatoria": obrigatoria(),
        "verificada": linha["idade_verificada_em"] is not None,
        "verificada_em": linha["idade_verificada_em"],
        "pendente": linha["pendente"],
        "disponivel": criar_provedor() is not None,
    }


async def iniciar(con, provedor: Provedor, conta: UUID) -> str:
    """Nova tentativa (as pendentes anteriores expiram) e a URL do provedor."""
    sessao = secrets.token_urlsafe(24)
    async with con.transaction():
        await con.execute(
            """UPDATE verificacoes_idade SET situacao = 'expirada', concluido_em = now()
               WHERE conta_id = $1 AND situacao = 'pendente'""",
            conta,
        )
        await con.execute(
            "INSERT INTO verificacoes_idade (conta_id, provedor, sessao_hash) VALUES ($1, $2, $3)",
            conta,
            provedor.nome,
            _hash_sessao(sessao),
        )
    return await provedor.iniciar(sessao)


async def concluir(con, sessao: str, aprovada: bool, *, conta: UUID | None = None) -> bool:
    """Grava o resultado de uma tentativa pendente e ainda válida. `conta`, quando informada,
    precisa ser a dona da tentativa (usado pelo provedor simulado). Devolve se encontrou."""
    async with con.transaction():
        linha = await con.fetchrow(
            """UPDATE verificacoes_idade SET situacao = $2, concluido_em = now()
               WHERE sessao_hash = $1 AND situacao = 'pendente'
                 AND criado_em > now() - make_interval(mins => $3)
                 AND ($4::uuid IS NULL OR conta_id = $4)
               RETURNING conta_id, provedor""",
            _hash_sessao(sessao),
            "aprovada" if aprovada else "recusada",
            VALIDADE_TENTATIVA_MIN,
            conta,
        )
        if linha is None:
            return False
        if aprovada:
            await con.execute(
                "UPDATE contas SET idade_verificada_em = now(), idade_provedor = $2 WHERE id = $1",
                linha["conta_id"],
                linha["provedor"],
            )
    return True


async def apagar_antigas(con) -> None:
    await con.execute(
        "DELETE FROM verificacoes_idade WHERE criado_em < now() - make_interval(days => $1)", GUARDAR_TENTATIVAS_DIAS
    )
