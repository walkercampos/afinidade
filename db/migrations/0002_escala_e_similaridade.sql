-- 0002: camada 3 (afinidade) e similaridade calculadas no próprio Postgres.
--
-- intarray fornece `&` (interseção) e icount() para int[], permitindo ordenar TODOS os
-- candidatos elegíveis por score direto no ORDER BY, com paginação por cursor.
-- Atenção: com intarray, os operadores && e @> sobre integer[] passam a ser os da extensão,
-- que só usam índices GIN com a opclass gin__int_ops — por isso os índices são recriados.
CREATE EXTENSION IF NOT EXISTS intarray;

DROP INDEX IF EXISTS perfis_tags_quero_gin;
DROP INDEX IF EXISTS perfis_tags_limite_gin;
CREATE INDEX perfis_tags_quero_gin  ON perfis USING gin (tags_quero gin__int_ops);
CREATE INDEX perfis_tags_limite_gin ON perfis USING gin (tags_limite gin__int_ops);
