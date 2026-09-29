# Plano de execução · Parte 7 — Moderação

## Painel web

Em **Conta → Moderação → Abrir painel**, visível só para quem tem o papel de moderador
(`make moderador apelido=...`). Para qualquer outra pessoa, a API responde 404: nem a existência
das rotas é revelada.

- **Fila:** casos graves primeiro (menor de idade, conteúdo ilegal), depois por volume.
- **Cada caso mostra:** o apelido, se a conta está oculta, o perfil público, as denúncias (motivo,
  detalhes, data) e as mensagens anexadas como evidência, quando houver.
- **Ações:**
  - **Restaurar** ou **Banir**, com a observação registrada em `moderacao_log` (quem, o quê,
    quando, por quê).
  - **Enviar aviso por e-mail:** o endereço nunca aparece para o moderador, e o envio fica
    registrado em `contatos_log`.

Captura: [docs/telas/13-moderacao.png](../telas/13-moderacao.png).

## Moderação automática (sem IA de terceiros)

O plano citava "moderação com IA". Mandar textos e fotos de um app adulto para um serviço de IA
externo expõe o conteúdo das pessoas a mais uma empresa. A escolha foi:

- **Regras locais**, no próprio servidor, sobre o conteúdo **público** do perfil (nome e bio).
  **Nunca** sobre mensagens privadas.
- **Foco no caso mais grave:** sinais de menor de idade (idade declarada entre 10 e 17 anos, "sou
  menor", "de menor", "ensino médio"...), com tratamento de negação ("nada de menor de idade aqui").
- **Precisão acima de tudo:** um falso positivo esconde uma pessoa inocente. Os testes têm uma
  lista de frases que **não podem** disparar ("3 anos de namoro", "moro aqui há 5 anos", "Leo,
  34"...).
- **Uma sinalização nunca bane:** cria uma **denúncia do sistema** (sem denunciante) e deixa a conta
  **em revisão** (oculta) até uma pessoa decidir. Salvar o perfil de novo não duplica a denúncia
  aberta.

### Próximos passos possíveis

- **Fotos:** detecção de nudez ou de menores exigiria um modelo de visão. Se for adotado, que rode
  no próprio servidor (modelo aberto) ou num provedor com contrato de operador (LGPD), e só sobre
  fotos denunciadas.
- **Novas regras:** golpes e spam (links repetidos, pedidos de dinheiro), sempre com uma lista de
  falsos positivos nos testes.
