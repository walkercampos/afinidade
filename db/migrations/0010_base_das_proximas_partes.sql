-- 0010: base de dados para as Partes 3, 6, 9 e 10 do plano de execução.
--
-- Só ACRESCENTA colunas e tabelas, com valores padrão que mantêm o comportamento atual: a
-- versão anterior do app continua funcionando com este esquema (rollback seguro).
-- Detalhes e diagrama em docs/plano/parte-02-modelo-de-dados.md.

-- ---------------------------------------------------------------------------------------
-- Parte 10: termos de uso e consentimento LGPD versionados.
-- Guardamos QUAL versão foi aceita e QUANDO; aceitar uma versão nova grava por cima.
-- Contas antigas ficam com NULL = "precisa aceitar a versão atual" no próximo acesso.
ALTER TABLE contas
    ADD COLUMN termos_versao     text CHECK (termos_versao ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
    ADD COLUMN termos_aceitos_em timestamptz,
    ADD CONSTRAINT termos_completos CHECK ((termos_versao IS NULL) = (termos_aceitos_em IS NULL));

-- ---------------------------------------------------------------------------------------
-- Parte 3: verificação de idade (ECA Digital, Lei 15.211/2025).
-- O provedor externo faz selfie + prova de vida; aqui fica SÓ o resultado. Nenhuma imagem,
-- documento, CPF ou data de nascimento é gravado.
ALTER TABLE contas
    ADD COLUMN idade_verificada_em timestamptz,
    ADD COLUMN idade_provedor      text CHECK (idade_provedor ~ '^[a-z0-9-]{2,30}$'),
    ADD CONSTRAINT idade_completa CHECK ((idade_verificada_em IS NULL) = (idade_provedor IS NULL));

-- Tentativas em andamento. `sessao_hash` = HMAC do id de sessão do provedor (o id em claro
-- não fica guardado): serve para casar o retorno do provedor com a conta, e nada mais.
CREATE TABLE verificacoes_idade (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conta_id     uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    provedor     text NOT NULL CHECK (provedor ~ '^[a-z0-9-]{2,30}$'),
    sessao_hash  bytea NOT NULL UNIQUE CHECK (octet_length(sessao_hash) = 32),
    situacao     text NOT NULL DEFAULT 'pendente'
                 CHECK (situacao IN ('pendente', 'aprovada', 'recusada', 'expirada')),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    concluido_em timestamptz,
    CHECK ((situacao = 'pendente') = (concluido_em IS NULL))
);
CREATE INDEX verificacoes_idade_conta_idx ON verificacoes_idade (conta_id, criado_em DESC);
-- Limpeza das tentativas antigas
CREATE INDEX verificacoes_idade_criado_em_idx ON verificacoes_idade (criado_em);

-- ---------------------------------------------------------------------------------------
-- Parte 6: tempo de vida das mensagens configurável por conexão.
--
-- Valores permitidos, em minutos (NULL = nunca expira):
--   5, 15, 30, 60 · 6 h (360), 12 h (720), 24 h (1440) · 3 d (4320), 7 d (10080), 14 d (20160)
--   4 semanas (40320) · 1 mês (43200), 3 meses (129600), 6 meses (259200)
CREATE FUNCTION ttl_mensagem_valido(minutos integer) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT minutos IS NULL OR minutos IN (5, 15, 30, 60, 360, 720, 1440, 4320, 10080, 20160,
                                          40320, 43200, 129600, 259200)
$$;

-- O prazo vai GRAVADO em cada mensagem no momento do envio: mudar a configuração da conversa
-- vale só para as mensagens enviadas depois (regra do plano). As antigas mantêm o prazo com
-- que foram enviadas. expira_em = lida_em + ttl_minutos; sem leitura, não expira.
-- Padrão 5: o comportamento atual (a Parte 6 passa o padrão das conversas novas para 24 h).
ALTER TABLE mensagens
    ADD COLUMN ttl_minutos integer DEFAULT 5 CHECK (ttl_mensagem_valido(ttl_minutos));

-- Configuração acordada por conversa: o par não ordenado (conta_a < conta_b), como no índice
-- de mensagens. Sem linha = padrão do app.
CREATE TABLE conversas_config (
    conta_a       uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    conta_b       uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    ttl_minutos   integer CHECK (ttl_mensagem_valido(ttl_minutos)),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (conta_a, conta_b),
    CHECK (conta_a < conta_b)
);

-- Mudar o prazo exige o aceite das duas pessoas: uma propõe, a outra confirma. Uma proposta
-- por conversa; propor de novo substitui a anterior. Expira se ninguém responder.
CREATE TABLE propostas_ttl (
    conta_a      uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    conta_b      uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    proposto_por uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    ttl_minutos  integer CHECK (ttl_mensagem_valido(ttl_minutos)),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    expira_em    timestamptz NOT NULL DEFAULT now() + interval '7 days',
    PRIMARY KEY (conta_a, conta_b),
    CHECK (conta_a < conta_b),
    CHECK (proposto_por IN (conta_a, conta_b)),
    CHECK (expira_em > criado_em)
);
CREATE INDEX propostas_ttl_expira_em_idx ON propostas_ttl (expira_em);

-- ---------------------------------------------------------------------------------------
-- Parte 9: segurança física — compartilhar um encontro com um contato de confiança.
--
-- Local, horário combinado e o contato de confiança são dados sensíveis (e o contato é de uma
-- terceira pessoa): tudo vai CIFRADO (AES-256-GCM, chave fora do banco), no mesmo formato de
-- `mensagens.conteudo`. Em claro ficam só os horários que a tarefa de fundo precisa para
-- disparar o alerta se a pessoa não fizer o check-in.
CREATE TABLE encontros (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conta_id         uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    -- Com quem (se for uma conexão do app). SET NULL: se a outra pessoa excluir a conta, o
    -- registro de segurança de quem marcou o encontro continua valendo.
    com_conta_id     uuid REFERENCES contas(id) ON DELETE SET NULL,
    detalhes         bytea NOT NULL,  -- cifrado: local, observações
    contato_confianca bytea NOT NULL, -- cifrado: e-mail do contato de confiança
    inicio_em        timestamptz NOT NULL,
    checkin_ate      timestamptz NOT NULL,
    situacao         text NOT NULL DEFAULT 'agendado'
                     CHECK (situacao IN ('agendado', 'confirmado_ok', 'alerta_enviado', 'cancelado')),
    criado_em        timestamptz NOT NULL DEFAULT now(),
    CHECK (checkin_ate > inicio_em),
    CHECK (checkin_ate <= inicio_em + interval '24 hours'),
    CHECK (com_conta_id IS NULL OR com_conta_id <> conta_id)
);
CREATE INDEX encontros_conta_idx ON encontros (conta_id, inicio_em DESC);
-- A tarefa de fundo procura só os que passaram do prazo sem check-in
CREATE INDEX encontros_alerta_idx ON encontros (checkin_ate) WHERE situacao = 'agendado';

-- ---------------------------------------------------------------------------------------
-- Parte 10: modo discrição (nome e ícone neutros, conteúdo escondido na tela inicial).
ALTER TABLE contas ADD COLUMN modo_discreto boolean NOT NULL DEFAULT false;
