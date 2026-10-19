# 2026-10-18 · Nova interface (web/)

- **Missão:** Explorar a nova interface em React (modo demonstração e contrato com a API) com
  celular de 360/390 px, computador, temas claro e escuro, para descobrir quebras de layout,
  telas que mostram dados velhos e chamadas que a API não conhece.
- **Versão:** branch `funcionalidade/nova-interface`
- **Tempo:** 90 minutos
- **Ambiente:** Chromium (Playwright), 360×780, 390×844 e 1280×800; tema do sistema claro e
  escuro; conta de demonstração (código 123456).

## O que foi tentado

- Todas as telas capturadas nos dois temas (entrar, criar conta, código, Descobrir, menu de
  segurança, É uma conexão, Conexões, chat, prazo, perfil, encontros, novo encontro, conta,
  moderação, termos, idade), conferindo o console e a rolagem lateral em cada uma.
- Trocar de aba (Entrar/Criar conta) e digitar logo em seguida.
- Curtir e pular pelos botões e arrastando o cartão; bloquear pelo menu do cartão.
- Propor, desistir e aceitar prazo no chat; apagar as próprias mensagens com a busca
  periódica rodando.
- Banir na moderação e voltar à fila.
- ESC e o botão vermelho em telas com e sem sessão; "voltar" do navegador depois do pânico.
- Contrato: as 54 chamadas da interface conferidas contra o OpenAPI da API.

## Achados

| # | Tipo | O que acontece | Esperado | Situação |
|---|---|---|---|---|
| 1 | bug | O brilho de fundo da tela de entrar criava rolagem lateral (534 px em tela de 390 px) | Sem rolagem lateral | corrigido: brilho recortado num contêiner fixo |
| 2 | bug | Apagar as minhas mensagens: às vezes elas voltavam por alguns segundos | Somem e não voltam | corrigido: o chat descarta respostas de buscas mais antigas que a última |
| 3 | bug | Depois de banir, a fila de moderação não atualizava (modo demonstração devolvia a mesma lista) | Caso sai da fila | corrigido: o modo demonstração devolve cópias, como a rede |
| 4 | bug | Botões de curtir/pular ficavam atrás da barra de abas em celulares baixos | Botões visíveis sem rolar | corrigido: altura do cartão acompanha a tela |
| 5 | bug | Campos de data do encontro cortados em 390 px | Data e hora inteiras | corrigido: um campo por linha no celular |
| 6 | observação | Categorias de interesses vêm do banco como slug (`restricao`, `sensacao`) | Nome com acento | corrigido: `nomeDaCategoria` |
| 7 | observação | Digitar no meio da animação de troca de aba vai para o formulário que está saindo | — | aceito: a troca leva 0,18 s, rápido demais para uma pessoa; os testes esperam a troca |

## Viraram teste

- `web/tests/e2e/demo.test.js`: 12 fluxos no navegador, cada um conferindo console e rolagem
  lateral (achados 1, 3, 5), o chat apagando sem as mensagens voltarem (achado 2) e o pânico.
- `web/tests/util.test.ts::nomeDaCategoria` (achado 6) e as funções de prazo e distância.
- `web/tests/e2e/api.test.js`: cadastro, idade, conexão, chat em tempo real e pânico com a API
  de verdade (roda no job `interface` do CI).
- `tests/test_contrato_front.py`: agora confere também as chamadas de `web/src`.

## Ideias para a próxima sessão

- Biometria com autenticador virtual do Chrome na nova interface.
- Leitor de tela (VoiceOver/TalkBack) nas folhas que sobem de baixo e no cartão arrastável.
- Servir `web/dist` pelo FastAPI em produção no lugar de `static/`.
