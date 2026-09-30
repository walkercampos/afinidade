# Registro de mudanças

Todas as mudanças relevantes do Afinidade ficam registradas aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/):

- **MAIOR** (1.0.0 → 2.0.0): muda algo que quebra o app antigo ou a API.
- **MENOR** (0.4.0 → 0.5.0): funcionalidade nova, sem quebrar nada.
- **CORREÇÃO** (0.4.0 → 0.4.1): só correções.

Como lançar uma versão: veja [docs/operacao.md](docs/operacao.md#lançar-uma-versão).

## [Não lançado]

### Adicionado
- Protótipo do formulário de identidade (orientação, gênero e características), autocontido em
  `prototipos/formulario-identidade/index.html`, no sistema visual do app, com testes no navegador.
- Regra de testes: tudo que é novo entra com teste unitário e uma sessão de teste exploratório
  registrada em `docs/testes-exploratorios/` (método, heurísticas do projeto e modelo).
- 22 testes unitários da lógica do formulário de identidade, rodando no Node sem navegador.

### Corrigido
- Formulário de identidade: o mínimo de 3 caracteres do "Outro" podia ser burlado com caracteres
  invisíveis (`a` + espaço de largura zero + `b`) ou com emojis (`🙂🙂` contava 4). Agora conta só o
  que se vê, e o texto enviado sai sem invisíveis.
- Formulário de identidade: com zoom de 200% no celular, nomes longos criavam rolagem lateral.

## [0.5.0] - 2026-09-29

### Adicionado
- Parte 2 do plano (modelo de dados): colunas e tabelas para verificação de idade, prazo das
  mensagens por conversa (com proposta e confirmação), encontros com contato de confiança,
  versão dos termos aceitos e modo discrição. Só acrescenta; o comportamento atual não muda.
- Teste que impede qualquer tabela nova de "prender" uma conta excluída.
- Partes 4, 5, 8 e 12 do plano: rotação de chaves de cifragem com recifragem
  (`python -m app.admin recifrar`); filtros "só com foto" e "ativos esta semana" na descoberta;
  revisão OWASP Top 10 (`docs/seguranca-owasp.md`) e `/.well-known/security.txt`; cobertura
  mínima de testes sobe para 95%.
- Parte 6 do plano: prazo das mensagens combinado por conversa (de 5 minutos a 6 meses, ou
  nunca). Uma pessoa propõe, a outra confirma, e o novo prazo vale só para as mensagens enviadas
  depois. Mensagem não lida não expira.
- Avisos em tempo real por WebSocket (nova mensagem, mensagem lida, proposta de prazo), sem
  nenhum conteúdo no aviso.

- Parte 3 do plano: verificação de idade. Sem idade verificada (quando obrigatória), não se
  descobre, curte nem conversa, e o perfil não aparece para ninguém. Só o resultado é guardado;
  nenhuma foto, documento ou CPF. Provedor simulado para desenvolvimento e testes; em produção o
  app não sobe com a verificação obrigatória e sem provedor real.

- Parte 10 do plano: termos de uso e política de privacidade versionados, com aceite explícito
  no cadastro e novo aceite quando mudarem; modo discreto ("Notas", ícone neutro, inclusive na
  tela inicial e depois do botão de pânico); tema claro, escuro ou automático.
- Teste de contrato: toda chamada do front existe na API com o mesmo método.
- Parte 9 do plano: encontro seguro. Registro cifrado de onde, quando e com quem; aviso ao contato
  de confiança; alerta por e-mail se o check-in não vier; atalhos para 190 e 180.
- Parte 7 do plano: painel web de moderação (fila, evidências, banir, restaurar e aviso por
  e-mail) e moderação automática local do conteúdo público dos perfis, com foco em sinais de
  menor de idade e testes de falsos positivos.

### Mudado
- Visual novo, no padrão dos apps mais usados no mundo: fonte do próprio aparelho, temas claro e
  escuro que seguem o celular, cartões limpos, botões em pílula, chips de interesses e barra de
  abas com ícones. Sai a identidade "Véu Luminoso" e a fonte serifada baixada pelo app.
- O prazo padrão das mensagens passa de 5 minutos para **24 horas depois de lidas**. Mensagens
  já enviadas mantêm os 5 minutos.

### Removido
- `MENSAGENS_RETENCAO_DIAS`: mensagens não lidas não são mais apagadas por tempo (regra do plano).

## [0.4.0] - 2026-09-29

### Adicionado
- Distância máxima escolhida numa barra deslizante (5 a 500 km ou qualquer distância); mexer na
  barra envia só o raio, nunca coordenadas.
- Teste automático do ataque de trilateração e do limite de trocas de localização.
- Aviso "Você viu todo mundo por enquanto" no fim do Descobrir.
- Id de requisição (`X-Request-ID`) em todas as respostas e no corpo dos erros 500.
- Logs estruturados em JSON em produção, sem IP, conta, e-mail ou ids de perfil.
- Versão do app em `/api/saude` (`lancamento`).
- Análise de segurança do código (CodeQL), modelos de issue e de pull request, CODEOWNERS,
  lançamento de versões pelo botão "Run workflow" (ou por tag) e guia de operação.
- Documentação: plano de execução (Parte 1), telas do app e localização.

### Corrigido
- `.env.example`: aspas no `EMAIL_REMETENTE` (o `make rodar` quebrava).

## [0.3.0] - 2026-09-28

### Adicionado
- Cadastro por e-mail (código de 6 dígitos ou link) e login por biometria (passkeys). Sem senhas.
- E-mail guardado criptografado, com aviso à pessoa sem expor o endereço.
- Identidade visual "Véu Luminoso".

### Removido
- Login por senha.

## [0.2.0] - 2026-09-28

### Adicionado
- Front-end web, botão de pânico (ESC), fotos borradas com pedido de acesso e chat que some
  5 minutos depois de lido.
- Denúncias e moderação, localização aproximada (~5 km), ranking e paginação no banco.
- Testes unitários, de regressão e no navegador; lint; pipeline de CI/CD.

## [0.1.0] - 2026-09-28

### Adicionado
- API de matchmaking (FastAPI + PostgreSQL) com o algoritmo de três camadas: gênero, limites
  absolutos e afinidade ponderada.

[Não lançado]: https://github.com/walkercampos/afinidade/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/walkercampos/afinidade/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/walkercampos/afinidade/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/walkercampos/afinidade/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/walkercampos/afinidade/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/walkercampos/afinidade/releases/tag/v0.1.0
