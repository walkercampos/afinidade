-- 0001: schema inicial (PostgreSQL 13+; gen_random_uuid() é nativo).
--
-- Decisão central: as tags de cada perfil ficam em arrays de inteiros (IDs do catálogo),
-- uma coluna por nível. Isso permite que as camadas 1 e 2 do algoritmo (gênero e
-- dealbreakers) rodem DENTRO do banco com os operadores de array && e @>, usando
-- índices GIN — só os candidatos que sobrevivem aos filtros chegam ao Python.

CREATE TABLE IF NOT EXISTS generos (
    id     smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug   text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{1,40}$'),
    rotulo text NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug      text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{1,40}$'),
    rotulo    text NOT NULL,
    categoria text,
    ativa     boolean NOT NULL DEFAULT true
);

-- Conta = credenciais. Sem e-mail, telefone ou nome civil: o handle é pseudônimo.
-- A data de nascimento é verificada no cadastro e NÃO é persistida; guardamos só quando
-- a maioridade e o consentimento (LGPD art. 11) foram dados.
-- token_versao: incrementar invalida todos os tokens emitidos (sair de todos os dispositivos).
CREATE TABLE IF NOT EXISTS contas (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    handle               text NOT NULL UNIQUE CHECK (handle ~ '^[a-z0-9_]{3,30}$'),
    senha_hash           text NOT NULL,
    adulto_confirmado_em timestamptz NOT NULL,
    consentimento_em     timestamptz NOT NULL,
    token_versao         integer NOT NULL DEFAULT 0,
    criado_em            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS perfis (
    conta_id      uuid PRIMARY KEY REFERENCES contas(id) ON DELETE CASCADE,
    nome_exibicao text NOT NULL CHECK (char_length(nome_exibicao) BETWEEN 1 AND 40),
    bio           text CHECK (char_length(bio) <= 500),
    genero_id     smallint NOT NULL REFERENCES generos(id),
    busca_por     smallint[] NOT NULL CHECK (cardinality(busca_por) > 0),
    tags_quero    integer[] NOT NULL DEFAULT '{}',
    tags_curioso  integer[] NOT NULL DEFAULT '{}',
    tags_limite   integer[] NOT NULL DEFAULT '{}',
    visivel       boolean NOT NULL DEFAULT true,
    ativo_em      timestamptz NOT NULL DEFAULT now(),
    -- Uma tag pertence a no máximo um nível: sem isso, "quero" e "limite" da mesma
    -- tag gerariam um perfil que bloqueia a si mesmo.
    CONSTRAINT tags_niveis_disjuntos CHECK (
        NOT (tags_quero && tags_curioso)
        AND NOT (tags_quero && tags_limite)
        AND NOT (tags_curioso && tags_limite)
    )
);

-- Camada 1: "B busca o gênero de A"  ->  busca_por @> ARRAY[genero_de_A]
CREATE INDEX IF NOT EXISTS perfis_busca_por_gin ON perfis USING gin (busca_por);
-- Camada 2: "B quer algo que é limite de A" / "B tem limite em algo que A quer"
CREATE INDEX IF NOT EXISTS perfis_tags_quero_gin  ON perfis USING gin (tags_quero);
CREATE INDEX IF NOT EXISTS perfis_tags_limite_gin ON perfis USING gin (tags_limite);
-- Feed: "A busca o gênero de B", ordenado por atividade recente
CREATE INDEX IF NOT EXISTS perfis_feed_idx ON perfis (genero_id, ativo_em DESC) WHERE visivel;

CREATE TABLE IF NOT EXISTS bloqueios (
    bloqueador_id uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    bloqueado_id  uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (bloqueador_id, bloqueado_id),
    CHECK (bloqueador_id <> bloqueado_id)
);
CREATE INDEX IF NOT EXISTS bloqueios_bloqueado_idx ON bloqueios (bloqueado_id);

-- Curtidas unilaterais; uma conexão é uma curtida recíproca.
CREATE TABLE IF NOT EXISTS curtidas (
    de_id     uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    para_id   uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    criado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (de_id, para_id),
    CHECK (de_id <> para_id)
);
CREATE INDEX IF NOT EXISTS curtidas_para_idx ON curtidas (para_id);
