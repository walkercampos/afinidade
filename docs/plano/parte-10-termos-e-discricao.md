# Plano de execução · Parte 10 — Termos, LGPD e discrição

## Termos de uso e política de privacidade

- Páginas públicas, sem login: [`/termos.html`](../../static/termos.html) e
  [`/privacidade.html`](../../static/privacidade.html). Linguagem simples e honesta: dizem o que é
  guardado, por quê, com quem é compartilhado e **o que não prometemos** (nada de anonimato
  absoluto nem criptografia de ponta a ponta).
- **Versão** = data da última mudança relevante (`app/termos.py`, `VERSAO_ATUAL`). As páginas
  levam a mesma data em `data-versao`; um teste confere que as três batem.
- **Aceite explícito no cadastro:** caixa "Li e aceito os termos de uso e a política de
  privacidade", separada do consentimento para dados sensíveis (LGPD, art. 11, I).
- **Mudou a versão:** todo mundo precisa aceitar de novo antes de ver perfis, curtir ou conversar.
  O próprio perfil, a conta e **excluir tudo** continuam acessíveis. A ordem de exigências é:
  conta ativa, termos aceitos e idade verificada.
- Guardamos só **qual versão** foi aceita e **quando** (`contas.termos_versao`,
  `contas.termos_aceitos_em`).

**Antes de abrir ao público:**
- Preencher o controlador e o contato do encarregado (DPO) na política de privacidade (está
  marcado como "[preencher antes de abrir ao público]").
- Fazer revisão jurídica dos dois textos.

## Modo discrição

Em Conta → Aparência e discrição:

- **Modo discreto:** o app aparece como **"Notas"** com um ícone neutro na aba do navegador, no
  histórico e na tela inicial (manifesto próprio para "Adicionar à tela inicial"). Fica gravado na
  conta (vale em todos os aparelhos) e também no aparelho, para valer desde a abertura, antes do
  login.
- **O botão de pânico apaga tudo, menos o modo discreto**: senão a próxima abertura mostraria o nome
  do app.
- **Tema:** Automático (segue o celular), Claro ou Escuro. Fica só no aparelho.
- Só é guardado no navegador o que difere do padrão: quem nunca mexeu não deixa rastro.

## Contrato front ↔ API

`tests/test_contrato_front.py` lê todas as chamadas `api(...)` e `fetch("/api/...")` do front e
confere, contra o OpenAPI da própria API, que cada rota existe **com o mesmo método**. É a ideia do
cliente gerado do full-stack-fastapi-template, adaptada a um front sem build. Conferi que o teste
falha quando uma rota é trocada.
