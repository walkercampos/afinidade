-- 0012: índices de mensagens por remetente e por destinatário.
-- A lista de conversas filtra por "de_id = eu OR para_id = eu": sem estes índices o banco lia a
-- tabela inteira a cada abertura da lista (teste de carga, docs/carga/). Também servem ao
-- ON DELETE CASCADE ao excluir uma conta e ao "apagar minhas mensagens" da conversa.
CREATE INDEX IF NOT EXISTS mensagens_de_idx ON mensagens (de_id, para_id);
CREATE INDEX IF NOT EXISTS mensagens_para_idx ON mensagens (para_id);
