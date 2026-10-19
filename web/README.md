# Nova interface (web/)

Interface do Afinidade em React + TypeScript + Tailwind, com as mesmas telas e garantias do
front atual (`static/`): conta sem senha (e-mail + biometria), descoberta em cartões com fotos
protegidas, chat efêmero com prazo combinado, encontro seguro, moderação, modo discreto e o
botão de pânico (ESC) em todas as telas. Conversa com a mesma API (`/api`), no mesmo domínio:
a sessão continua num cookie HttpOnly com o header anti-CSRF, e nada é carregado de fora
(sem fontes, CDNs ou rastreadores), então a CSP estrita do back-end vale do mesmo jeito.

## Rodando

```bash
cd web
npm ci
npm run demo        # http://localhost:5173 com dados de exemplo, sem back-end (código: 123456)
npm run dev         # http://localhost:5173 ligado à API local (make rodar), via proxy em /api
npm run build       # gera web/dist
```

No `npm run dev`, inclua `http://localhost:5173` em `WEBAUTHN_ORIGENS` do `.env` para a
biometria e o canal em tempo real aceitarem a origem.

## Testes

```bash
npm test                                   # unitários (node --test)
npm run build:demo && npm run preview:demo # sobe o modo demonstração em :4173
WEB_URL=http://localhost:4173 npm run e2e:demo
```

O teste ligado à API (`npm run e2e:api`) precisa da API rodando com `EMAIL_PROVEDOR=arquivo` e
`IDADE_PROVEDOR=simulado`; o comando completo está no topo de `tests/e2e/api.test.js` e no job
`interface` do CI, que roda tudo isso em todo push. O teste de contrato
(`tests/test_contrato_front.py`) confere que toda chamada desta interface existe na API.

## Organização

```
src/lib/        cliente da API, rotas (#/tela), pânico, discrição, passkeys, tempo real, modo demo
src/componentes peças de interface (botões, cartões, folhas, avisos) e de perfil
src/telas/      uma tela por arquivo: Entrar, Descobrir, Conexões, Chat, Perfil, Encontros, Conta...
```

Cores e raios vêm dos tokens de `src/index.css`, os mesmos de
[docs/design/sistema-visual.md](../docs/design/sistema-visual.md), nos temas claro e escuro.
