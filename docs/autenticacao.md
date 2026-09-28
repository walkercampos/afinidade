# Acesso: e-mail para criar a conta, biometria para entrar

Não existe senha. A conta nasce com o **e-mail** (código de 6 dígitos ou link de uso único), e
depois a pessoa ativa a **biometria** (passkey: digital, rosto ou PIN) para os próximos acessos. O e-mail
continua servindo para entrar em um aparelho novo ou recuperar a conta.

```
Criar conta                                   Dia a dia                     Aparelho novo / perdeu o celular
───────────                                   ─────────                     ────────────────────────────────
e-mail + 18+ + consentimento                  "Entrar com biometria"        "Receber código por e-mail"
   → código de 6 dígitos (ou link) por e-mail    → digital / rosto / PIN       → código → entra
   → confirma → conta criada                     → entra                       → ativa a biometria de novo
   → "Ativar biometria" (passkey)
```

## Privacidade do e-mail

| O quê | Como |
|---|---|
| E-mail no banco | **nunca em texto**. Duas formas, cada uma com sua chave fora do banco: `HMAC-SHA256(EMAIL_PEPPER, e-mail)` para **achar** a conta, e o e-mail **cifrado** com AES-256-GCM (`CHAVE_EMAIL`) para o app poder **falar** com a pessoa. Com só o banco vazado, nenhum e-mail aparece. |
| Enviar o código | usa o endereço que a pessoa acabou de digitar |
| Falar com a pessoa | o e-mail só é decifrado na hora do envio, dentro do servidor. Moderadores enviam avisos **sem ver o endereço**, e todo envio fica em `contatos_log` (quem, quando, assunto; o corpo não é guardado). |
| A própria pessoa | vê o e-mail mascarado em *Conta* (`j****@gmail.com`) |
| Código e link | também só em hash; uso único; valem 15 min; um pedido novo invalida o anterior |
| Descobrir quem tem conta | impossível pela API: "entrar" e "criar conta" respondem igual, e o envio acontece depois da resposta (o tempo de resposta também não denuncia) |
| Texto do e-mail | neutro ("Seu código de acesso"), sem o nome do app, porque aparece na tela de bloqueio |
| Outras pessoas | nunca veem o e-mail; o perfil mostra só o apelido |
| Força bruta no código | até 5 tentativas por código; até 5 e-mails por hora por endereço; limite por IP |
| Link | o token vai no fragmento (`#/verificar/...`), que o navegador não envia a servidores nem em `Referer`, e sai do histórico assim que é usado |

O que o app **não** consegue esconder: o provedor de e-mail (ex.: Resend) vê o destinatário e o
código. Por isso a tela de cadastro sugere usar um e-mail só para isso ou um alias (Ocultar meu
e-mail do iCloud, Firefox Relay).

### Como falar com a pessoa

- **Pela linha de comando** (quem administra o servidor):
  `python -m app.admin avisar <apelido> "<assunto>" "<mensagem>"`
- **Pela moderação** (API, só moderadores): `POST /api/moderacao/contas/{id}/aviso`
  com `{"assunto": "...", "mensagem": "..."}`.

Nos dois casos o endereço não é mostrado a ninguém, o texto segue o mesmo tom neutro, e o envio é
registrado. Pela LGPD, o uso do e-mail é informado no cadastro: acesso, recuperação e avisos sobre a
conta. **Propaganda ou newsletter exigiriam um consentimento separado**, que o app não pede.

## Biometria (passkeys)

- A **chave privada nunca sai do aparelho**, e a digital ou o rosto nunca chegam ao app. O servidor
  guarda só a chave pública, que não serve para entrar em conta nenhuma.
- **Resistente a phishing:** a assinatura só vale para o domínio verdadeiro do app.
- Exigimos **passkey descobrível** (entra sem digitar nada) e **verificação do usuário** (biometria ou PIN).
- **Desafios de uso único no banco**, contador contra autenticador clonado e `user.id` aleatório (não o id da conta).
- A pessoa pode ter várias (celular, computador) e remover qualquer uma; o e-mail sempre permite voltar.

Arquivos: `app/verificacao.py`, `app/contato.py`, `app/email.py` e `app/routes/auth.py` (e-mail); `app/passkeys.py` e
`app/routes/passkeys.py` (biometria); migrações `0007_passkeys.sql` e `0008_email.sql`; no front,
`telas/entrar.js`, `telas/biometria.js`, `telas/verificar.js` e `telas/conta.js`.

## 1. Configuração

### E-mail (custo zero com o Resend)

1. Crie uma conta em [resend.com](https://resend.com). O plano gratuito cobre um MVP; confira os limites atuais.
2. **Domains → Add Domain**: adicione seu domínio e crie os registros DNS indicados (SPF/DKIM).
   Sem domínio próprio, o Resend só envia para o seu próprio e-mail, o que serve para testes.
3. **API Keys → Create API Key** com permissão **Sending access** (só envio, o mínimo necessário).
4. No Render (*seu serviço → Environment*):
   - `EMAIL_PROVEDOR=resend` (o `render.yaml` já define)
   - `RESEND_API_KEY=re_...`
   - `EMAIL_REMETENTE=Afinidade <nao-responda@seudominio.com>`
   - `EMAIL_PEPPER` e `CHAVE_EMAIL`: o `render.yaml` gera as duas sozinho. **Nunca troque depois de
     ter usuários** e guarde um backup seguro (ver tabela no item 4).

Alternativa: `EMAIL_PROVEDOR=smtp` com `SMTP_HOST`, `SMTP_PORTA` (587), `SMTP_USUARIO` e `SMTP_SENHA`,
por exemplo com Brevo, Mailgun ou o SMTP do seu provedor. A conexão exige TLS.

### Biometria

| Variável | Exemplo em produção |
|---|---|
| `WEBAUTHN_RP_ID` | `afinidade.onrender.com` (só o domínio) |
| `WEBAUTHN_ORIGENS` | `https://afinidade.onrender.com` (a origem exata) |

Passkeys só funcionam em HTTPS (ou em `localhost`). Elas ficam presas ao domínio: escolha o
**definitivo** cedo, porque trocar depois invalida as passkeys existentes. Nesse caso as pessoas
entram por e-mail e ativam de novo.

**Em produção, o app se recusa a subir** sem essas variáveis, sem `EMAIL_PEPPER` ou com um provedor
de e-mail de desenvolvimento. É melhor falhar na hora do que funcionar pela metade.

### Desenvolvimento

Com o `.env.example`, os e-mails viram arquivos `.txt` na pasta `emails-dev/`: abra o mais recente
para ver o código ou clicar no link. As passkeys funcionam em `http://localhost:8000`.

## 2. Instalação

```bash
pip install -r requirements.txt            # inclui webauthn (py_webauthn); o e-mail usa só a biblioteca padrão
pip install -r requirements-dev.txt        # testes, lint, auditoria
npm ci && npx playwright install chromium  # só para os testes no navegador
```

As migrações rodam sozinhas na próxima inicialização (`python -m app.admin migrar` para rodar à mão).

## 3. Testes

| Arquivo | O que cobre |
|---|---|
| `tests/test_email.py` | e-mail nunca em texto no banco, respostas iguais com ou sem conta, cadastro com e-mail existente, normalização, limite de tentativas, uso único, expiração, pedido novo invalidando o anterior, link mágico, texto discreto, limite de envios, disputa de apelido |
| `tests/test_contato.py` | e-mail cifrado, aviso da moderação sem revelar o endereço, só moderadores, linha de comando, registro em `contatos_log`, separação de chaves |
| `tests/test_unit_email.py` | cada carteiro (arquivo, Resend, SMTP com TLS obrigatório), falhas de envio e as travas de configuração |
| `tests/test_passkeys.py` | biometria com criptografia real (autenticador de software): phishing, replay, clone, chave errada, falta de verificação, desafio de outra conta, banimento, exclusão |
| `tests/e2e/fluxo.test.js` | no navegador: cadastro pelo e-mail lendo o código da "caixa de entrada", ativação da biometria com o autenticador virtual do Chrome, sair e entrar só com a digital, e o link do e-mail |

## 4. Boas práticas com o `.env` e os segredos

1. **O `.env` nunca vai para o Git** (está no `.gitignore` e no `.dockerignore`); só o `.env.example`,
   com valores falsos. A pasta `emails-dev/` também é ignorada.
2. **Produção:** segredos só no painel do Render; na pipeline, em *GitHub → Settings → Environments*.
3. **Segredos fortes:** `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. **Um conjunto por ambiente** (dev, testes, produção). Nunca reaproveite o de produção.
5. **Chave do Resend com o mínimo de permissão** ("Sending access"), e troque-a se vazar (pode ser trocada sem efeito colateral).
6. **Saiba o que cada troca causa:**

| Segredo | Se trocar |
|---|---|
| `JWT_SECRET` | todo mundo é deslogado (seguro; faça isso se suspeitar de vazamento) |
| `RESEND_API_KEY` / `SMTP_SENHA` | nada; só atualize no painel |
| `EMAIL_PEPPER` | ninguém é mais encontrado pelo e-mail. **Faça backup e não troque.** |
| `CHAVE_EMAIL` | o app não consegue mais mandar avisos (o acesso por e-mail continua funcionando). **Faça backup e não troque.** |
| `CHAVE_MENSAGENS` | mensagens e fotos existentes ficam ilegíveis. **Faça backup e não troque.** |
| `WEBAUTHN_RP_ID` | as passkeys param de funcionar; as pessoas reativam após entrar por e-mail |

7. **Nada secreto no front-end:** tudo em `static/` é público.
8. **Proteções automáticas:** o pre-commit barra chaves privadas; ative também *Secret scanning* e
   *Push protection* no GitHub (grátis em repositórios públicos).
