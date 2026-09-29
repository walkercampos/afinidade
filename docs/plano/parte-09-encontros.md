# Plano de execução · Parte 9 — Segurança física

## Encontro seguro

Antes de encontrar alguém, a pessoa registra:
- **com quem** (uma conexão do app, ou "prefiro não dizer");
- **onde** e **quando começa**;
- **até quando** fará o check-in (até 24 h depois do início);
- o **e-mail de um contato de confiança** e como esse contato a conhece ("Ana, sua irmã").

| Momento | O que acontece |
|---|---|
| Ao registrar | O contato recebe um e-mail avisando que foi indicado e para quê, **sem** local nem horário |
| Toca em "Estou bem" | Encontro encerrado; nada é enviado |
| Passa do check-in sem confirmar | O contato recebe o local, o horário, com quem e as observações, mais os números 190 e 180 |
| Cancela | Nada é enviado |

A tela mostra sempre os atalhos **190 (Polícia)** e **180 (violência contra a mulher)**. Ela fica em
Conta → Encontro seguro e no botão "Encontro seguro" de cada conversa (com a conexão já escolhida).

## Privacidade e segurança

- Local, observações e o e-mail do contato ficam **cifrados** (AES-256-GCM, domínio próprio
  `afinidade/encontros/v1`, contexto amarrado ao id do encontro). Em claro, só os horários que a
  tarefa de fundo precisa.
- Só a própria pessoa vê e mexe nos encontros dela; a outra pessoa do encontro não fica sabendo.
- Se a outra pessoa excluir a conta, o registro de segurança continua (`SET NULL`); se quem
  registrou excluir, tudo vai junto.
- Registros são apagados **30 dias** depois do encontro. Limite de 10 encontros por dia.

## Como o alerta funciona

A tarefa de fundo (a cada 30 s) procura encontros agendados com o check-in vencido:
- **Uma vez só:** marca o encontro como `alerta_enviado` antes de enviar, com um UPDATE condicional,
  o que vale mesmo com duas réplicas rodando.
- **Falha isolada:** se um envio falhar, aquele encontro volta para `agendado` e tenta de novo no
  próximo ciclo, sem atrasar os alertas das outras pessoas.

**Limitação honesta:** o alerta depende do app estar no ar. No plano gratuito do Render, o serviço
"dorme" sem acesso e a tarefa de fundo só roda quando ele acorda. Antes de abrir ao público, use um
plano sem hibernação ou um agendador externo que acorde o serviço (ver
[operacao.md](../operacao.md)).
