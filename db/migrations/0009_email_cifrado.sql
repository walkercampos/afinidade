-- 0009: e-mail recuperável para o app poder falar com a pessoa (avisos da conta, moderação).
--
-- O e-mail passa a ser guardado CIFRADO (AES-256-GCM) com a chave CHAVE_EMAIL, que fica fora do
-- banco e é separada da chave das mensagens. O email_hash (HMAC) continua sendo usado para achar
-- a conta; o texto cifrado só é aberto na hora de enviar um e-mail.
ALTER TABLE contas ADD COLUMN email_cifrado bytea;
ALTER TABLE verificacoes_email ADD COLUMN email_cifrado bytea;

-- Registro de todo contato feito com uma conta (quem, quando, assunto). O corpo não é guardado.
CREATE TABLE contatos_log (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conta_id   uuid REFERENCES contas(id) ON DELETE SET NULL,
    enviado_por text NOT NULL CHECK (char_length(enviado_por) <= 60),  -- 'cli' ou o apelido do moderador
    assunto    text NOT NULL CHECK (char_length(assunto) <= 120),
    enviado_em timestamptz NOT NULL DEFAULT now()
);
