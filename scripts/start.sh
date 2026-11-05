#!/usr/bin/env bash
# Starts the bots. OVERRULED_OFFLINE=1 runs scripted speeches, for trying it without Claude.
cd "$(dirname "$0")/.."
BIN=.controller/node_modules/.bin/switch-agent-controller
if [ -d .state/controller ]; then
  "$BIN" run --data-dir .state/controller > .state/controller.log 2>&1 &
  trap 'kill %1 2>/dev/null' EXIT
fi
uv run -q python -m overruled.court
