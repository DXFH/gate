#!/usr/bin/env bash
# Fault-injection tests for src/vpngate.py. Writes tests/results/*.log and a summary table.
cd "$(dirname "$0")/.." || exit 1
mkdir -p tests/results; : > tests/results/summary.txt
export MAX_CHECK_NODES=${MAX_CHECK_NODES:-60} CHECK_TIMEOUT=2 RETRY_BASE_DELAY=0.1 CHECK_CONCURRENCY=8 BREAKER_THRESHOLD=10 OPTIMAL_API=""
run_case() {  # name mode extra-env...
  local name=$1 mode=$2; shift 2
  local port=$((18000 + RANDOM % 1000)) pid="" url=""
  if [ "$mode" != "none" ]; then
    python3 tests/mock_worker.py $port $mode & pid=$!; sleep 0.7
    url="http://127.0.0.1:$port/check?sstp=vpn:vpn@"
  fi
  local out=tests/results/$name.out; rm -f $out.gh
  local t0=$(date +%s)
  env DOMAIN="$url" GITHUB_OUTPUT=$PWD/$out.gh PUBLIC_DIR=$PWD/tests/results/public-$name "$@" python3 src/vpngate.py > tests/results/$name.log 2>&1
  local rc=$?; local dt=$(( $(date +%s) - t0 ))
  [ -n "$pid" ] && kill $pid 2>/dev/null
  local pub=$(grep -h '^publish=' $out.gh 2>/dev/null | tail -1 | cut -d= -f2)
  local nodes=0; [ -f tests/results/public-$name/nodes.txt ] && nodes=$(wc -l < tests/results/public-$name/nodes.txt)
  printf '%-22s mode=%-8s exit=%s publish=%-5s nodes.txt_lines=%-4s time=%ss\n' "$name" "$mode" "$rc" "${pub:-n/a}" "$nodes" "$dt" | tee -a tests/results/summary.txt
}
run_case T1_no_domain none
run_case T2_ok ok
run_case T3_timeout timeout
run_case T4_http500 http500
run_case T5_garbage garbage
run_case T6_http403 http403
run_case T7_flaky flaky
run_case T8_timeout_strict timeout STRICT=1