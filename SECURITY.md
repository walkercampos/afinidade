# Segurança

## Reportar uma vulnerabilidade

Não abra issue pública. Envie os detalhes em privado para a pessoa mantenedora do repositório
(GitHub → *Security* → *Report a vulnerability*, se habilitado). Respondemos em até 7 dias.

## Princípios

1. **Minimização:** o dado mais seguro é o que não existe. Sem e-mail, telefone, nome civil, foto, localização,
   data de nascimento ou IP gravados.
2. **Exclusão real:** apagar a conta remove as linhas do banco (sem *soft delete*) e invalida as sessões.
3. **Defesa em profundidade:** validação no Pydantic **e** `CHECK` no banco; filtro de compatibilidade no SQL
   **e** no Python; cookie `SameSite=Strict` **e** header anti-CSRF.
4. **Sem terceiros no navegador:** nenhum script, fonte, analytics ou pixel externo (garantido pela CSP).

## Checklist antes de produção

- [ ] `AMBIENTE=producao` (cookie `Secure`, HSTS, `/docs` desligado)
- [ ] `JWT_SECRET` aleatório de 48+ caracteres, só no painel do provedor (nunca no repositório)
- [ ] `DATABASE_URL` com `sslmode=require`
- [ ] Backups do banco habilitados e com acesso restrito
- [ ] 2FA ativado nas contas do GitHub, Render e Neon
- [ ] Revisão jurídica: LGPD (dados sensíveis), Marco Civil (art. 15) e verificação de idade
- [ ] Fluxo de denúncia e moderação

## Limitações conhecidas

- O rate limit é em memória: vale por instância e zera quando ela reinicia.
- Sem e-mail não há recuperação de senha — é uma escolha de privacidade, comunicada no cadastro.
- Tags e preferências precisam ficar em claro no banco para o filtro funcionar; a proteção delas é o
  controle de acesso ao banco, TLS e a criptografia em repouso do provedor.
