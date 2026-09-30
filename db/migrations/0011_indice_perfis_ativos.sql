-- 0011: índice para a descoberta com custo fixo.
-- A descoberta calcula a nota só para os perfis elegíveis mais ativos (app/descoberta.py,
-- CANDIDATOS_MAX). Com este índice, o banco percorre os perfis já na ordem de atividade e para
-- quando junta o suficiente, em vez de ler e ordenar todos a cada busca.
-- Teste de carga (docs/carga/): ~90 ms -> ~7 ms por busca com 30 mil perfis.
CREATE INDEX IF NOT EXISTS perfis_ativos_idx ON perfis (ativo_em DESC, conta_id DESC) WHERE visivel;
