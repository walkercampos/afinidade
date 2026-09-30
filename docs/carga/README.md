# Teste de carga: 30 mil pessoas online ao mesmo tempo

Data: 30/09/2026 · Versão: 0.5.0 + correções deste relatório · Kit: [`carga/`](../../carga/README.md)

## Resumo

| | Resultado |
|---|---|
| **30 mil online, nesta máquina** | **Não aguenta.** A máquina de teste (4 vCPU) roda API, banco e gerador de carga juntos; a CPU acaba antes. |
| **Limite medido nesta máquina** | **10 mil online passa em todas as metas** (0% de erro, p95 ~380 ms). 15 mil já colapsa. |
| **Antes das correções** | **5 mil** online derrubavam a API: 50% de erro, respostas de 60 s. |
| **Bugs reais encontrados e corrigidos** | 7 (abaixo), todos com teste de regressão. Três deles afetam produção com qualquer volume. |
| **Para 30 mil** | Escalar na horizontal: ~6 vCPU de API (ex.: 3 instâncias de 2 vCPU) e ~6 a 8 vCPU de banco, com o gerador de carga em outra máquina. As correções deste relatório são o que torna isso possível. |

## O cenário

"Uma pessoa online" é o que o app faz com a tela aberta: um **WebSocket aberto o tempo todo** e,
a cada **~30 s**, uma ação pela API (45% descobrir, 15% lista de conversas, 15% ler conversa,
10% mandar mensagem, 10% conta, 5% conexões). Detalhes em [`carga/README.md`](../../carga/README.md).

É um perfil **intenso**: 30 mil pessoas assim geram ~1.000 requisições/s e ~450 buscas na
descoberta por segundo. Uso real costuma ser mais leve (tela parada, app em segundo plano), então
a capacidade real por máquina tende a ser maior que a medida aqui.

**Metas:** erro < 1%, p95 < 500 ms, p99 < 1,5 s, descobrir p95 < 800 ms, WebSockets abrindo > 99%.

**Ambiente:** um contêiner com 4 vCPU e 16 GB, dividido entre PostgreSQL 16 (com TLS), a API
(uvicorn, 4 workers) e o gerador de carga. Banco com 30 mil contas completas na Grande São Paulo,
todas se buscando mutuamente (o pior caso para a descoberta).

## Linha do tempo

| # | Execução | Resultado | O que revelou |
|---|---|---|---|
| 1 | 5 mil, versão original | ❌ 50,6% de erro, p50 47 s, p95 60 s; 85% dos WebSockets abrem | Descoberta O(N) e avisos presos no worker (bugs 1 a 4) |
| 2 | 5 mil, com as correções 1 a 4 | ✅ 0% de erro em 48.961 requisições, p95 61 ms, descobrir p95 74 ms, 100% dos WebSockets | |
| 3 | 30 mil com k6 | ❌ o próprio k6 foi morto por falta de memória (5,2 GB) | k6 reserva ~330 KB por usuário virtual; criado o gerador leve em Node |
| 4 | 30 mil, gerador em Node | ❌ a API **congelou** com ~10,7 mil | Impasse no pool de conexões (bug 5) |
| 5 | 30 mil, bug 5 corrigido | ❌ CPU esgotada a partir de ~12 mil; 57% de erro | Limite de CPU; WebSocket gastando memória à toa (bug 6) |
| 6 | 10 mil | ⚠️ 0% de erro, mas p95 3,9 s | Postgres a 200% de CPU; `pg_stat_statements` apontou o bug 7 |
| 7 | 10 mil, bug 7 corrigido | ✅ **todas as metas**: 0% de erro em 103.867 requisições, p95 ~380 ms, p99 ~1,1 s, descobrir p95 ~410 ms | |
| 8 | 15 mil | ❌ colapso: 52% de erro | Limite desta máquina entre 10 e 15 mil |
| 9 | 30 mil, versão final | ❌ 46% de erro no pico. p95 104 ms com 9 mil online, 9,6 s com 12,7 mil, colapso com 18 mil; depois o sistema se estabiliza sozinho em ~10,5 mil conectados e ~350 req/s | Confirma o teto desta máquina (execuções 7 e 8) |

## Bugs encontrados (todos corrigidos, com teste)

| # | Problema | Efeito | Correção | Ganho |
|---|---|---|---|---|
| 1 | A descoberta calculava a nota de **todos** os perfis da região a cada busca | Custo crescia com o número de usuários | Nota só para os 1.000 elegíveis mais ativos, **depois** de todos os filtros | ~90 → ~40 ms |
| 2 | Faltava índice por atividade | O banco lia e ordenava todos os perfis | Migração 0011 (`perfis_ativos_idx`) | ~40 → **~7 ms** |
| 3 | Plano genérico do PostgreSQL a partir da 6ª execução de cada consulta preparada | O índice era ignorado depois de 5 buscas por conexão | Conexões com `plan_cache_mode = force_custom_plan` | 61 → 7 ms |
| 4 | Com mais de um worker, o aviso de mensagem só chegava a quem estava no mesmo processo | ~40% dos avisos entregues com 4 workers | Avisos também pelo PostgreSQL (`LISTEN/NOTIFY`, só ids) | 100% entregues |
| 5 | Ao avisar, a rota segurava uma conexão do pool e pedia outra ao mesmo pool | Com 10 envios simultâneos num worker, **a API inteira parava** | Publicação com conexão própria, em fila e em lotes | Sem impasse |
| 6 | Compressão por mensagem no WebSocket | 77 KB de memória por conexão, para avisos de ~60 bytes | `--ws-per-message-deflate false` (Dockerfile) | 43 KB por conexão (−44%) |
| 7 | Ler uma conversa e listar conversas liam a **tabela inteira de mensagens** | Custo crescia com o total de mensagens do app | Condição reescrita para o índice do par + migração 0012 | 6,3 → **0,055 ms** e 4,9 → 0,32 ms |

Os bugs 3, 5 e 7 afetam produção **com qualquer volume**: o 7, por exemplo, deixaria cada conversa
aberta mais lenta a cada mensagem enviada no app inteiro.

## Onde está o limite agora

Com 10 mil online (execução 7), a CPU fica assim: **PostgreSQL ~160%**, **API ~130%**, gerador
~35% (100% = 1 núcleo). No banco, `pg_stat_statements` mostra a descoberta como ~90% do tempo
(~7,5 ms por busca, custo fixo); todo o resto está abaixo de 0,5 ms.

Estimativa para 30 mil com este perfil intenso (proporcional, com ~40% de folga):

| Parte | CPU medida por mil online | Para 30 mil |
|---|---|---|
| API | ~0,13 vCPU | ~4 vCPU → **~6 vCPU** com folga (ex.: 3 instâncias de 2 vCPU) |
| PostgreSQL | ~0,16 vCPU | ~5 vCPU → **6 a 8 vCPU** |
| Memória dos WebSockets | 43 KB por conexão | ~1,3 GB, divididos entre as instâncias |

Com várias instâncias, as conexões ao banco somam (hoje: 10 do pool + 2 dos avisos por worker):
use o pooler do Neon (PgBouncer) na `DATABASE_URL`.

## O que vem depois (não feito aqui)

1. **Degradar em vez de colapsar.** Hoje, acima do limite, as requisições entram numa fila até o
   tempo esgotar (60 s), e as reconexões pioram tudo. Com `--limit-concurrency` no uvicorn, a API
   responde 503 na hora e o cliente espera antes de tentar de novo.
2. **Descoberta mais barata.** É ~90% do tempo do banco. Opções: guardar a primeira página de
   cada pessoa por 1 a 2 minutos, ou reduzir o teto de 1.000 candidatos.
3. **Rodar o teste oficial (k6) numa máquina só para o gerador**, apontando para um ambiente de
   homologação com a configuração de produção. `carga/online.js` já está pronto para isso.
4. **Limite de requisições compartilhado** entre instâncias (hoje é por processo; limitação já
   documentada em `docs/arquitetura.md`).

## Como repetir

Veja [`carga/README.md`](../../carga/README.md). Resumo:

```bash
DATABASE_URL=.../afinidade_carga AMBIENTE=dev python -m carga.semear 30000
WORKERS=4 carga/servidor.sh &
GERADOR=node USUARIOS=10000 PROCESSOS=2 SUBIDA_S=150 PICO_S=300 NOME=10k carga/rodar.sh
```
