# Registro de mudanças

Todas as mudanças relevantes do Afinidade ficam registradas aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/):

- **MAIOR** (1.0.0 → 2.0.0): muda algo que quebra o app antigo ou a API.
- **MENOR** (0.4.0 → 0.5.0): funcionalidade nova, sem quebrar nada.
- **CORREÇÃO** (0.4.0 → 0.4.1): só correções.

Como lançar uma versão: veja [docs/operacao.md](docs/operacao.md#lançar-uma-versão).

## [Não lançado]

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

[Não lançado]: https://github.com/walkercampos/afinidade/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/walkercampos/afinidade/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/walkercampos/afinidade/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/walkercampos/afinidade/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/walkercampos/afinidade/releases/tag/v0.1.0
