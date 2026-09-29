# Operação

Guia para quem mantém o Afinidade no ar: publicar, voltar atrás, investigar erros e atender
pedidos de dados.

## Fluxo de branches

```
funcionalidade/*  ─┐
correcao/*        ─┼─▶ develop ──(pull request)──▶ main ──▶ deploy automático no Render
                   │
tag vX.Y.Z na main ────────────────────────────────────────▶ Release no GitHub
```

- Todo trabalho nasce numa branch `funcionalidade/...` ou `correcao/...` a partir da `develop`.
- A `main` só recebe pull requests vindos da `develop`, com a pipeline verde.
- Cada push na `main` publica no Render (se o secret `RENDER_DEPLOY_HOOK_URL` estiver cadastrado).

### Proteção da `main` (configurar uma vez no GitHub)

Settings → Branches → **Add branch ruleset** (ou "Add rule") para `main`:

1. **Require a pull request before merging**.
2. **Require status checks to pass**: marque `lint`, `testes`, `navegador`, `auditoria`, `imagem`
   e `analisar (python)` / `analisar (javascript-typescript)` (CodeQL).
3. **Block force pushes** e **Restrict deletions**.

Com isso ninguém, nem por engano, publica código que não passou nos testes.

## Lançar uma versão

1. Na `develop`, mova as entradas de "Não lançado" do `CHANGELOG.md` para uma seção nova
   `## [X.Y.Z] - AAAA-MM-DD` e atualize os links no fim do arquivo.
2. Troque `VERSAO` em `app/__init__.py`, `version` em `pyproject.toml` e o selo de versão no README (um teste garante que as
   duas batem e que o CHANGELOG tem a seção).
3. Abra o pull request `develop` → `main` e faça o merge com a pipeline verde.
4. No GitHub: **Actions → Lançamento → Run workflow**, com a branch `main` selecionada.
   (Alternativa pelo terminal: `git tag vX.Y.Z && git push origin vX.Y.Z`.)
5. O workflow confere a versão, cria a tag `vX.Y.Z` e o Release com as notas do CHANGELOG.
   Se o Release daquela versão já existir, ele para e avisa.

## Deploy e como voltar atrás

- **Deploy:** automático a cada push na `main`, só depois de todos os testes passarem. A pipeline
  espera a versão nova responder em `/api/saude` antes de dar como concluído.
- **Voltar atrás (rollback):** no painel do Render → serviço → **Events** → escolha o deploy
  anterior → **Rollback**. Leva menos de um minuto.
- **Migrações de banco** rodam sozinhas na subida do app e **não são desfeitas** no rollback. Por
  isso toda migração precisa funcionar também com a versão anterior do app (adicionar coluna ou
  tabela é seguro; renomear ou apagar exige duas versões: primeiro parar de usar, depois apagar).

## Investigar um erro

- Toda resposta tem o cabeçalho `X-Request-ID`, e todo erro 500 mostra um **código** para a pessoa.
- No Render → **Logs**, procure pelo código: a linha JSON do erro traz a rota, o status e o
  rastreamento completo.
- Os logs **não** têm IP, conta, e-mail, ids de perfil, parâmetros nem corpo das requisições. Se
  precisar de mais contexto, reproduza o problema; não acrescente dados pessoais ao log.

## Segredos

| Variável | Pode trocar? |
|---|---|
| `JWT_SECRET` | Sim. Todos precisam entrar de novo. Faça isso se suspeitar de vazamento. |
| `CHAVE_MENSAGENS` | **Não.** Mensagens e fotos antigas ficam ilegíveis. |
| `EMAIL_PEPPER` | **Não.** As pessoas deixam de ser encontradas pelo e-mail. |
| `CHAVE_EMAIL` | **Não.** Os e-mails guardados ficam ilegíveis. |

Guarde uma cópia das três chaves que não podem ser trocadas num cofre de senhas fora do Render.
Sem elas, um backup do banco não serve para nada (o que também é uma proteção).

## Backups

O Neon mantém histórico para restaurar o banco a um momento anterior (o prazo depende do plano;
confira no painel). Antes de qualquer migração arriscada, crie uma **branch** do banco no Neon: é
uma cópia instantânea para onde dá para voltar.

## Pedidos de titulares de dados (LGPD)

| Pedido | Como atender |
|---|---|
| Excluir os dados | A própria pessoa faz em Conta → Excluir tudo (apaga na hora, em cascata). |
| Saber o que guardamos | `docs/arquitetura.md` → "Privacidade por construção" lista cada dado. |
| Corrigir dados | A pessoa edita o próprio perfil a qualquer momento. |
| Contato com a pessoa | `python -m app.admin avisar <apelido> <assunto> <mensagem>` ou a rota de moderação; cada envio fica em `contatos_log`. |

## Incidente de segurança

1. Contenha: troque o `JWT_SECRET` (derruba todas as sessões) e, se for o caso, pause o serviço.
2. Descubra o alcance pelos logs (código da requisição, rota, horário).
3. A LGPD exige comunicar a ANPD e as pessoas afetadas em prazo curto quando houver risco
   relevante. Registre o que aconteceu, o que foi afetado e o que foi feito.
4. Corrija, adicione um teste de regressão e publique pela pipeline normal.
