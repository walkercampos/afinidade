# Autenticação sem senha: passkeys

O Afinidade usa **passkeys (WebAuthn/FIDO2)** implementadas no próprio servidor. A senha continua
disponível como alternativa. Não há Magic Link por e-mail, Clerk nem Supabase, pelos motivos abaixo.

## Por que passkeys, e não Magic Link, Clerk ou Supabase

| | Passkeys no próprio servidor | Magic Link por e-mail | Clerk | Supabase Auth |
|---|---|---|---|---|
| Precisa de e-mail | **não** | sim | sim (ou telefone) | sim (ou telefone) |
| Resistente a phishing | **sim** (a assinatura só vale para o domínio certo) | não (o link pode ser encaminhado ou interceptado) | depende do método | depende do método |
| Terceiros veem seus usuários e IPs | **não** | provedor de e-mail | sim | sim |
| Carrega JavaScript de fora (quebra a CSP) | **não** | não | sim | não |
| Custo | **zero, sem limite** | envio de e-mails (cotas) | grátis até um limite | grátis até um limite |
| O que vaza se o banco vazar | **só chaves públicas: inútil para invadir** | nada útil | fora do seu controle | fora do seu controle |

Para um app cujo princípio é "não sabemos quem você é", pedir e-mail quebraria a promessa. As passkeys
são ao mesmo tempo o método **mais seguro** e o **mais anônimo**.

## Como funciona

```
Cadastro                                             Login
────────                                             ─────
navegador → POST /api/auth/passkey/registro/opcoes   navegador → POST /api/auth/passkey/login/opcoes
            (18+, consentimento, apelido opcional)   ← desafio aleatório (uso único, 5 min)
← desafio aleatório (uso único, 5 min)               aparelho: digital/rosto/PIN → assina o desafio
aparelho: digital/rosto/PIN → cria o par de chaves   navegador → POST /api/auth/passkey/login
navegador → POST /api/auth/passkey/registro          servidor confere a assinatura com a chave pública,
servidor confere e cria conta + passkey juntas       o domínio, o desafio e o contador → sessão
```

- A **chave privada nunca sai do aparelho**. O servidor guarda só a pública (`passkeys.chave_publica`).
- **Passkey descobrível:** o login não pede apelido; o aparelho mostra as passkeys que tem para o site.
- **Verificação do usuário obrigatória:** o aparelho sozinho não basta, precisa da digital, do rosto ou do PIN.
- **Desafios de uso único no banco** (`desafios_webauthn`): consumidos com `DELETE ... RETURNING`,
  funcionam com várias instâncias e impedem replay. Os expirados são limpos a cada 30 s.
- **Contador de assinaturas:** se não avançar, o login é recusado (sinal de autenticador clonado).
- `user.id` do WebAuthn é um valor aleatório (`contas.webauthn_id`), não o id da conta.
- Não é possível remover a última passkey de uma conta sem senha (a pessoa ficaria trancada para fora).

Arquivos: `app/passkeys.py` (regras + banco), `app/routes/passkeys.py` (API),
`db/migrations/0007_passkeys.sql`, `static/js/api.js` e `static/js/util.js` (navegador),
`static/js/telas/entrar.js` e `telas/conta.js` (telas).

## 1. Configuração (não existe painel)

Como tudo roda no seu servidor, não há painel nem chave de API. São só duas variáveis:

| Variável | O que é | Exemplo em produção |
|---|---|---|
| `WEBAUTHN_RP_ID` | o domínio do app, **sem** `https://` e sem porta | `afinidade.onrender.com` |
| `WEBAUTHN_ORIGENS` | a origem exata da barra do navegador (várias: separe por vírgula) | `https://afinidade.onrender.com` |

No **Render**, depois do primeiro deploy (quando você já sabe a URL):
*Dashboard → seu serviço → Environment → Add Environment Variable*, cadastre as duas acima e salve.
O Render reinicia o serviço sozinho. **Em produção, o app se recusa a subir sem elas**, de propósito:
é melhor falhar na hora do que ter passkeys quebradas ou aceitando qualquer origem.

Cuidados:

- Passkeys **só funcionam em HTTPS** (ou em `http://localhost` durante o desenvolvimento).
- As passkeys ficam presas ao `WEBAUTHN_RP_ID`. **Se você trocar de domínio** (ex.: de `onrender.com`
  para um domínio próprio), as passkeys antigas deixam de funcionar. Escolha o domínio definitivo cedo,
  ou peça às pessoas para adicionarem uma passkey nova antes da troca.
- Para usar em `app.dominio.com` **e** `dominio.com`, use `WEBAUTHN_RP_ID=dominio.com` e liste as duas origens.

Localmente, o `.env.example` já vem com `localhost` e `http://localhost:8000`.

## 2. Instalação

```bash
cd matchmaking
pip install -r requirements.txt        # inclui webauthn==3.0.1 (py_webauthn, Duo Security)
# desenvolvimento e testes:
pip install -r requirements-dev.txt
npm ci && npx playwright install chromium   # só para os testes no navegador
```

O banco é atualizado sozinho na próxima inicialização (migração `0007_passkeys`).
Para aplicar manualmente: `python -m app.admin migrar`.

## 3. Código e testes

| Camada | Testes |
|---|---|
| Criptografia e regras (`tests/test_passkeys.py`, 23 testes) | Um **autenticador de software** (`tests/autenticador.py`) gera chaves ES256 de verdade e assina como um celular. Cobre cadastro, login, replay, desafio expirado, phishing (outra origem ou outro domínio), chave errada, contador clonado, falta de verificação biométrica, respostas malformadas, adicionar e remover passkeys, conta banida e exclusão de conta. |
| Navegador (`tests/e2e/fluxo.test.js`) | O **autenticador virtual do Chrome** simula um celular com biometria: cria a conta só com passkey, sai e entra de novo. |
| Funções puras do front (`tests/js/util.test.js`) | Conversões base64url ↔ bytes e mensagens de erro. |

## 4. Boas práticas com o `.env` e os segredos

1. **O `.env` nunca vai para o Git.** Já está no `.gitignore` e no `.dockerignore`. Só o
   `.env.example`, com valores falsos, é versionado.
2. **Em produção, os segredos ficam no painel do provedor** (Render → Environment) e, na pipeline,
   em *GitHub → Settings → Environments → producao → Secrets*. Nunca em arquivos, commits,
   issues ou logs.
3. **Gere segredos fortes:** `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   O `render.yaml` já gera `JWT_SECRET` e `CHAVE_MENSAGENS` automaticamente.
4. **Um conjunto de segredos por ambiente** (dev, testes, produção). Nunca reaproveite o de produção.
5. **Saiba o que acontece ao trocar cada um:**
   - `JWT_SECRET`: todo mundo é deslogado (seguro; faça isso se suspeitar de vazamento);
   - `CHAVE_MENSAGENS`: mensagens e fotos existentes ficam ilegíveis. **Guarde um backup seguro**
     (ex.: no gerenciador de senhas da equipe) e não troque sem um plano de migração;
   - `WEBAUTHN_RP_ID`: as passkeys existentes param de funcionar (veja acima).
6. **Nada de segredo no front-end.** Tudo em `static/` é público. Este app não tem chave de API
   no navegador; se um dia tiver, só chaves feitas para serem públicas.
7. **Proteções automáticas já ligadas:** o hook `detect-private-key` do pre-commit barra chaves
   privadas no commit. Ative também *Secret scanning* e *Push protection* em *GitHub → Settings →
   Code security*, que são grátis para repositórios públicos.
8. **Menor privilégio no banco:** em produção, use um usuário do Postgres dono só do banco do app,
   nunca o superusuário do provedor.
