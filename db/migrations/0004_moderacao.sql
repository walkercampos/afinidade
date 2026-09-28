-- 0004: denúncias e moderação.

-- situacao: 'ativa' | 'em_revisao' (oculta e sem poder curtir/enviar mensagens até um(a)
-- moderador(a) decidir) | 'banida' (não entra mais; tokens invalidados).
ALTER TABLE contas
    ADD COLUMN papel    text NOT NULL DEFAULT 'usuario' CHECK (papel IN ('usuario', 'moderador')),
    ADD COLUMN situacao text NOT NULL DEFAULT 'ativa' CHECK (situacao IN ('ativa', 'em_revisao', 'banida'));

CREATE TABLE denuncias (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- SET NULL: a denúncia continua valendo se quem denunciou excluir a conta.
    denunciante_id uuid REFERENCES contas(id) ON DELETE SET NULL,
    denunciado_id  uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    motivo         text NOT NULL CHECK (motivo IN (
                       'assedio', 'menor_de_idade', 'perfil_falso', 'spam',
                       'conteudo_ilegal', 'discurso_de_odio', 'outro')),
    detalhes       text CHECK (char_length(detalhes) <= 1000),
    -- Mensagens anexadas pela pessoa denunciante, cifradas como o resto do chat.
    evidencias     bytea,
    status         text NOT NULL DEFAULT 'aberta' CHECK (status IN ('aberta', 'procedente', 'improcedente')),
    criado_em      timestamptz NOT NULL DEFAULT now(),
    resolvido_em   timestamptz,
    CHECK (denunciante_id IS NULL OR denunciante_id <> denunciado_id)
);
CREATE UNIQUE INDEX denuncias_uma_aberta_por_par ON denuncias (denunciante_id, denunciado_id) WHERE status = 'aberta';
CREATE INDEX denuncias_abertas_idx ON denuncias (denunciado_id) WHERE status = 'aberta';

-- Toda decisão de moderação fica registrada (quem, o quê, quando, por quê).
CREATE TABLE moderacao_log (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    moderador_id  uuid REFERENCES contas(id) ON DELETE SET NULL,
    conta_id      uuid REFERENCES contas(id) ON DELETE SET NULL,
    acao          text NOT NULL CHECK (acao IN ('revisao_automatica', 'banir', 'restaurar')),
    observacao    text CHECK (char_length(observacao) <= 1000),
    criado_em     timestamptz NOT NULL DEFAULT now()
);
