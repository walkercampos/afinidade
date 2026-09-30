# Teste de carga

Kit para medir quantas pessoas **online ao mesmo tempo** o Afinidade aguenta. Resultados e
análise em [docs/carga/](../docs/carga/README.md).

## O que é "uma pessoa online"

O que o app faz de verdade com a tela aberta:

- um **WebSocket** aberto o tempo todo (avisos de mensagem nova, leitura e prazo);
- a cada **~30 s** (21 a 39 s, sorteado), uma ação pela API:

| Ação | Rota | Peso |
|---|---|---|
| Descobrir perfis | `GET /api/descobrir?limite=20` | 45% |
| Lista de conversas | `GET /api/conversas` | 15% |
| Ler a conversa | `GET /api/conversas/{par}/mensagens` | 15% |
| Mandar mensagem | `POST /api/conversas/{par}/mensagens` | 10% |
| Ver a conta | `GET /api/conta` | 10% |
| Conexões | `GET /api/conexoes` | 5% |

É um uso intenso: 30 mil pessoas online geram ~1.000 requisições/s. Os limites por conta
(120 req/min, 30 mensagens/min) continuam ligados e o teste respeita todos.

## Metas (o teste falha se não cumprir)

| Métrica | Meta |
|---|---|
| Requisições com erro | < 1% |
| Tempo de resposta p95 / p99 | < 500 ms / < 1,5 s |
| Descobrir p95 | < 800 ms |
| WebSockets que conectam | > 99% |

## Como rodar

Precisa de PostgreSQL local, do [k6](https://grafana.com/docs/k6/latest/set-up/install-k6/) e
de um `.env` de desenvolvimento.

```bash
# 1. Banco só de carga (o nome TEM de terminar em _carga; o semeador recusa qualquer outro)
createdb afinidade_carga
DATABASE_URL=postgresql://.../afinidade_carga python -m app.admin migrar

# 2. Contas prontas (termos, idade, perfil, localização, pares de conexão) + tokens
set -a; . ./.env; set +a
DATABASE_URL=postgresql://.../afinidade_carga AMBIENTE=dev python -m carga.semear 30000

# 3. API como em produção (vários workers, sem --reload)
WORKERS=4 carga/servidor.sh &

# 4. Carga: cada processo do k6 segura ~15 mil conexões
K6=k6 USUARIOS=30000 PROCESSOS=2 NOME=30k carga/rodar.sh -e SUBIDA=5m -e PICO=10m
```

Resultados em `carga/resultados/` (fora do git): resumo de cada processo do k6
(`<nome>-<i>.txt` e `.json`) e o monitor de CPU, memória e conexões (`<nome>-monitor.log`).

Para um teste rápido: `USUARIOS=500 PROCESSOS=1 carga/rodar.sh -e SUBIDA=20s -e PICO=1m`.

## Segurança

- `carga/semear.py` só roda com `AMBIENTE` diferente de produção **e** num banco cujo nome
  termina em `_carga`, e apaga só contas `carga_*`.
- Os tokens ficam em `carga/.tokens.json` (permissão 600, fora do git) e valem 24 h.
- Nunca rode contra o ambiente publicado: o teste cria mensagens e ocupa a API.
