# Afinidade — MVP

Rede social adulta (18+) de conexões por afinidade, focada em diversidade de gênero e fetiches.
Implementa o algoritmo de três camadas — **filtros rígidos**, **limites absolutos** e **afinidade ponderada** —
com uma API **FastAPI + PostgreSQL** e um front-end web leve (HTML/CSS/JS puro, ~7 KB comprimido, sem build).

**Objetivos do MVP:** custo zero, máximo anonimato entre usuários e mínimo de dados guardados, segurança
contra vazamentos, app leve e responsivo (funciona como PWA no celular).

## Custo zero

| Peça | Serviço gratuito | Observação |
|---|---|---|
| Código + CI | GitHub (repo privado + Actions) | testes e auditoria de dependências a cada push |
| API + front-end | [Render](https://render.com) plano *free* (via `render.yaml`) | a instância "dorme" sem uso; o 1º acesso depois disso leva alguns segundos |
| Banco | [Neon](https://neon.tech) Postgres plano *free* | criptografia em repouso e TLS inclusos |
| Domínio/HTTPS | subdomínio `*.onrender.com` com HTTPS automático | domínio próprio é o único custo opcional |

Os limites dos planos gratuitos mudam com frequência; confira nas páginas dos provedores antes de lançar.
Tudo roda num único contêiner (`Dockerfile`), então dá para migrar para Koyeb, Fly.io ou uma VPS sem mudar código.

### Deploy

1. Crie um projeto no Neon e copie a *connection string* (termina com `?sslmode=require`).
2. No Render: **New → Blueprint**, aponte para este repositório. Ele lê o `render.yaml`, gera o `JWT_SECRET` sozinho
   e pede o `DATABASE_URL` — cole a string do Neon.
3. Pronto. O schema é criado na primeira inicialização. Abra a URL `*.onrender.com`.

## Anonimato: o que o app garante e o que não dá para garantir

**Garantido pelo código:**

- **Nenhum dado de identificação civil.** Cadastro só com apelido + senha: sem e-mail, telefone, nome real, foto ou localização.
- **Data de nascimento não é guardada.** Serve só para checar 18+ no cadastro.
- **IPs não são gravados.** Sem log de acesso; o rate limit usa um HMAC do IP com chave que só existe na memória e muda a cada hora.
- **Limites absolutos são privados.** Ninguém vê os seus; eles só escondem pessoas incompatíveis.
- **Exclusão real e imediata** (`Conta → Excluir tudo`): conta, perfil, curtidas e conexões são apagados do banco na hora,
  e os tokens da conta deixam de valer.
- **Bloqueio mútuo:** as duas pessoas somem uma para a outra em todas as telas.

**Não é possível prometer "100% de anonimato"**, e é melhor não dizer isso aos usuários:

- O provedor de hospedagem e o banco veem IPs de conexão na infraestrutura deles.
- Um texto de bio ou apelido reutilizado de outra rede pode identificar a pessoa — o app avisa, mas não impede.
- **Questões legais para revisar com um(a) advogado(a) antes do lançamento público:** o Marco Civil da Internet (art. 15)
  obriga provedores de aplicação com fins econômicos a guardar registros de acesso (IP, data e hora) por 6 meses;
  a LGPD trata dados sobre vida sexual como sensíveis (art. 11); e o ECA Digital (Lei 15.211/2025) exige mecanismos
  confiáveis de verificação de idade para conteúdo adulto — autodeclaração pode não bastar.
  Um MVP fechado e sem fins lucrativos tem mais margem, mas isso precisa ser confirmado.

## Arquitetura: do script à API

### Por que FastAPI + PostgreSQL

- **Reuso direto do algoritmo.** O core já é Python; `app/matcher.py` é uma porta fiel do script, sem nenhuma
  dependência de framework ou banco, e é testado isoladamente (`tests/test_matcher.py`).
- **Assíncrono de ponta a ponta** (FastAPI + asyncpg): cada instância atende milhares de conexões simultâneas, e a API
  é *stateless* (JWT) — para escalar, basta subir mais réplicas atrás de um load balancer.
- **Validação e documentação automáticas** (Pydantic + OpenAPI em `/docs`), que servem como contrato para o front.
- **PostgreSQL** porque as camadas 1 e 2 do algoritmo são exatamente operações de conjunto que o Postgres faz nativamente
  sobre arrays (`&&` = interseção não vazia, `@>` = contém), com índices GIN. MongoDB também tem `$in`/`$all` sobre arrays,
  mas o Postgres dá, de graça, integridade referencial, `CHECK` constraints, transações e `ON DELETE CASCADE`,
  o que importa muito para exclusão real de dados sensíveis.

### Onde cada camada roda

```
GET /api/descobrir
  │
  ├─ PostgreSQL (buscar_candidatos) ─────────────────────────────── usa índices GIN
  │    Camada 1: p.genero_id = ANY(minha_busca) AND p.busca_por @> ARRAY[meu_genero]
  │    Camada 2: NOT (p.tags_quero && meus_limites) AND NOT (p.tags_limite && meu_quero)
  │    + exclui bloqueados (nas duas direções) e quem eu já curti
  │    → até CANDIDATOS_PREFETCH perfis, mais ativos primeiro
  │
  └─ Python (matcher.calcular_match / score_mutuo)
       Camada 3: pesos 3 / 2 / 1, normalização, tags em comum
       → ordena por score_mutuo e devolve os `limite` melhores
```

O descarte pesado (gênero e dealbreakers) acontece no banco, então o Python só pontua quem já é elegível.
O Python repete as camadas 1 e 2 como rede de segurança, e `POST /api/perfis/{id}/curtir` também as aplica: ninguém
consegue curtir um perfil que não busca o seu gênero ou cujo limite absoluto você quer praticar.

### Mudanças em relação ao script original

| Ponto | Script | API |
|---|---|---|
| Tag em mais de um nível (ex.: `quero` e `limite_absoluto`) | aceito silenciosamente | rejeitado (Pydantic + `CHECK` no banco) |
| Score | só do ponto de vista de A | `score_porcentagem` (visão de A, igual ao original) **+** `score_mutuo` (média dos dois lados), usado no ranking |
| Tags | texto livre | catálogo (`/api/catalogo/tags`) — evita "Bondage" ≠ "bondage " |
| Limites absolutos | — | nunca aparecem no perfil público; servem só para filtrar |

`POST /api/match/simular` aceita exatamente o payload do script original e devolve o mesmo JSON (mais `score_mutuo`).

## Banco de dados

Schema completo em [`db/schema.sql`](db/schema.sql); catálogo inicial em [`db/seed.sql`](db/seed.sql).

```
generos (id smallint, slug, rotulo)          tags (id int, slug, rotulo, categoria, ativa)
   ▲                                            ▲  (referenciados por ID dentro dos arrays)
   │                                            │
contas (id uuid, handle, senha_hash, adulto_confirmado_em, consentimento_em, token_versao)
   │ 1:1, ON DELETE CASCADE
perfis (conta_id, nome_exibicao, bio, genero_id,
        busca_por     smallint[]  ── GIN
        tags_quero    integer[]   ── GIN
        tags_curioso  integer[]
        tags_limite   integer[]   ── GIN
        visivel, ativo_em)
   CHECK: os três arrays de tags são disjuntos

bloqueios (bloqueador_id, bloqueado_id)       curtidas (de_id, para_id)  → curtida recíproca = conexão
```

**Por que arrays e não uma tabela `perfil_tags (conta_id, tag_id, nivel)`?** A tabela de junção é mais "normalizada",
mas para achar candidatos precisaríamos de `NOT EXISTS` com joins para cada perfil. Com arrays, cada camada vira um
único operador indexável, e o perfil inteiro é lido em uma linha. O custo é que o Postgres não valida FK dentro de
arrays — por isso a API resolve todo slug contra o catálogo antes de gravar (`repository.ids_por_slug`).
Se um dia precisar de analytics do tipo "quantas pessoas querem X", `WHERE tags_quero @> ARRAY[X]` já usa o índice.

## Segurança

| Ameaça | Proteção |
|---|---|
| Roubo de sessão via XSS | token em cookie **HttpOnly** (o JavaScript não lê); front insere dados só com `textContent`; **CSP** estrita sem scripts inline nem de terceiros |
| CSRF | cookie `SameSite=Strict` + header `X-CSRF` obrigatório em escrita (sites de terceiros não conseguem enviá-lo) |
| Força bruta de senha | scrypt com sal; rate limit por IP **e** por apelido no login |
| Descobrir quais apelidos existem pelo tempo de resposta | login verifica um hash falso quando o apelido não existe |
| Token vazado | expira em 24 h; "Sair de todos os dispositivos" e exclusão de conta invalidam todos os tokens na hora (`token_versao`) |
| SQL injection | 100% consultas parametrizadas (asyncpg); nomes de tabela só de uma lista fixa |
| Assédio | só dá para curtir quem busca o seu gênero e não conflita com seus limites; bloqueio mútuo |
| Clickjacking, sniffing, vazamento de URL | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, HSTS em produção |
| Cache de dados sensíveis | `Cache-Control: no-store` em toda a API |
| Dependência vulnerável | `pip-audit` no CI + Dependabot semanal |
| Contêiner comprometido | roda como usuário sem privilégios; sem cabeçalho `Server` |
| Documentação expondo a API | `/docs` desligado em produção |

Veja também [`SECURITY.md`](SECURITY.md) (como reportar falhas e o que ainda falta).

## Como rodar

### Com Docker

```bash
cp .env.example .env        # troque o JWT_SECRET
docker compose up --build
# App em http://localhost:8000, documentação da API em http://localhost:8000/docs
```

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && set -a && . ./.env && set +a   # aponte DATABASE_URL para seu Postgres
uvicorn app.main:app --reload
# abra http://localhost:8000
```

### Testes

```bash
pytest tests/test_matcher.py                     # só o algoritmo, sem banco
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/matchmaking_test pytest   # tudo (o banco é APAGADO)
```

## Endpoints (todos sob `/api`)

| Método | Rota | O que faz |
|---|---|---|
| POST | `/auth/registro` | cria conta (18+ e consentimento), inicia sessão |
| POST | `/auth/login` | inicia sessão |
| POST | `/auth/sair` | encerra a sessão em todos os dispositivos |
| DELETE | `/conta` | apaga tudo da conta |
| GET | `/catalogo/generos`, `/catalogo/tags` | opções válidas para o perfil |
| PUT / GET | `/perfil` | cria/atualiza e lê o próprio perfil |
| GET | `/descobrir?limite=20` | candidatos ranqueados com compatibilidade |
| GET | `/perfis/{id}` | perfil público + compatibilidade |
| POST | `/perfis/{id}/curtir` | curte; `{"conexao": true}` se for recíproco |
| POST | `/perfis/{id}/bloquear` | bloqueia nas duas direções |
| GET | `/conexoes` | curtidas recíprocas |
| POST | `/match/simular` | roda o algoritmo sobre dois payloads no formato do script original |

Autenticação: o front-end usa o cookie de sessão (e envia `X-CSRF: 1`); outros clientes podem usar
`Authorization: Bearer <access_token>` devolvido por `/auth/login`.

## Estrutura

```
├── app/
│   ├── matcher.py      # algoritmo puro (camadas 1, 2 e 3)
│   ├── repository.py   # todo o SQL (camadas 1 e 2 no banco)
│   ├── main.py         # rotas, cabeçalhos de segurança, serve o front
│   ├── schemas.py      # contratos Pydantic e validações (18+, consentimento, níveis disjuntos)
│   ├── security.py     # scrypt, JWT, cookie HttpOnly, anti-CSRF
│   ├── ratelimit.py    # rate limit em memória sem guardar IPs
│   ├── db.py, config.py
├── static/             # front-end: index.html, app.js, app.css, manifest (PWA)
├── db/schema.sql, db/seed.sql
├── tests/              # algoritmo, rate limit e ponta a ponta (API + Postgres)
├── Dockerfile, docker-compose.yml, render.yaml, .env.example
└── .github/            # CI (testes + pip-audit) e Dependabot
```

## Próximos passos naturais

- **Denúncias e moderação** (tabela de denúncias + fila de revisão) antes de abrir para o público.
- **Verificação de idade** por provedor externo, se exigida (ver seção de anonimato).
- **Rate limit compartilhado** (Redis gratuito, ex.: Upstash) se passar a rodar mais de uma instância.
- **Migrações versionadas** (dbmate, Alembic) quando o schema começar a mudar com usuários reais.
- **Localização aproximada:** coluna `regiao` com geohash truncado (~5 km) — nunca coordenadas exatas — e filtro no SQL.
- **Score no banco:** com a extensão `intarray`, a camada 3 pode virar `icount(a & b) * 3 + ...` no próprio `ORDER BY`,
  eliminando o prefetch quando a base crescer.
- **Chat entre conexões**, com mensagens apagadas quando qualquer lado bloqueia ou exclui a conta.
