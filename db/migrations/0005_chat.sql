-- 0005: chat entre conexões, com mensagens efêmeras.
--
-- Cada mensagem é apagada 5 minutos depois de lida (e deixa de ser devolvida pela API no
-- instante exato em que expira, mesmo antes da limpeza física). Mensagens nunca lidas são
-- apagadas após o prazo de retenção (MENSAGENS_RETENCAO_DIAS).
--
-- O texto nunca é gravado em claro: `conteudo` = versão (1 byte) || nonce (12) || AES-256-GCM.
-- A chave fica só na variável de ambiente CHAVE_MENSAGENS, fora do banco: um vazamento do
-- banco ou de um backup não expõe as conversas.
CREATE TABLE mensagens (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    de_id     uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    para_id   uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    conteudo  bytea NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT now(),
    lida_em   timestamptz,
    CHECK (de_id <> para_id)
);
-- Uma conversa é o par não ordenado (menor id, maior id).
CREATE INDEX mensagens_conversa_idx ON mensagens (LEAST(de_id, para_id), GREATEST(de_id, para_id), id);
CREATE INDEX mensagens_nao_lidas_idx ON mensagens (para_id, de_id) WHERE lida_em IS NULL;
CREATE INDEX mensagens_criado_em_idx ON mensagens (criado_em);
CREATE INDEX mensagens_lida_em_idx ON mensagens (lida_em) WHERE lida_em IS NOT NULL;
