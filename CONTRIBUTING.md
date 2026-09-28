# Como contribuir

Obrigado por ajudar! Este guia explica como o código está organizado, como rodar tudo
localmente e o passo a passo para criar uma funcionalidade nova sem quebrar as garantias
de privacidade do app.

## Ambiente local (5 minutos)

Requisitos: Python 3.11+, Docker (só para o PostgreSQL) e `make`.

```bash
cp .env.example .env          # gere JWT_SECRET e CHAVE_MENSAGENS com o comando indicado no arquivo
make instalar                 # dependências de desenvolvimento + hooks de pre-commit
make db                       # sobe o PostgreSQL local (cria também o banco de testes)
make rodar                    # http://localhost:8000  ·  documentação da API em /docs
make verificar                # lint + testes + auditoria: exatamente o que o CI roda
```

`make` sem argumentos lista todos os comandos.

## Mapa do código

```
app/
├── main.py          montagem: ciclo de vida, cabeçalhos de segurança, registro das rotas
├── config.py        todas as variáveis de ambiente (um único lugar)
├── security.py      senhas, JWT, cookie, anti-CSRF e as dependências de sessão
├── deps.py          dependências comuns das rotas (perfil obrigatório, perfil visível, cifrador)
├── routes/          CAMADA HTTP — uma por domínio: valida entrada, escolhe status, chama o domínio
│   ├── auth.py  perfil.py  descoberta.py  chat.py  fotos.py  moderacao.py  saude.py
├── schemas.py       contratos de entrada/saída (Pydantic), um bloco por domínio
│
├── matcher.py       ALGORITMO puro (sem banco): compatibilidade, score mútuo, similaridade
├── descoberta.py    o mesmo algoritmo em SQL, para ranquear e paginar dentro do Postgres
├── repository.py    SQL de contas, perfis, curtidas, bloqueios e conexões
├── mensagens.py     chat efêmero        ├── fotos.py      fotos protegidas
├── moderacao.py     denúncias e revisão ├── geo.py        geohash e distâncias
├── cripto.py        AES-GCM para dados em repouso
├── ratelimit.py     limite de requisições sem guardar IPs
└── admin.py         linha de comando (promover moderador, migrar)
db/migrations/       uma migração SQL por arquivo, aplicadas em ordem na inicialização
tests/               conftest.py tem as fixtures (`pessoa`, `conexao_entre`, `db`)
```

**Regra das camadas:** rotas não escrevem SQL e módulos de domínio não conhecem HTTP
(nada de `HTTPException` fora de `routes/`, `deps.py` e `security.py`). Assim a regra de
negócio pode ser testada e reaproveitada sem a API.

## Criando uma funcionalidade nova

Exemplo: "favoritar perfis".

1. **Banco:** `make migracao nome=favoritos` cria `db/migrations/0007_favoritos.sql`.
   Escreva o SQL ali. **Nunca edite uma migração que já foi para a `main`**: crie outra.
   Use `ON DELETE CASCADE` para tudo que pertence a uma conta, porque excluir a conta precisa apagar tudo.
2. **Domínio:** crie `app/favoritos.py` com funções `async def ...(con, ...)` contendo o SQL
   e as regras. Parâmetros sempre com `$1, $2...`, nunca com texto do usuário na string SQL.
3. **Contratos:** adicione os modelos em `app/schemas.py`, num bloco `# ---------- favoritos ----------`.
4. **Rotas:** crie `app/routes/favoritos.py` com `router = APIRouter(tags=["favoritos"])` e
   registre o módulo na tupla de `criar_app()` em `app/main.py`.
5. **Testes:** crie `tests/test_favoritos.py` usando a fixture `pessoa` (veja os testes existentes).
   Teste o caminho feliz **e** as proteções (bloqueio, conta em revisão, outra pessoa tentando acessar).
6. `make verificar` e abra o PR.

### Checklist de privacidade (vale para todo PR)

- [ ] Não grava nada que identifique a pessoa fora do app (e-mail, telefone, IP, coordenada exata, EXIF).
- [ ] Respeita bloqueios nas duas direções e esconde contas `em_revisao`/`banida` (use `exigir_perfil_visivel`).
- [ ] Ações que alcançam outra pessoa usam `conta_ativa` (e não só `conta_atual`).
- [ ] Conteúdo privado (mensagens, fotos, evidências) é cifrado com `Cifrador` e um contexto próprio.
- [ ] Rotas que podem ser abusadas têm `exigir_limite(...)`.
- [ ] Em erro de autorização, prefira 404 a 403 quando o 403 revelaria algo (ex.: "você foi bloqueado").
- [ ] Dados de outros usuários entram no front só via `textContent` (nunca `innerHTML`).

## Testes (obrigatórios)

Todo PR vem com testes, e o CI bloqueia o merge se a cobertura cair abaixo de 90%.

| Tipo | Arquivo | Quando usar |
|---|---|---|
| Unitário | `tests/test_unit_<módulo>.py` | Funções puras: algoritmo, validação, cifragem, geohash, cursor. Rodam em milissegundos e sem banco. |
| Ponta a ponta | `tests/test_<domínio>.py` | Fluxos pela API com PostgreSQL real, com fixtures `pessoa`, `conexao_entre` e `db`. |
| Regressão | `tests/test_unit_regressoes.py` | **Todo bug corrigido ganha um teste que reproduz o erro**, com o nome do problema. |
| Paridade | `tests/test_paridade.py` | Garante que o algoritmo em SQL e em Python dão o mesmo resultado. |

Para cada função nova, teste pelo menos:

- o caminho feliz;
- os limites: vazio, zero, máximo, exatamente no limite (ex.: quem faz 18 anos hoje);
- entradas inválidas ou maliciosas (formato errado, texto enorme, maiúsculas e espaços);
- a proteção: outra pessoa tentando acessar, bloqueio, conta em revisão.

`make testar` roda tudo com relatório de cobertura; `pytest tests/test_unit_*.py` roda só
os unitários (não precisa de banco).

## Algoritmo: Python e SQL precisam concordar

O ranking roda em SQL (`descoberta.py`) e os detalhes exibidos em Python (`matcher.py`).
Ao mudar pesos ou fórmulas, **mude os dois** e rode `tests/test_paridade.py`, que compara
os dois em perfis aleatórios.

## Estilo e revisão

- `ruff` cuida de formatação, ordem de imports, bugs comuns e regras de segurança
  (o pre-commit roda sozinho a cada commit). Não discuta estilo em revisão: o ruff decide.
- Nomes de domínio em português (`perfil`, `curtir`, `denuncia`), como no restante do código.
- Comentários explicam o **porquê** (principalmente decisões de privacidade), não o quê.
- Mensagens de commit no imperativo, curtas, explicando a mudança ("Adiciona favoritos").
- Todo PR passa pela pipeline (lint, testes, auditoria, build + smoke test da imagem).
  Merge na `main` dispara o deploy.

## Segurança

Encontrou uma falha? **Não abra issue pública.** Veja [SECURITY.md](SECURITY.md).
