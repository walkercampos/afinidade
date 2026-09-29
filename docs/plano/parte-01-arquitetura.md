# Plano de execução · Parte 1 — Arquitetura

> Decisão tomada: **evoluir o app atual** (FastAPI + PostgreSQL + front web) em vez de reescrever na
> stack React Native / Node / Prisma / Socket.IO / Firebase. Este documento explica o porquê, mostra
> a arquitetura-alvo e define a ordem das partes 2 a 12.

## 1. Por que evoluir em vez de reescrever

| Critério | Reescrever (Node/RN/Prisma/Firebase) | Evoluir (atual) |
|---|---|---|
| Tempo até voltar ao nível de hoje | semanas | zero |
| Testes existentes (154 Python, 11 JS, 5 no navegador; cobertura 97,8%) | perdidos | mantidos |
| Custo | Firebase Storage e Socket.IO escalado saem do gratuito cedo | tudo cabe em plano gratuito |
| Segurança já auditada (passkeys, CSRF, CSP, cifra de e-mail, fotos e mensagens) | refazer e reauditar | mantida |
| App de celular | nativo desde o início | PWA agora; Expo depois consumindo **a mesma API** |

A stack pedida e a atual resolvem os mesmos problemas. A tabela mostra o equivalente de cada peça:

| Pedido no plano | Equivalente adotado | Observação |
|---|---|---|
| React Native + Expo | PWA (instalável, sem loja) → Expo na fase 2 | A API já é JSON; o app nativo entra sem mudar o back-end |
| Node.js + TypeScript + Express | Python 3.12 + FastAPI + Pydantic | Tipagem e validação na borda equivalentes |
| Prisma | SQL versionado em `db/migrations` + asyncpg | Consultas de matching dependem de `intarray` e índices GIN que ORM não gera bem |
| PostgreSQL + PostGIS | PostgreSQL + geohash de 5 caracteres (~5 km) | Mais privado: a coordenada exata nunca é gravada. PostGIS continua possível no Neon se um dia for preciso |
| Socket.IO | WebSocket nativo do FastAPI (Parte 6) com polling como reserva | Sem dependência extra; mesma autenticação por cookie |
| Neon | Neon | igual |
| Render | Render (Docker, plano gratuito) | igual |
| Resend | Resend (ou SMTP) | igual |
| Firebase Storage | Fotos cifradas no próprio PostgreSQL; Cloudflare R2 (10 GB grátis) quando crescer | Sem SDK de terceiros no cliente e sem rastreamento |

## 2. Arquitetura-alvo

```
Celular / navegador
  PWA (HTML + CSS + JS em módulos, sem build) ─── fase 2: app Expo usando a mesma API
    │  HTTPS · cookie HttpOnly SameSite=Strict + header X-CSRF (web) · Bearer (app nativo)
    │  WebSocket /ws (mensagens em tempo real; polling como reserva)
    ▼
FastAPI — contêiner sem estado no Render
  routes/            HTTP e WebSocket: validação, autenticação, rate limit
  domínio            matcher · descoberta · mensagens · fotos · moderacao · geo · cripto
                     + idade (P3) · encontros (P9) · moderacao_ia (P7)
  tarefas de fundo   expiração de mensagens · limpeza de desafios/códigos · alertas de encontro (P9)
    │                        │                             │
    ▼                        ▼                             ▼
PostgreSQL (Neon)     Provedor de idade (P3)         Resend (e-mails)
migrações SQL         devolve só "18+: sim/não"      só avisos transacionais
chaves fora do banco  nenhum documento guardado aqui
```

### Fronteiras de confiança

1. **Cliente → API:** nada vindo do cliente é confiável. Pydantic valida tudo; o servidor recalcula
   idade, distância e compatibilidade.
2. **API → banco:** o banco guarda só dados cifrados ou derivados (HMAC do e-mail, célula geohash,
   mensagens e fotos em AES-256-GCM). As chaves ficam apenas em variáveis de ambiente.
3. **API → terceiros:** só três saídas: provedor de idade (fluxo hospedado por ele, com resultado
   assinado), Resend (e-mail) e, na Parte 7, a moderação automática. Nenhum rastreador, analytics
   ou fonte externa no front (CSP `default-src 'self'`).

## 3. Regras inegociáveis e onde cada uma é garantida

| Regra | Como é garantida | Verificação |
|---|---|---|
| Nunca prometer 100% de anonimato | Textos falam em "discrição" e "dados mínimos"; a política lista o que é guardado | revisão de textos (Parte 10) |
| Nunca prometer ponta a ponta (E2EE) | Mensagens são "cifradas no servidor"; a doc explica que o servidor detém a chave | idem |
| Limites nunca expostos | Só o dono lê os próprios limites; ficam fora da similaridade, das respostas de erro e dos logs | teste de API + busca por `tags_limite` nos logs (Parte 12) |
| Verificação de idade obrigatória (ECA Digital, Lei 15.211/2025) | Conta sem verificação não entra na descoberta, não curte e não conversa | teste de autorização (Parte 3) |
| Consentimento LGPD explícito e destacado | Tela própria no cadastro, versão aceita gravada em `contas` | teste de cadastro (Parte 10) |
| Exclusão imediata da conta | `ON DELETE CASCADE` em tudo que pertence à conta | já existe e é testado |
| Expiração de mensagens configurável | `expira_em = lida_em + ttl`; não lidas não expiram; `NULL` = nunca | Parte 6 |
| Custo zero primeiro | Só planos gratuitos; qualquer serviço pago precisa de alternativa gratuita documentada | tabela de custos abaixo |
| Transparência | Página "O que guardamos" gerada da própria documentação | Parte 10 |
| Código, comentários e docs em pt-BR | Convenção do CONTRIBUTING | revisão de PR |

## 4. O que já existe e o que falta, parte por parte

| Parte | Tema | Já existe | Falta |
|---|---|---|---|
| 2 | Modelo de dados | 9 migrações; contas, perfis, curtidas, bloqueios, mensagens, fotos, denúncias, passkeys, e-mail cifrado | Colunas de verificação de idade, TTL por conexão, pedidos de troca de TTL, encontros, versão dos termos aceitos |
| 3 | Autenticação e idade | E-mail (código/link) + passkeys; sem senhas; declaração 18+ | **Verificação real de idade** (selfie + prova de vida; CPF só se o provedor exigir, sem guardar aqui) |
| 4 | Criptografia | AES-256-GCM (mensagens, fotos, e-mail), HMAC para busca, chaves por domínio | Rotação de chaves com versão no texto cifrado; documento de ameaças |
| 5 | Matching | 3 camadas no SQL, similaridade, distância, paridade com Python | Filtros de busca (faixa etária, só com foto, ativos na semana) |
| 6 | Mensagens | Chat cifrado, some 5 min após leitura, polling | **WebSocket**, **TTL configurável por conexão (padrão 24h) com acordo das duas pessoas** |
| 7 | Moderação | Denúncias, revisão automática, log, rotas e CLI | **Painel web**, moderação automática de fotos e textos |
| 8 | Segurança da aplicação | CSP, CSRF, cookies, rate limit, revogação de sessão, pip-audit | Rate limit compartilhado para várias réplicas; cabeçalhos revisados; checklist OWASP |
| 9 | Segurança física | Botão de pânico | **Compartilhar encontro** com contato de confiança, check-in e alerta; link para 190/180 |
| 10 | Onboarding e discrição | Tema discreto, pânico (ESC) | **Modo discrição** (nome e ícone neutros, bloqueio por biometria), termos e consentimento LGPD destacados |
| 11 | Infraestrutura | Docker, Render, Neon, CI/CD completo, Dependabot | Backups e restauração testada, monitoramento de erros sem dados pessoais |
| 12 | Testes | 97,8% de cobertura (mínimo 90%), E2E, execução diária | Subir o mínimo para **95%**; testes de regressão das regras inegociáveis |

## 5. Ordem de execução

Cada parte é entregue em uma branch `funcionalidade/parte-NN-*`, com testes, e integrada à `develop`
com CI verde. A `main` recebe versões estáveis.

1. **Parte 2** ✅ ([modelo de dados](parte-02-modelo-de-dados.md)) — migrações para tudo que as partes seguintes precisam (feito primeiro para não
   reabrir o esquema a cada parte).
2. **Parte 6** ✅ — TTL configurável e WebSocket (muda o comportamento visível mais importante).
3. **Parte 3** — verificação de idade (bloqueia a abertura ao público).
4. **Parte 10** — termos, consentimento LGPD e modo discrição (também bloqueia a abertura).
5. **Parte 9** — segurança física.
6. **Parte 7** — painel de moderação e moderação automática.
7. **Partes 4, 5, 8, 11** — reforços incrementais.
8. **Parte 12** — atravessa todas: cada parte já entra com seus testes; ao final o mínimo sobe para 95%.

## 6. Custos (plano gratuito)

| Serviço | Uso | Plano gratuito | Quando deixa de ser grátis |
|---|---|---|---|
| Render | API | 750 h/mês; hiberna sem uso | Tráfego contínuo → plano pago (~US$ 7/mês) |
| Neon | Banco | 0,5 GB | Muitas fotos → mover fotos para R2 |
| Resend | E-mail | 3.000/mês, 100/dia | Mais de 100 cadastros/dia |
| Cloudflare R2 | Fotos (futuro) | 10 GB, sem custo de saída | — |
| Provedor de idade | Parte 3 | **a confirmar** | Em geral cobram por verificação; comparar Unico, FlagCheck e Didit na Parte 3 |
| GitHub Actions | CI/CD | Ilimitado em repositório público | — |

A verificação de idade é o único item que provavelmente terá custo por uso. A Parte 3 compara os
provedores e define uma interface (`app/idade.py`) para trocar de provedor sem mudar o resto.

## 7. Riscos e perguntas em aberto

- **Provedor de idade:** preço, se exige CPF, e se devolve apenas o resultado (sem imagem nem
  documento). Critério: não guardar nada além de `idade_verificada_em` e do provedor usado.
- **Moderação automática (Parte 7):** analisar fotos e textos fora do servidor expõe conteúdo a
  terceiros. Preferir modelo local leve ou só ativar sobre conteúdo denunciado.
- **WebSocket no Render gratuito:** a conexão cai quando o serviço hiberna; o cliente reconecta e
  usa polling enquanto isso.
- **App nativo:** passkeys no Expo exigem configuração de domínio associado (iOS/Android); fica para
  a fase 2.
