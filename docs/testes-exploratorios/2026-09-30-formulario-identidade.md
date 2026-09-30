# 2026-09-30 · Formulário de identidade

- **Missão:** Explorar o protótipo `prototipos/formulario-identidade/index.html` com textos
  Unicode, só teclado, toque, telas estreitas e envio repetido, para descobrir se a validação do
  "Outro" pode ser burlada e se a página continua usável em qualquer tela.
- **Versão:** `develop` em 5b44588
- **Tempo:** sessão curta, assistida por scripts Playwright (as variações acima)
- **Ambiente:** Chromium (Playwright), 360×780, 320×640, 180×400 (zoom de 200% num celular),
  1280×800; tema claro e escuro; toque ligado.

## O que foi tentado

- "Outro" com: `ab`, `   ab   `, `abc`, `🙂🙂`, `👩🏽‍💻👩🏽‍💻`, `é` com acento combinante, `a` + dois
  espaços de largura zero + `b`, `a` + dois hífens suaves + `b`, três quebras de linha,
  `<img src=x onerror=alert(1)>`, 500 caracteres.
- Errar o "Outro", desmarcar, enviar; marcar de novo (o texto antigo volta e o erro some).
- Navegar só com Tab e Espaço; contar as paradas de Tab.
- Duplo clique em "Salvar".
- Abrir cada balão ⓘ pelo foco em 320, 180 e 1280 px e medir se a página rola na horizontal.
- Tocar no ⓘ no celular (tema escuro) e tocar fora.
- Ler a árvore de acessibilidade de uma categoria.

## Achados

| # | Tipo | O que acontece | Esperado | Situação |
|---|---|---|---|---|
| 1 | bug | `a` + 2 espaços de largura zero + `b` (e com hífen suave) passa no mínimo de 3: a pessoa vê "ab" | contar só o que se vê | corrigido: `limparOutro` remove caracteres de formatação invisíveis |
| 2 | bug | `🙂🙂` passa: o JS contava unidades UTF-16 (4), não caracteres (2) | contar caracteres como a pessoa vê | corrigido: `contarVisiveis` conta grafemas com `Intl.Segmenter` (👩🏽‍💻 conta 1) |
| 3 | bug | Com zoom de 200% (180 px) a página rola na horizontal: "Cisheteronormatividade" e outros nomes longos não quebram | nenhuma rolagem lateral (WCAG 1.4.10) | corrigido: `overflow-wrap: anywhere` no nome da opção |
| 4 | observação | Duplo clique em "Salvar" gera dois envios | um envio | aceito no protótipo (só `console.log`; o PUT previsto é idempotente). Ao ligar a API, desabilitar o botão durante o envio |
| 5 | observação | Cada ⓘ é uma parada de Tab: 68 paradas no formulário | menos esforço no teclado | aceito: é o que permite abrir a descrição pelo teclado e pelo toque. Reavaliar ao levar para o app (ex.: descrição sempre visível em `aria-describedby`) |

O que funcionou bem: texto com cara de HTML fica só texto (vai para o JSON sem ser interpretado);
`maxlength` segura 500 caracteres colados; desmarcar o "Outro" depois do erro libera o envio;
o balão abre com toque e fecha ao tocar fora; nenhum balão sai da tela em 320 e 1280 px; tema
escuro correto; cada caixa tem nome acessível próprio.

Durante a correção, os testes de mutação mostraram um ramo impossível em `ladoDaDica` (o balão
nunca estoura dos dois lados porque sua largura é limitada à da tela menos as margens); o ramo foi
removido.

## Viraram teste

- `tests/js/formulario_identidade.test.js` (22 unitários, no Node, sem navegador): integridade de
  `OPCOES`; `limparOutro` (NFC, invisíveis, emoji composto, corte em 200 sem partir emoji, HTML);
  `contarVisiveis`; `montarIdentidade` (vazio, ordem, ids desconhecidos e repetidos, limite exato de
  3, "Outro" desmarcado, várias categorias inválidas); `ladoDaDica` (limites exatos de 16 px e tela
  estreita).
- `tests/e2e/formulario_identidade.test.js`:
  - "regressão (teste exploratório): invisíveis e emojis não burlam o mínimo do 'Outro'";
  - "regressão (teste exploratório): com zoom de 200% (180 px) nada rola na horizontal".
  Os dois falham na versão anterior da página.

## Ideias para a próxima sessão

- Leitor de tela real (NVDA/VoiceOver) lendo o balão e o erro do "Outro".
- Quando o formulário for para o app: CSP, envio para a API, sessão expirada no meio, pânico (ESC)
  com o formulário preenchido.
