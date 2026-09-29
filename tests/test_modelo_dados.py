"""Regras do banco (migração 0010 e garantias gerais do esquema).

Testa direto no PostgreSQL: estas regras valem mesmo se algum código da API errar.
"""

import os
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

TTLS_VALIDOS = [None, 5, 15, 30, 60, 360, 720, 1440, 4320, 10080, 20160, 40320, 43200, 129600, 259200]
BLOB = b"\x01" + os.urandom(40)  # formato de um valor cifrado (versão + nonce + dados)


def _par(a, b):
    return tuple(sorted((a.id, b.id)))


def test_toda_referencia_a_conta_some_ou_se_desliga_ao_excluir(client, db):
    """Exclusão imediata (regra do plano): nenhuma tabela pode segurar uma conta apagada."""
    linhas = db.fetch(
        """
        SELECT c.conrelid::regclass::text AS tabela, c.confdeltype::text AS regra
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.confrelid = 'contas'::regclass
        """
    )
    assert linhas, "nenhuma referência a contas encontrada"
    presas = [(r["tabela"], r["regra"]) for r in linhas if r["regra"] not in ("c", "n")]  # CASCADE, SET NULL
    assert presas == []


def test_dados_sensiveis_novos_so_existem_cifrados(client, db):
    tipos = dict(
        db.fetch(
            """
            SELECT table_name || '.' || column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND (table_name, column_name) IN
                  (('encontros', 'detalhes'), ('encontros', 'contato_confianca'),
                   ('verificacoes_idade', 'sessao_hash'))
            """
        )
    )
    assert tipos == {
        "encontros.detalhes": "bytea",
        "encontros.contato_confianca": "bytea",
        "verificacoes_idade.sessao_hash": "bytea",
    }
    # Verificação de idade: nenhuma coluna para documento, CPF, imagem ou data de nascimento
    colunas = {
        r["column_name"]
        for r in db.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name IN ('contas', 'verificacoes_idade')"
        )
    }
    assert not {c for c in colunas if any(p in c for p in ("cpf", "documento", "selfie", "imagem", "nascimento"))}


@pytest.mark.parametrize("ttl", TTLS_VALIDOS)
def test_prazos_de_mensagem_permitidos(client, db, ttl):
    assert db.fetchval("SELECT ttl_mensagem_valido($1)", ttl) is True


@pytest.mark.parametrize("ttl", [0, 1, 4, 10, 1439, 1441, 525600, -5])
def test_prazos_de_mensagem_recusados(client, db, ttl):
    assert db.fetchval("SELECT ttl_mensagem_valido($1)", ttl) is False


def test_mensagem_guarda_o_prazo_e_mantem_os_5_minutos_por_padrao(conexao_entre, db):
    a, b = conexao_entre()
    assert a.post(f"/api/conversas/{b.id}/mensagens", json={"texto": "oi"}).status_code == 201
    assert db.fetchval("SELECT ttl_minutos FROM mensagens WHERE de_id = $1::uuid", a.id) == 5
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("UPDATE mensagens SET ttl_minutos = 7 WHERE de_id = $1::uuid", a.id)
    db.execute("UPDATE mensagens SET ttl_minutos = NULL WHERE de_id = $1::uuid", a.id)  # NULL = nunca


def test_configuracao_e_proposta_de_prazo_por_conversa(conexao_entre, pessoa, db):
    a, b = conexao_entre()
    menor, maior = _par(a, b)
    db.execute(
        "INSERT INTO conversas_config (conta_a, conta_b, ttl_minutos) VALUES ($1::uuid, $2::uuid, 1440)", menor, maior
    )
    # O par é sempre (menor, maior): a mesma conversa não pode ter duas configurações
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("INSERT INTO conversas_config (conta_a, conta_b) VALUES ($1::uuid, $2::uuid)", maior, menor)

    db.execute(
        "INSERT INTO propostas_ttl (conta_a, conta_b, proposto_por, ttl_minutos)"
        " VALUES ($1::uuid, $2::uuid, $1::uuid, 60)",
        menor,
        maior,
    )
    # Só quem está na conversa pode propor
    de_fora = pessoa()
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute(
            "UPDATE propostas_ttl SET proposto_por = $3::uuid WHERE conta_a = $1::uuid AND conta_b = $2::uuid",
            menor,
            maior,
            de_fora.id,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("UPDATE propostas_ttl SET ttl_minutos = 2 WHERE conta_a = $1::uuid", menor)

    # Excluir uma das contas leva junto a configuração e a proposta
    assert a.delete("/api/conta").status_code == 204
    assert db.fetchval("SELECT count(*) FROM conversas_config WHERE $1::uuid IN (conta_a, conta_b)", a.id) == 0
    assert db.fetchval("SELECT count(*) FROM propostas_ttl WHERE $1::uuid IN (conta_a, conta_b)", a.id) == 0


def test_termos_e_idade_sao_gravados_completos(pessoa, db):
    p = pessoa()
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("UPDATE contas SET termos_versao = '2026-10-01' WHERE id = $1::uuid", p.id)  # sem a data do aceite
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("UPDATE contas SET idade_verificada_em = now() WHERE id = $1::uuid", p.id)  # sem o provedor
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute(
            "UPDATE contas SET termos_versao = 'v2', termos_aceitos_em = now() WHERE id = $1::uuid", p.id
        )  # versão é sempre uma data AAAA-MM-DD
    db.execute(
        "UPDATE contas SET termos_versao = '2026-10-01', termos_aceitos_em = now(),"
        " idade_verificada_em = now(), idade_provedor = 'didit' WHERE id = $1::uuid",
        p.id,
    )
    # Contas existentes começam sem aceite nem verificação, e com o modo discreto desligado
    nova = pessoa()
    linha = db.fetchrow(
        "SELECT termos_versao, idade_verificada_em, modo_discreto FROM contas WHERE id = $1::uuid", nova.id
    )
    assert dict(linha) == {"termos_versao": None, "idade_verificada_em": None, "modo_discreto": False}


def test_tentativa_de_verificacao_de_idade(pessoa, db):
    p = pessoa()
    inserir = "INSERT INTO verificacoes_idade (conta_id, provedor, sessao_hash) VALUES ($1::uuid, 'didit', $2)"
    db.execute(inserir, p.id, os.urandom(32))
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute(inserir, p.id, b"curto")  # só o HMAC de 32 bytes, nunca o id em claro
    with pytest.raises(asyncpg.CheckViolationError):
        db.execute("UPDATE verificacoes_idade SET situacao = 'aprovada' WHERE conta_id = $1::uuid", p.id)
    db.execute(
        "UPDATE verificacoes_idade SET situacao = 'aprovada', concluido_em = now() WHERE conta_id = $1::uuid", p.id
    )
    assert p.delete("/api/conta").status_code == 204
    assert db.fetchval("SELECT count(*) FROM verificacoes_idade WHERE conta_id = $1::uuid", p.id) == 0


def test_encontro_prazos_e_exclusao(conexao_entre, db):
    a, b = conexao_entre()
    inicio = datetime.now(UTC) + timedelta(days=1)
    inserir = (
        "INSERT INTO encontros (conta_id, com_conta_id, detalhes, contato_confianca, inicio_em, checkin_ate)"
        " VALUES ($1::uuid, $2::uuid, $3, $3, $4, $5) RETURNING id"
    )
    encontro = db.fetchval(inserir, a.id, b.id, BLOB, inicio, inicio + timedelta(hours=3))
    for fim in (inicio, inicio - timedelta(hours=1), inicio + timedelta(hours=25)):
        with pytest.raises(asyncpg.CheckViolationError):
            db.fetchval(inserir, a.id, b.id, BLOB, inicio, fim)
    with pytest.raises(asyncpg.CheckViolationError):
        db.fetchval(inserir, a.id, a.id, BLOB, inicio, inicio + timedelta(hours=1))  # consigo mesma

    # Se a outra pessoa sai do app, o registro de segurança de quem marcou continua
    assert b.delete("/api/conta").status_code == 204
    assert db.fetchval("SELECT com_conta_id FROM encontros WHERE id = $1", encontro) is None
    # Se quem marcou sai, o encontro vai junto
    assert a.delete("/api/conta").status_code == 204
    assert db.fetchval("SELECT count(*) FROM encontros WHERE id = $1", encontro) == 0
