#!/usr/bin/env bash
# REAL jcode CLI -> REAL Ollama model, never a fake executor.
set -euo pipefail
: "${CHIMERA_MODEL:=qwen2.5-coder:1.5b}"
export JCODE_NO_TELEMETRY=1 DO_NOT_TRACK=1
command -v jcode >/dev/null || { echo "Actual jcode must be installed" >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker with local Ollama must be available" >&2; exit 2; }
jcode provider add chimera-ollama \
  --base-url http://127.0.0.1:11434/v1 \
  --model "$CHIMERA_MODEL" \
  --no-api-key --set-default
timeout 300s jcode --provider-profile chimera-ollama --model "$CHIMERA_MODEL" \
  run --no-update \
  'In one English sentence explain what a software coding agent does.' \
  > /tmp/chimera-real-jcode-output.txt
test -s /tmp/chimera-real-jcode-output.txt || {
  echo "jcode returned no completion" >&2; exit 1;
}
docker compose -f compose.yaml -f compose.jcode-ci.yaml exec -T ollama ollama ps \
  | grep -F "$CHIMERA_MODEL" >/dev/null || {
    echo "Ollama did not report the requested model loaded after jcode" >&2; exit 1;
  }
echo "REAL_JCODE_ACTUAL_OLLAMA_MODEL=PASS model=$CHIMERA_MODEL"
