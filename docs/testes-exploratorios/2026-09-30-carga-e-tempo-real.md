# 2026-09-30 · Carga, avisos entre workers e descoberta com teto

- **Missão:** Explorar os avisos em tempo real com vários workers, o banco instável e a
  descoberta com teto de candidatos, com a API real (4 workers) e 30 mil contas, para descobrir
  se algum aviso vaza conteúdo, chega duplicado ou se perde depois de falhas, e se "sair"
  continua fechando tudo.
- **Versão:** branch `funcionalidade/teste-de-carga`
- **Tempo:** sessão curta, assistida por script (Python + websockets + asyncpg), depois do teste de
  carga e somada a ele (o próprio teste de carga foi exploratório: cada execução mudou o roteiro da
  seguinte; veja a linha do tempo em [docs/carga/](../carga/README.md)).
- **Ambiente:** uvicorn com 4 workers, PostgreSQL 16 local, banco `afinidade_carga`.

## O que foi tentado

1. A mesma pessoa com 5 aparelhos (espalhados pelos workers); a outra manda uma mensagem.
2. Abrir o 6º ao 12º aparelho da mesma pessoa.
3. Derrubar no banco as 4 conexões `LISTEN` (`pg_terminate_backend`), mandar mensagem logo em
   seguida e de novo 6 s depois.
4. Publicar no canal cargas malformadas e um evento com id inválido.
5. Escutar o canal `afinidade_avisos` direto no banco enquanto uma mensagem é enviada.
6. "Sair de todos os dispositivos" com 7 aparelhos abertos em workers diferentes.
7. Paginar a descoberta de 100 em 100 até acabar.

## Achados

| # | Tipo | O que acontece | Esperado | Situação |
|---|---|---|---|---|
| 1 | ok | Cada um dos 5 aparelhos recebe 1 aviso, só com tipo e id da conversa | idem | — |
| 2 | observação | Do 6º ao 8º aparelho são aceitos; do 9º em diante, recusados (4429). O limite de 5 é **por worker** | 5 no total | Aceito por ora: em produção roda 1 worker (Dockerfile). Com várias instâncias, contar no banco ou no pub/sub. Registrado em `docs/arquitetura.md` |
| 3 | ok | Com os ouvintes derrubados, só o worker de quem enviou entrega; em ≤ 6 s os 4 reconectam sozinhos e todos voltam a receber | idem | — |
| 4 | ok | Cargas malformadas são ignoradas; a API segue respondendo | idem | — |
| 5 | ok | No banco passa só `{"o","a","c","t","v"}` (ids e tipo), nunca o texto | idem | — |
| 6 | ok | Sair fecha os 7 canais, em todos os workers, com 4401 | idem | Na 1ª tentativa o script lia um aviso antigo ainda na fila e marcava "continuou aberto"; corrigido o script, confirmado |
| 7 | ok | 1.000 perfis em 11 páginas, sem repetidos (o teto de candidatos) | idem | — |

O teste de carga em si encontrou 7 bugs, todos corrigidos com teste de regressão: descoberta O(N),
falta de índice por atividade, plano genérico do PostgreSQL, avisos presos no worker, impasse no
pool, WebSocket comprimindo à toa e mensagens lendo a tabela inteira. Detalhes e números em
[docs/carga/](../carga/README.md).

## Viraram teste

- `tests/test_tempo_real.py`: ida e volta do evento, eventos inválidos e malformados, aviso e
  derrubada entre dois processos, sem banco segue local, e o impasse no pool.
- `tests/test_desempenho_consultas.py`: consultas quentes precisam poder usar índice.
- `tests/test_descoberta_filtros.py`: teto de candidatos depois de todos os filtros.
- `tests/test_modelo_dados.py`: índice por atividade e plano sob medida no pool.
- `tests/test_unit_regressoes.py`: WebSocket sem compressão na imagem.
- `tests/test_unit_carga.py` e `tests/js/carga.test.js`: semeador (nunca produção) e estatística
  do gerador.

## Ideias para a próxima sessão

- Rodar `carga/online.js` (k6) numa máquina separada contra homologação.
- Explorar o comportamento com `--limit-concurrency` (responder 503 em vez de enfileirar).
