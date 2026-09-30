#!/usr/bin/env bash
# Roda o cenário "online" em N processos e guarda o resumo de cada um em
# carga/resultados/<nome>-<i>.json, mais o monitor de CPU, memória e conexões.
#   GERADOR=k6   K6=/caminho/k6 USUARIOS=30000 PROCESSOS=2 NOME=30k carga/rodar.sh -e SUBIDA=5m -e PICO=10m
#   GERADOR=node USUARIOS=30000 PROCESSOS=2 SUBIDA_S=300 PICO_S=600 NOME=30k carga/rodar.sh
# O k6 é o padrão; o gerador em Node (carga/online-node.mjs) usa ~15x menos memória.
set -euo pipefail
cd "$(dirname "$0")/.."
GERADOR="${GERADOR:-k6}"; K6="${K6:-k6}"; USUARIOS="${USUARIOS:-30000}"; PROCESSOS="${PROCESSOS:-2}"; NOME="${NOME:-carga}"
mkdir -p carga/resultados
export K6_NO_USAGE_REPORT=true
ulimit -n "$(ulimit -Hn)"
( while sleep 10; do
    # 2ª amostra do top = uso de CPU no último segundo (100% = 1 núcleo)
    top -bn2 -d1 -w 200 | awk -v hora="$(date +%T)" '
      /^top -/ {amostra++}
      amostra == 2 && /^%Cpu/ {ocioso = $8}
      amostra == 2 && $1 ~ /^[0-9]+$/ {
        cmd = $12; cpu = $9; mem = $6
        if (cmd == "k6" || cmd == "node") {k6 += cpu; k6m += mem}
        else if (cmd == "postgres") {pg += cpu; pgm += mem}
        else if (cmd ~ /^(python3?|uvicorn)$/) {api += cpu; apim += mem}
      }
      END {printf "%s ocioso=%s%% cpu[gerador=%d%% api=%d%% postgres=%d%%] ", hora, ocioso, k6, api, pg}'
    echo "tcp_8000=$(awk '$2 ~ /:1F40$/ && $4 == "01"' /proc/net/tcp | wc -l)" \
      "mem_livre=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)MB"
  done ) > "carga/resultados/${NOME}-monitor.log" &
MONITOR=$!
trap 'kill $MONITOR 2>/dev/null' EXIT
pids=()
for ((i = 0; i < PROCESSOS; i++)); do
  # Cada processo mira um IP de loopback diferente: mais portas de origem disponíveis.
  base="http://127.0.0.$((i + 1)):8000"
  if [[ "$GERADOR" == node ]]; then
    BASE="$base" USUARIOS="$USUARIOS" FATIA="$i/$PROCESSOS" node carga/online-node.mjs \
      "carga/resultados/${NOME}-${i}.json" > "carga/resultados/${NOME}-${i}.txt" 2> "carga/resultados/${NOME}-${i}.err" &
  else
    "$K6" run --no-color -q --address "127.0.0.1:$((6565 + i))" -e BASE="$base" -e USUARIOS="$USUARIOS" \
      -e FATIA="$i/$PROCESSOS" --summary-export "carga/resultados/${NOME}-${i}.json" "$@" carga/online.js \
      > "carga/resultados/${NOME}-${i}.txt" 2> "carga/resultados/${NOME}-${i}.err" &
  fi
  pids+=($!)
done
status=0
for p in "${pids[@]}"; do wait "$p" || status=$?; done
exit $status
