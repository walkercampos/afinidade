"""Segurança física (Parte 9 do plano): compartilhar um encontro com um contato de confiança.

A pessoa registra onde e quando vai encontrar alguém e o e-mail de alguém de confiança. Até o
horário combinado de check-in, ela confirma que está tudo bem. Se não confirmar, o contato de
confiança recebe um e-mail com os detalhes do encontro.

Privacidade:
- Local, observações e o e-mail do contato (dado de uma terceira pessoa) ficam CIFRADOS
  (AES-256-GCM, chave fora do banco). Em claro, só os horários que a tarefa de fundo precisa.
- O contato recebe um aviso na hora do cadastro (sabe que foi indicado e para quê) e só recebe os
  detalhes se o alerta disparar.
- Registros são apagados 30 dias depois do encontro.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from .cripto import Cifrador
from .email import Mensagem

log = logging.getLogger("matchmaking.encontros")
DOMINIO = b"afinidade/encontros/v1"
GUARDAR_DIAS = 30
MAX_CHECKIN = timedelta(hours=24)
MAX_ANTECEDENCIA = timedelta(days=60)


class EncontroInvalido(Exception):
    """Mensagem pronta para a pessoa."""


def criar_cifrador(segredo: str, anteriores: tuple[str, ...] = ()) -> Cifrador:
    return Cifrador(segredo, dominio=DOMINIO, anteriores=anteriores)


def _contexto(encontro_id: UUID, campo: bytes) -> bytes:
    return b"encontro|" + campo + b"|" + encontro_id.bytes


def validar_horarios(inicio: datetime, checkin: datetime, agora: datetime) -> None:
    if inicio < agora - timedelta(hours=12):
        raise EncontroInvalido("O encontro não pode ter começado há mais de 12 horas.")
    if inicio > agora + MAX_ANTECEDENCIA:
        raise EncontroInvalido("Registre o encontro com até 60 dias de antecedência.")
    if checkin <= inicio:
        raise EncontroInvalido("O horário do check-in precisa ser depois do início do encontro.")
    if checkin > inicio + MAX_CHECKIN:
        raise EncontroInvalido("O check-in precisa ser em até 24 horas depois do início.")
    if checkin <= agora:
        raise EncontroInvalido("O horário do check-in já passou.")


async def criar(
    con,
    cif: Cifrador,
    dono: UUID,
    *,
    com: UUID | None,
    local: str,
    observacoes: str,
    como_te_conhecem: str,
    contato_email: str,
    inicio: datetime,
    checkin: datetime,
) -> UUID:
    encontro_id = uuid.uuid4()
    detalhes = json.dumps(
        {"local": local, "observacoes": observacoes, "como_te_conhecem": como_te_conhecem}, ensure_ascii=False
    )
    await con.execute(
        """INSERT INTO encontros (id, conta_id, com_conta_id, detalhes, contato_confianca, inicio_em, checkin_ate)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        encontro_id,
        dono,
        com,
        cif.cifrar(detalhes, _contexto(encontro_id, b"detalhes")),
        cif.cifrar(contato_email, _contexto(encontro_id, b"contato")),
        inicio,
        checkin,
    )
    return encontro_id


def _abrir(cif: Cifrador, linha) -> dict:
    detalhes = json.loads(cif.decifrar(linha["detalhes"], _contexto(linha["id"], b"detalhes")))
    return {
        **detalhes,
        "id": linha["id"],
        "contato_email": cif.decifrar(linha["contato_confianca"], _contexto(linha["id"], b"contato")),
        "inicio_em": linha["inicio_em"],
        "checkin_ate": linha["checkin_ate"],
        "situacao": linha["situacao"],
        "com_nome": linha["com_nome"],
        "com_handle": linha["com_handle"],
    }


_SELECT = """SELECT e.*, p.nome_exibicao AS com_nome, c.handle AS com_handle
             FROM encontros e
             LEFT JOIN contas c ON c.id = e.com_conta_id
             LEFT JOIN perfis p ON p.conta_id = e.com_conta_id"""


async def listar(con, cif: Cifrador, dono: UUID) -> list[dict]:
    linhas = await con.fetch(f"{_SELECT} WHERE e.conta_id = $1 ORDER BY e.inicio_em DESC LIMIT 50", dono)
    return [_abrir(cif, linha) for linha in linhas]


async def mudar_situacao(con, dono: UUID, encontro_id: UUID, nova: str) -> bool:
    """Check-in ('confirmado_ok') ou cancelamento ('cancelado'), só de encontros agendados."""
    status = await con.execute(
        "UPDATE encontros SET situacao = $3 WHERE id = $1 AND conta_id = $2 AND situacao = 'agendado'",
        encontro_id,
        dono,
        nova,
    )
    return status != "UPDATE 0"


def mensagem_de_indicacao(para: str, como_te_conhecem: str) -> Mensagem:
    quem = como_te_conhecem or "Uma pessoa"
    return Mensagem(
        para=para,
        assunto="Você foi indicado(a) como contato de confiança",
        texto=(
            f"{quem} indicou este e-mail como contato de confiança para um encontro.\n\n"
            "Você só vai receber outra mensagem se essa pessoa não confirmar, no horário combinado, que "
            "está tudo bem. Nesse caso, enviaremos o local e o horário do encontro para você tentar contato.\n\n"
            "Se você não conhece essa pessoa, pode ignorar este e-mail."
        ),
    )


def mensagem_de_alerta(para: str, e: dict) -> Mensagem:
    quem = e["como_te_conhecem"] or "A pessoa que indicou você"
    com = f"{e['com_nome']} (@{e['com_handle']} no app Afinidade)" if e["com_handle"] else "não informado"
    return Mensagem(
        para=para,
        assunto="Alerta: check-in do encontro não confirmado",
        texto=(
            f"{quem} indicou você como contato de confiança e NÃO confirmou que está bem no horário combinado.\n\n"
            f"Local: {e['local']}\n"
            f"Início: {e['inicio_em']:%d/%m/%Y %H:%M} (UTC)\n"
            f"Check-in esperado até: {e['checkin_ate']:%d/%m/%Y %H:%M} (UTC)\n"
            f"Com quem: {com}\n"
            + (f"Observações: {e['observacoes']}\n" if e["observacoes"] else "")
            + "\nTente falar com essa pessoa. Se não conseguir e achar que há risco, ligue 190 (Polícia Militar)."
            "\nViolência contra a mulher: 180."
        ),
    )


async def disparar_alertas(con, cif: Cifrador, carteiro) -> int:
    """Tarefa de fundo: encontros agendados com o check-in vencido geram o alerta (uma vez só)."""
    linhas = await con.fetch(
        f"""{_SELECT} WHERE e.situacao = 'agendado' AND e.checkin_ate <= now()
            ORDER BY e.checkin_ate LIMIT 50"""
    )
    enviados = 0
    for linha in linhas:
        # Marca antes de enviar (o UPDATE condicional garante um alerta só, mesmo com duas
        # réplicas rodando a tarefa). Se o envio falhar, volta para 'agendado' e tenta de novo.
        marcou = await con.execute(
            "UPDATE encontros SET situacao = 'alerta_enviado' WHERE id = $1 AND situacao = 'agendado'", linha["id"]
        )
        if marcou == "UPDATE 0":
            continue
        e = _abrir(cif, linha)
        try:
            await carteiro.enviar(mensagem_de_alerta(e["contato_email"], e))
            enviados += 1
        except Exception:
            # Um e-mail que falhou não pode atrasar os alertas das outras pessoas: volta para
            # 'agendado' (nova tentativa no próximo ciclo) e segue para o próximo.
            log.exception("Falha ao enviar alerta de encontro; nova tentativa no próximo ciclo")
            await con.execute("UPDATE encontros SET situacao = 'agendado' WHERE id = $1", linha["id"])
    return enviados


async def apagar_antigos(con) -> None:
    await con.execute("DELETE FROM encontros WHERE inicio_em < now() - make_interval(days => $1)", GUARDAR_DIAS)
