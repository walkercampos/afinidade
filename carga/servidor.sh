#!/usr/bin/env bash
# Sobe a API contra o banco de carga, do jeito que roda em produção (sem --reload, vários workers).
#   WORKERS=4 carga/servidor.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export DATABASE_URL="${DATABASE_URL_CARGA:-postgresql://matchmaking:matchmaking@localhost:5432/afinidade_carga}"
export AMBIENTE=dev
# Os limites por conta continuam valendo; o teste respeita todos (cada pessoa age a cada ~30 s).
ulimit -n "$(ulimit -Hn)"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORTA:-8000}" --workers "${WORKERS:-4}" \
  --no-access-log --log-level warning --backlog 4096 --timeout-keep-alive 75 --ws-per-message-deflate false ${EXTRA:-}
