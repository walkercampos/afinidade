# Arquitetura

## Visão geral

```
Navegador (HTML + CSS + JS em módulos, sem build)
   │  mesmo domínio: cookie HttpOnly SameSite=Strict + header X-CSRF
   ▼
FastAPI (um contêiner, sem estado)
   ├── routes/*        HTTP: validação, status, autenticação
   ├── domínio         matcher · descoberta · mensagens · fotos · moderacao · geo · cripto
   └── tarefa de fundo limpeza das mensagens expiradas (a cada 30 s)
   │
   ▼
PostgreSQL (Neon)     migrações versionadas em db/migrations
```

A API não guarda estado em memória além do rate limit, então dá para rodar várias réplicas.
Com mais de uma réplica, troque o rate limit em memória por um compartilhado (ex.: Redis gratuito).

## O algoritmo

1. **Filtros rígidos:** eu busco o gênero da pessoa **e** ela busca o meu.
2. **Limites absolutos:** ninguém que QUER algo que é meu limite, nem que tem como limite algo que eu QUERO.
3. **Afinidade ponderada:** quero+quero = 3, quero+curioso = 2, curioso+curioso = 1, normalizado pelo
   máximo possível de cada lado. O feed usa o **score mútuo** (média dos dois lados).
4. **Similaridade** (cosseno; quero = 1, curioso = 0,5): quão parecidos são os gostos. Limites ficam de
   fora de propósito, senão daria para descobrir os limites de alguém variando o próprio perfil.
5. **Distância:** cada lado pode definir um máximo; vale o menor dos dois.

As camadas 1, 2 e 5 são `WHERE` com índices GIN; as camadas 3 e 4 são expressões com a extensão
`intarray` no `ORDER BY`, com paginação por cursor (`X-Proximo-Cursor`). `matcher.py` tem as mesmas
fórmulas em Python, e `tests/test_paridade.py` garante que os dois lados concordam.

Ordens disponíveis em `/api/descobrir?ordem=`: `compatibilidade` (padrão), `afinidade`, `recentes`.

## Banco de dados

| Tabela | Conteúdo |
|---|---|
| `contas` | apelido, **HMAC do e-mail** (busca) e **e-mail cifrado** (avisos), `webauthn_id` aleatório, quando confirmou 18+ e o consentimento, `papel`, `situacao`, `token_versao` |
| `verificacoes_email` | códigos e links de uso único (só em hash), 15 min, contador de tentativas |
| `passkeys`, `desafios_webauthn` | chaves **públicas** das passkeys e desafios de uso único (5 min); ver [autenticacao.md](autenticacao.md) |
| `perfis` | nome de exibição, bio, gênero, `busca_por[]`, `tags_quero[]`, `tags_curioso[]`, `tags_limite[]`, célula geohash |
| `curtidas`, `bloqueios` | relações entre contas (curtida recíproca = conexão) |
| `mensagens` | texto **cifrado** (AES-256-GCM), `lida_em` (some 5 min depois) |
| `fotos` | versões nítida e borrada, **cifradas**, e hash SHA-256 |
| `acessos_fotos` | pedidos de acesso: pendente, aprovado ou negado (só o dono muda) |
| `denuncias`, `moderacao_log` | denúncias (evidências cifradas) e trilha de auditoria das decisões |
| `generos`, `tags` | catálogos |

Tudo que pertence a uma conta tem `ON DELETE CASCADE`: excluir a conta apaga tudo na hora.

## Privacidade por construção

| Dado | O que acontece |
|---|---|
| E-mail | HMAC-SHA256 para busca + AES-256-GCM para avisos (chaves próprias, fora do banco); aberto só na hora de enviar; contatos registrados em `contatos_log` |
| Data de nascimento | verificada no cadastro e descartada |
| Coordenadas | viram uma célula de ~5 km; a posição exata nunca é gravada (detalhes e proteção contra trilateração em [localizacao.md](localizacao.md)) |
| IP | não é registrado; o rate limit usa HMAC com chave em memória trocada a cada hora |
| Metadados das fotos (GPS, aparelho) | removidos ao recriar a imagem pixel a pixel |
| Foto nítida | só sai do servidor para o dono e para quem ele aprovou |
| Mensagens | cifradas; invisíveis pela API no instante em que expiram; apagadas fisicamente em até 30 s |
| Limites absolutos | nunca aparecem para outras pessoas nem entram na similaridade |

As chaves (`JWT_SECRET`, `CHAVE_MENSAGENS`) ficam só nas variáveis de ambiente do servidor, nunca no banco.
Um vazamento do banco ou de um backup não expõe mensagens nem fotos.

## Front-end

`static/js/`: `app.js` (entrada), `roteador.js` (telas por hash, sem empilhar histórico, contexto por
navegação), `api.js`, `dom.js` (só insere texto, nunca HTML), `panico.js`, `componentes.js`,
`util.js` (funções puras testadas com `node --test`) e `telas/` (uma por tela).

CSP estrita (`script-src 'self'`), sem nenhum recurso de terceiros, `Cache-Control: no-store` em tudo.

## Moderação

- Denunciar também bloqueia. As mensagens podem ir junto como evidência, cifradas.
- Uma denúncia grave (menor de idade, conteúdo ilegal) ou 3 denunciantes distintos com contas de 24 h+
  deixam a conta **em revisão**: ela some da descoberta e não pode curtir nem mandar mensagens.
- Moderadores (`make moderador apelido=...`) usam `/api/moderacao/fila` e
  `/api/moderacao/contas/{id}/decisao` (`banir` ou `restaurar`). Banir derruba todas as sessões.
