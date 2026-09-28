# Segurança

## Reportar uma vulnerabilidade

**Não abra issue pública.** Use *Security → Report a vulnerability* no GitHub (reporte privado) ou fale
diretamente com a pessoa mantenedora. Respondemos em até 7 dias.

## Princípios

1. **Minimização:** o dado mais seguro é o que não existe. Não guardamos e-mail, telefone, nome civil,
   IP, coordenadas, data de nascimento nem metadados de fotos.
2. **Cifrado em repouso:** mensagens, fotos e evidências de denúncias são cifradas com AES-256-GCM. A chave
   fica fora do banco.
3. **Exclusão real:** apagar a conta remove tudo na hora (sem *soft delete*) e invalida as sessões.
4. **Defesa em profundidade:** validação na API **e** `CHECK` no banco; filtros no SQL **e** no Python;
   cookie `SameSite=Strict` **e** header anti-CSRF; blur gerado no servidor, não só no CSS.
5. **Sem terceiros no navegador:** nenhum script, fonte, CDN, analytics ou pixel externo (garantido pela CSP).

## O que está implementado

| Ameaça | Proteção |
|---|---|
| Roubo de sessão (XSS) | cookie HttpOnly; o front insere dados só como texto; CSP `script-src 'self'` |
| CSRF | `SameSite=Strict` + header `X-CSRF` obrigatório em escrita |
| Força bruta | scrypt; limite por IP (sem guardar o IP) e por apelido |
| Enumeração de apelidos | tempo de login constante (hash falso para apelido inexistente) |
| Sessão vazada ou conta banida | `token_versao`: sair, excluir ou banir invalida todos os tokens na hora |
| SQL injection | consultas 100% parametrizadas; nomes de tabela e coluna só de listas fixas |
| Vazamento do banco ou de backup | mensagens, fotos e evidências cifradas com chave fora do banco |
| Foto revelando localização | EXIF/GPS removidos; imagem recriada pixel a pixel |
| "Tirar o blur" pelo navegador | quem não tem acesso recebe do servidor só a versão borrada |
| Bomba de descompressão em imagens | limite de 5 MB e de 25 megapixels, checado antes de decodificar |
| Triangulação de localização | só a célula de ~5 km; distância em faixas; limite de trocas de localização por hora |
| Assédio | curtir só quem passa nos filtros; chat só entre conexões; bloqueio; denúncia |
| Denúncias falsas em massa | só contas com 24 h+ contam para ocultar automaticamente; moderador decide |
| Alguém chegando por trás | botão de pânico/ESC; `no-store` em tudo; navegação sem histórico |
| Dependência vulnerável | `pip-audit` em todo push e diariamente; Dependabot |
| Contêiner comprometido | usuário sem privilégios, sem cabeçalho `Server`, `/docs` desligado em produção |

## Checklist antes de produção

- [ ] `AMBIENTE=producao` (padrão)
- [ ] `JWT_SECRET` e `CHAVE_MENSAGENS` aleatórios, só no painel do provedor. **Faça backup seguro da
      `CHAVE_MENSAGENS`**: perdê-la torna mensagens e fotos ilegíveis.
- [ ] `DATABASE_URL` com `sslmode=require`
- [ ] 2FA nas contas do GitHub, Render e Neon; proteção da branch `main` exigindo a pipeline verde
- [ ] Pelo menos uma pessoa moderadora ativa
- [ ] Revisão jurídica: LGPD, Marco Civil (art. 15) e verificação de idade

## Limitações conhecidas

- O chat é cifrado no servidor, **não ponta a ponta**: quem controla o servidor poderia ler as mensagens
  durante os 5 minutos de vida delas.
- Linhas apagadas do PostgreSQL somem fisicamente só depois do *vacuum*; backups do provedor podem guardar
  cópias por um tempo. Por isso o conteúdo é cifrado.
- O rate limit é em memória: vale por instância e zera quando ela reinicia.
- Sem e-mail não há recuperação de senha (escolha de privacidade, avisada no cadastro).
- Tags precisam ficar em claro no banco para o filtro funcionar; a proteção delas é o controle de acesso ao banco.
