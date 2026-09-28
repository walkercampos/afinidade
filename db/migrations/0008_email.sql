-- 0008: contas criadas com e-mail (código/link de uso único) e sem senha.
--
-- O e-mail NUNCA é gravado em texto. Guardamos só um HMAC-SHA256 dele com uma chave secreta
-- (EMAIL_PEPPER) que fica fora do banco: dá para achar a conta de quem digita o e-mail, mas um
-- vazamento do banco não revela e-mail nenhum (nem por dicionário, sem a chave).
ALTER TABLE contas ADD COLUMN email_hash bytea UNIQUE CHECK (octet_length(email_hash) = 32);

-- Senhas deixam de existir: o acesso é por e-mail (código/link) e biometria (passkey).
ALTER TABLE contas DROP COLUMN senha_hash;

-- Verificações de e-mail pendentes. Código e token também só em hash; uso único; 15 min.
CREATE TABLE verificacoes_email (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email_hash  bytea NOT NULL CHECK (octet_length(email_hash) = 32),
    conta_id    uuid REFERENCES contas(id) ON DELETE CASCADE,  -- preenchido quando é login
    dados       jsonb,                                         -- cadastro pendente (apelido)
    codigo_hash bytea NOT NULL,
    token_hash  bytea NOT NULL UNIQUE,
    tentativas  smallint NOT NULL DEFAULT 0,
    expira_em   timestamptz NOT NULL,
    CHECK ((conta_id IS NULL) <> (dados IS NULL))  -- ou é cadastro, ou é login
);
CREATE INDEX verificacoes_email_expira_idx ON verificacoes_email (expira_em);
CREATE INDEX verificacoes_email_hash_idx ON verificacoes_email (email_hash);
