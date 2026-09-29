# Plano de execução · Parte 3 — Verificação de idade

Exigência do ECA Digital (Lei 15.211/2025) para serviços com conteúdo adulto: confirmar a idade de
verdade, não só com "tenho 18 anos".

## Como funciona para quem usa

1. Cria a conta (e-mail) e monta o perfil normalmente.
2. Ao tentar descobrir, ver perfis, curtir ou conversar, o app leva para **Confirme sua idade**.
3. A pessoa faz a verificação numa empresa especializada (selfie com prova de vida; CPF só se a
   empresa exigir) e volta ao app.
4. Até verificar, o perfil **não aparece para ninguém**.

## O que fica guardado (e o que não fica)

| Guardado | Nunca guardado |
|---|---|
| `contas.idade_verificada_em` e `contas.idade_provedor` | Selfie, vídeo, documento, CPF, data de nascimento |
| Tentativas (`verificacoes_idade`): situação e horários; o id da sessão do provedor só como HMAC | O id da sessão em claro |

As tentativas são apagadas depois de 30 dias. Um teste garante que o banco não tem colunas de
documento, CPF, selfie ou nascimento.

## Regras no código

- `security.conta_liberada`: conta ativa **e**, se a verificação for obrigatória, idade verificada.
  Vale para Descobrir, Afins, ver perfil, fotos de outras pessoas, pedir acesso às fotos, curtir e
  enviar mensagem. Criar e editar o próprio perfil continua liberado.
- `repository.conta_visivel`: contas sem idade verificada não aparecem na descoberta nem em
  `/perfis/{id}`.
- Descobrir confere o **perfil antes da idade**: quem acabou de chegar monta o perfil primeiro.
- Uma tentativa vale por 1 hora; uma nova tentativa invalida a anterior; até 5 tentativas por dia.

## Configuração

| Variável | Padrão | O que faz |
|---|---|---|
| `IDADE_OBRIGATORIA` | `true` em produção, `false` fora dela | Exige a verificação para descobrir, curtir e conversar |
| `IDADE_PROVEDOR` | `desativado` em produção, `simulado` fora dela | Quem verifica |

**O app não sobe fingindo que verifica:**
- em produção, `IDADE_OBRIGATORIA=true` com `IDADE_PROVEDOR=desativado` impede a inicialização,
  com uma mensagem explicando o que fazer;
- `simulado` nunca é aceito em produção.

Enquanto nenhum provedor real estiver contratado, o `render.yaml` sobe com
`IDADE_OBRIGATORIA=false`. Isso serve **só para uma fase fechada de testes**: o app não pode abrir
ao público assim.

## Provedor simulado (desenvolvimento e testes)

`IDADE_PROVEDOR=simulado` troca a empresa verificadora por uma tela do próprio app com os botões
**Aprovar** e **Recusar**. A rota que ela usa (`POST /api/idade/simulado/{sessao}`) só existe fora
de produção, e só a dona da tentativa consegue concluí-la. Os testes no navegador da pipeline
rodam com a verificação obrigatória e passam por esse fluxo.

## Plugar um provedor real

Candidatos citados no plano: **Unico**, **FlagCheck**, **Didit**. Critérios para escolher:

1. Devolve só o resultado (maior de idade: sim/não), sem precisar mandar imagem ou documento
   para cá.
2. Webhook de resultado **assinado** (HMAC ou similar).
3. Preço por verificação e se há cota gratuita.
4. Conformidade com a LGPD (contrato de operador, onde os dados ficam, por quanto tempo).

Para integrar (em `app/idade.py`):

1. Uma classe com `nome` e `async def iniciar(self, sessao) -> url`, que cria a sessão na API do
   provedor usando `sessao` como referência e devolve a URL para onde a pessoa vai.
2. Registrar a classe em `PROVEDORES`.
3. Uma rota de retorno (webhook) que **confere a assinatura** do provedor e chama
   `idade.concluir(con, sessao, aprovada)`. Sem assinatura válida, responde 401 e não grava nada.
4. Testes com uma assinatura válida e com uma inválida.
5. Chave de API e segredo do webhook em variáveis de ambiente, nunca no código.
