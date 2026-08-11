#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/administrator/hyperagent-skill
source "$ROOT/env.sh"
set -a
source "$HOME/.config/hyperagent/engine.env"
set +a
export HSMT_ENGINE_URL=http://127.0.0.1:8787
export NODE_COMPILE_CACHE=/tmp/openclaw-node-compile-cache
export OPENCLAW_NO_RESPAWN=1
mkdir -p "$NODE_COMPILE_CACHE"
exec openclaw "$@"
