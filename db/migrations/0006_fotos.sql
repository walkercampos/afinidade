-- 0006: fotos protegidas.
--
-- Para cada foto guardamos duas versões, ambas cifradas (AES-256-GCM) com a mesma chave do chat:
--   nitida  : a foto sem metadados (EXIF/GPS removidos), no máximo 1080 px;
--   borrada : gerada no servidor a partir de uma miniatura de 24 px — irreversível.
-- Quem não tem autorização recebe SÓ a borrada: a nítida nunca chega ao navegador dessa
-- pessoa (blur feito só com CSS seria removido em um clique no "Inspecionar elemento").
CREATE TABLE fotos (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conta_id  uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    hash      text NOT NULL CHECK (hash ~ '^[0-9a-f]{64}$'),
    nitida    bytea NOT NULL,
    borrada   bytea NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conta_id, hash)
);
CREATE INDEX fotos_conta_idx ON fotos (conta_id, criado_em);

-- Pedido de acesso às fotos nítidas. Só o dono muda o status (aprovado/negado).
CREATE TABLE acessos_fotos (
    dono_id         uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    visualizador_id uuid NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'aprovado', 'negado')),
    criado_em       timestamptz NOT NULL DEFAULT now(),
    respondido_em   timestamptz,
    PRIMARY KEY (dono_id, visualizador_id),
    CHECK (dono_id <> visualizador_id)
);
CREATE INDEX acessos_fotos_pendentes_idx ON acessos_fotos (dono_id) WHERE status = 'pendente';
