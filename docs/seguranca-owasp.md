# Revisão de segurança · OWASP Top 10 (2021)

Parte 8 do plano. Para cada categoria do [OWASP Top 10](https://owasp.org/Top10/): o que o
Afinidade faz, onde está no código e como é testado. Revisar a cada funcionalidade nova.

| # | Risco | Como o Afinidade se protege | Onde / teste |
|---|---|---|---|
| A01 | **Controle de acesso quebrado** | Toda rota exige sessão; ações sobre outra pessoa conferem conexão, bloqueio e visibilidade no SQL; moderação responde 404 a quem não é moderador; encontros e fotos só pelo dono | `security.py`, `deps.py`; `test_api`, `test_moderacao`, `test_encontros`, `test_fotos` |
| A02 | **Falhas criptográficas** | AES-256-GCM com contexto (AAD) por registro e chaves por domínio, fora do banco; HMAC para busca de e-mail; HTTPS + HSTS; cookie `Secure`; rotação de chaves com recifragem | `cripto.py`, `rotacao.py`; `test_rotacao`, `test_chat` |
| A03 | **Injeção** | SQL sempre parametrizado (asyncpg `$1`); o front só insere texto (nunca HTML); CSP estrita sem scripts inline | `dom.js`; `test_api` (HTML literal no chat), CodeQL |
| A04 | **Design inseguro** | Privacidade por construção: coordenada exata nunca gravada, limites invisíveis, mensagens que expiram, dados mínimos; ameaças documentadas | `docs/localizacao.md`; `test_localizacao` (trilateração) |
| A05 | **Configuração insegura** | `/docs` desligado em produção; cabeçalhos de segurança em tudo; o app **não sobe** com configuração perigosa (idade obrigatória sem provedor, provedor simulado em produção, e-mail de desenvolvimento) | `main.py`, `idade.py`, `config.py`; pipeline (contêiner) |
| A06 | **Componentes vulneráveis** | Versões fixas; `pip-audit` a cada push e todo dia; Dependabot semanal; CodeQL | `.github/workflows/` |
| A07 | **Falhas de autenticação** | Sem senha: código por e-mail (uso único, 15 min, 5 tentativas) e passkeys (verificação de usuário obrigatória, detecção de clone); rate limit; revogação de todas as sessões | `verificacao.py`, `passkeys.py`; `test_email`, `test_passkeys` |
| A08 | **Integridade de software e dados** | Deploy só pela pipeline depois de todos os testes; migrações versionadas; imagens e ações de CI com versão fixa | `ci.yml`, `db/migrations/` |
| A09 | **Falhas de log e monitoramento** | Logs estruturados com id de requisição, **sem dados pessoais** (teste garante); erros 500 rastreáveis pelo código mostrado à pessoa; `moderacao_log` e `contatos_log` | `observabilidade.py`; `test_observabilidade` |
| A10 | **SSRF** | O servidor não busca URLs informadas por usuários; as únicas saídas são para serviços fixos (Resend, provedor de idade) | revisão de código |

## Além do Top 10

- **CSRF:** cookie `SameSite=Strict` + cabeçalho `X-CSRF` obrigatório em mudanças; WebSocket
  confere a origem.
- **Enumeração de contas:** respostas idênticas no cadastro e no login por e-mail.
- **Abuso:** rate limit por conta e por IP (com HMAC, sem guardar IP); limite de trocas de
  localização, denúncias, propostas de prazo, verificações de idade e encontros.
- **Relato de falhas:** [`/.well-known/security.txt`](../static/.well-known/security.txt) e
  [SECURITY.md](../SECURITY.md).

## Pendências conhecidas

- Rate limit em memória: com mais de uma réplica, trocar por um compartilhado (Redis ou o proxy).
- Revisão por terceiros (pentest) antes de abrir ao público.
