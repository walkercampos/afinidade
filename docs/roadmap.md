# Próximos passos

Lista priorizada usando o [pH7Builder](https://github.com/pH7Software/pH7-Social-Dating-CMS)
(CMS de namoro maduro, PHP, licença MIT) como **referência de funcionalidades**. O código dele não
foi copiado: cada item é reimplementado aqui, e só entra o que não enfraquece o anonimato.

## Prioridade alta (antes de abrir ao público)

| # | Funcionalidade | Por quê | Como fazer sem ferir a privacidade |
|---|---|---|---|
| 1 | **Painel web de moderação** | Hoje a moderação é só por API/linha de comando. | Tela `#/moderacao`, visível só para moderadores, usando as rotas que já existem. |
| 2 | **Notificações dentro do app** | Hoje ninguém sabe que tem conexão, mensagem ou pedido de foto novo sem abrir a tela. | Contadores via `GET /api/novidades` e bolinha no menu. Nada de e-mail ou push de terceiros. |
| 3 | **Verificação de idade real** | Exigência legal provável para conteúdo adulto (ECA Digital). | Provedor externo que devolve só "maior de idade: sim", sem documento guardado aqui. |
| 4 | **Termos de uso e política de privacidade** | LGPD e regras da comunidade (base para moderar). | Páginas estáticas + versão aceita registrada em `contas`. |

## Prioridade média

| # | Funcionalidade | Observação |
|---|---|---|
| 5 | Faixa etária opcional ("25–34") e filtro por idade | Só a faixa, nunca a data. |
| 6 | Filtros de busca (tags obrigatórias, só com foto, só ativos na semana) | Parâmetros extras em `/api/descobrir`. |
| 7 | Idiomas (pt, en, es) | O pH7 é multilíngue; aqui bastam arquivos de texto no front. |
| 8 | "Desfazer conexão" sem bloquear | Remove a curtida e apaga a conversa. |
| 9 | Catálogo de tags editável por moderadores | Hoje é pelo `seed.sql`. |
| 10 | Rate limit compartilhado (Redis gratuito) | Necessário ao rodar mais de uma instância. |

## Prioridade baixa / avaliar

- Grupos ou fóruns por interesse (o pH7 tem fóruns): exigiria moderação de conteúdo público.
- Chat em tempo real (WebSocket) no lugar do polling de 3 s.
- Criptografia ponta a ponta no chat (chaves no aparelho): proteção maior, mas sem recuperação de conversas e mais complexa.

## Do pH7 que NÃO vamos adotar

| Funcionalidade | Motivo |
|---|---|
| Cadastro por e-mail, newsletters | Identifica a pessoa fora do app. |
| Pagamentos, planos, créditos, anúncios, afiliados | O app é 100% gratuito; anúncios trazem rastreadores de terceiros. |
| "Quem visitou meu perfil" | Expõe o comportamento de quem só olhou. |
| Analytics de terceiros, botões de redes sociais | Rastreamento entre sites. |
| Vídeos | Custo de armazenamento incompatível com o plano gratuito e moderação difícil. |
