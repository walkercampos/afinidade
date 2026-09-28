-- Catálogo inicial. Os usuários escolhem apenas entre slugs daqui, o que mantém
-- os arrays pequenos (inteiros) e evita variações como "Bondage" / "bondage " / "BDSM-bondage".

INSERT INTO generos (slug, rotulo) VALUES
    ('homem-cis', 'Homem Cis'),
    ('mulher-cis', 'Mulher Cis'),
    ('homem-trans', 'Homem Trans'),
    ('mulher-trans', 'Mulher Trans'),
    ('travesti', 'Travesti'),
    ('nao-binarie', 'Não-binárie'),
    ('genero-fluido', 'Gênero fluido'),
    ('agenero', 'Agênero'),
    ('outro', 'Outro')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tags (slug, rotulo, categoria) VALUES
    ('bondage', 'Bondage', 'restricao'),
    ('leather', 'Leather', 'estetica'),
    ('latex', 'Látex', 'estetica'),
    ('dirty-talk', 'Dirty Talk', 'verbal'),
    ('impact-play', 'Impact Play', 'sensacao'),
    ('wax-play', 'Wax Play', 'sensacao'),
    ('privacao-sensorial', 'Privação sensorial', 'sensacao'),
    ('dominacao-submissao', 'Dominação / Submissão', 'dinamica'),
    ('roleplay', 'Roleplay', 'dinamica'),
    ('ageplay', 'Ageplay (entre adultos)', 'dinamica'),
    ('voyeurism', 'Voyeurismo', 'exposicao'),
    ('exibicionismo', 'Exibicionismo', 'exposicao'),
    ('podolatria', 'Podolatria', 'fetiche'),
    ('urophilia', 'Urofilia', 'fetiche')
ON CONFLICT (slug) DO NOTHING;
