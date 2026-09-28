-- 0007: login sem senha com passkeys (WebAuthn).
--
-- Uma passkey é um par de chaves criado no aparelho da pessoa: a chave privada nunca sai de lá
-- (fica no chaveiro do celular/computador ou numa chave física) e aqui guardamos só a pública.
-- Não há segredo no banco que permita entrar na conta: um vazamento não compromete ninguém.

-- Contas criadas só com passkey não têm senha.
ALTER TABLE contas ALTER COLUMN senha_hash DROP NOT NULL;

-- Identificador opaco e aleatório da conta para os autenticadores (user.id do WebAuthn).
-- Não é o id da conta: nada que o chaveiro do aparelho guarde aponta para dados do app.
ALTER TABLE contas ADD COLUMN webauthn_id bytea UNIQUE CHECK (octet_length(webauthn_id) = 32);

CREATE TABLE passkeys (
    id            bytea PRIMARY KEY CHECK (octet_length(id) BETWEEN 16 AND 1023),  -- credential ID
    conta_id      uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    chave_publica bytea NOT NULL,                -- chave pública em formato COSE
    contador      bigint NOT NULL DEFAULT 0,     -- detecta autenticador clonado
    transportes   text[] NOT NULL DEFAULT '{}',
    sincronizada  boolean NOT NULL DEFAULT false, -- passkey com backup (iCloud, Google...)
    nome          text NOT NULL CHECK (char_length(nome) BETWEEN 1 AND 40),
    criado_em     timestamptz NOT NULL DEFAULT now(),
    usado_em      timestamptz
);
CREATE INDEX passkeys_conta_idx ON passkeys (conta_id);

-- Desafios de uso único (5 min). Guardados no banco, e não em memória, para funcionar com
-- várias instâncias e para que cada desafio só possa ser consumido uma vez (anti-replay).
CREATE TABLE desafios_webauthn (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    desafio   bytea NOT NULL CHECK (octet_length(desafio) >= 32),
    tipo      text NOT NULL CHECK (tipo IN ('registro', 'login', 'adicionar')),
    conta_id  uuid REFERENCES contas(id) ON DELETE CASCADE,  -- só em 'adicionar'
    dados     jsonb,                                         -- cadastro pendente (apelido, webauthn_id)
    expira_em timestamptz NOT NULL
);
CREATE INDEX desafios_webauthn_expira_idx ON desafios_webauthn (expira_em);
