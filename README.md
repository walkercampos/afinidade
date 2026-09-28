# Matchmaking API

Backend de conexões para uma rede social adulta (18+) focada em diversidade de gênero e fetiches.
Implementa o algoritmo de três camadas — **filtros rígidos**, **limites absolutos** e **afinidade ponderada** —
como uma API **FastAPI + PostgreSQL**.

## 1. Do script à API

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
GET /descobrir
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
O Python repete as camadas 1 e 2 como rede de segurança, e `POST /perfis/{id}/curtir` também as aplica: ninguém
consegue curtir um perfil que não busca o seu gênero ou cujo limite absoluto você quer praticar.

### Mudanças em relação ao script original

| Ponto | Script | API |
|---|---|---|
| Tag em mais de um nível (ex.: `quero` e `limite_absoluto`) | aceito silenciosamente | rejeitado (Pydantic + `CHECK` no banco) |
| Score | só do ponto de vista de A | `score_porcentagem` (visão de A, igual ao original) **+** `score_mutuo` (média dos dois lados), usado no ranking |
| Tags | texto livre | catálogo (`/catalogo/tags`) — evita "Bondage" ≠ "bondage " |
| Limites absolutos | — | nunca aparecem no perfil público; servem só para filtrar |

`POST /match/simular` aceita exatamente o payload do script original e devolve o mesmo JSON (mais `score_mutuo`).

## 2. Banco de dados

Schema completo em [`db/schema.sql`](db/schema.sql); catálogo inicial em [`db/seed.sql`](db/seed.sql).

```
generos (id smallint, slug, rotulo)          tags (id int, slug, rotulo, categoria, ativa)
   ▲                                            ▲  (referenciados por ID dentro dos arrays)
   │                                            │
contas (id uuid, handle, senha_hash, adulto_confirmado_em)
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

## 3. Anonimato e segurança

Dados sobre vida sexual e orientação são **dados pessoais sensíveis** (LGPD, art. 5º, II e art. 11). O que já está no código:

- **Pseudonimato:** só `handle` + senha. Sem e-mail, telefone ou nome civil. Os IDs expostos são UUIDs aleatórios.
- **Maioridade:** o cadastro exige data de nascimento com 18+ e confirmação explícita; a data **não é gravada**,
  só o instante da confirmação (`adulto_confirmado_em`).
- **Senhas** com scrypt (stdlib) e sal por usuário; tokens JWT com expiração.
- **Exclusão real:** `DELETE /conta` apaga conta, perfil, curtidas e bloqueios em cascata.
- **Bloqueio** esconde os dois perfis um do outro em todas as rotas e desfaz conexões.
- **Sem access log** no uvicorn (o `Dockerfile` usa `--no-access-log`), para não guardar IP + rota por requisição.

Antes de produção, você vai precisar de pelo menos:

- **Verificação de idade real** por um provedor (documento + selfie). Autodeclaração não basta para conteúdo adulto.
- **Consentimento específico** para o tratamento de dados sensíveis, política de privacidade e canal para o titular.
- **Rate limiting** em `/auth/*`, `/curtir` e `/descobrir` (ex.: no proxy reverso ou com Redis).
- **Denúncia e moderação** (tabela de denúncias, fila de revisão), além do bloqueio.
- **Criptografia em repouso** do banco e backups, e TLS em todas as conexões.
- Migrações versionadas (Alembic, dbmate) em vez de aplicar `schema.sql` na inicialização.

## Como rodar

### Com Docker

```bash
cp .env.example .env        # troque o JWT_SECRET
docker compose up --build
# API em http://localhost:8000, documentação interativa em http://localhost:8000/docs
```

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && set -a && . ./.env && set +a   # aponte DATABASE_URL para seu Postgres
uvicorn app.main:app --reload
```

### Testes

```bash
pytest tests/test_matcher.py                     # só o algoritmo, sem banco
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/matchmaking_test pytest   # tudo (o banco é APAGADO)
```

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| POST | `/auth/registro` | cria conta (18+), devolve token |
| POST | `/auth/login` | devolve token |
| DELETE | `/conta` | apaga tudo da conta |
| GET | `/catalogo/generos`, `/catalogo/tags` | opções válidas para o perfil |
| PUT / GET | `/perfil` | cria/atualiza e lê o próprio perfil |
| GET | `/descobrir?limite=20` | candidatos ranqueados com compatibilidade |
| GET | `/perfis/{id}` | perfil público + compatibilidade |
| POST | `/perfis/{id}/curtir` | curte; `{"conexao": true}` se for recíproco |
| POST | `/perfis/{id}/bloquear` | bloqueia nas duas direções |
| GET | `/conexoes` | curtidas recíprocas |
| POST | `/match/simular` | roda o algoritmo sobre dois payloads no formato do script original |

### Exemplo de uso no front-end

```js
const API = "http://localhost:8000";
const { access_token } = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ handle: "alfa", senha: "senha-forte-123" }),
}).then(r => r.json());

const feed = await fetch(`${API}/descobrir?limite=20`, {
  headers: { Authorization: `Bearer ${access_token}` },
}).then(r => r.json());

// feed[i] = { perfil: { id, nome_exibicao, bio, genero, quero, curioso },
//             compatibilidade: { match_valido, score_porcentagem, score_mutuo, tags_em_comum, motivo } }
```

## Estrutura

```
matchmaking/
├── app/
│   ├── matcher.py      # algoritmo puro (camadas 1, 2 e 3)
│   ├── repository.py   # todo o SQL (camadas 1 e 2 no banco)
│   ├── main.py         # rotas FastAPI
│   ├── schemas.py      # contratos Pydantic e validações (18+, níveis disjuntos)
│   ├── security.py     # scrypt + JWT
│   ├── db.py           # pool asyncpg e aplicação do schema
│   └── config.py       # variáveis de ambiente
├── db/schema.sql, db/seed.sql
├── tests/              # unitários (matcher) e ponta a ponta (API + Postgres)
├── Dockerfile, docker-compose.yml, .env.example
```

## Próximos passos naturais

- **Localização aproximada:** coluna `regiao` com geohash truncado (~5 km) — nunca coordenadas exatas — e filtro no SQL.
- **Score no banco:** com a extensão `intarray`, a camada 3 pode virar `icount(a & b) * 3 + ...` no próprio `ORDER BY`,
  eliminando o prefetch quando a base crescer.
- **Chat entre conexões**, com mensagens apagadas quando qualquer lado bloqueia ou exclui a conta.
