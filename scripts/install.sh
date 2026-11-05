#!/usr/bin/env bash
# Starts Switch and Mattermost locally and creates the court. Needs Docker and uv.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=0.31.0
ETIQUETA=${ETIQUETA:-switch-v$VERSION}
PROYECTO=${PROYECTO:-overruled}
COMPOSE=(docker compose -f deploy/local/standalone-docker-compose.yml --profile collab --profile gateway --project-directory . -p "$PROYECTO")

if [ "${1:-}" = "--clean" ]; then
  [ -d .switch ] && (cd .switch && "${COMPOSE[@]}" down -v)
  rm -rf .switch .state
fi

[ -d .switch ] || git clone -q --depth 1 --branch "$ETIQUETA" https://github.com/sandbox-quantum/switch.git .switch
if [ ! -f .switch/.env ]; then
  cp .switch/.env.example .switch/.env
  for key in DB_PASSWORD DB_OWNER_PASSWORD AGENT_REGISTRATION_TOKEN GATEWAY_ADMIN_PASSWORD \
               MATTERMOST_ADMIN_PASSWORD MATTERMOST_USER_PASSWORD; do
    sed -i.bak "s|^$key=.*|$key=$(openssl rand -hex 24)|" .switch/.env
  done
  sed -i.bak "s|^SECRET_KEYS=.*|SECRET_KEYS=local:$(openssl rand -hex 32)|" .switch/.env
  sed -i.bak "s|^CONTROLLER_TOKEN_SECRET=.*|CONTROLLER_TOKEN_SECRET=$(openssl rand -hex 32)|" .switch/.env
  # High ports, so nothing clashes with other services on this machine.
  sed -i.bak -e "s/^SWITCH_VERSION=.*/SWITCH_VERSION=$VERSION/" -e 's/^GATEWAY_HOST_PORT=.*/GATEWAY_HOST_PORT=3300/' \
    -e 's/^API_HOST_PORT=.*/API_HOST_PORT=8300/' -e 's/^MATTERMOST_HOST_PORT=.*/MATTERMOST_HOST_PORT=8365/' \
    -e 's/^POSTGRES_HOST_PORT=.*/POSTGRES_HOST_PORT=55433/' -e 's/^MATTERMOST_USER=.*/MATTERMOST_USER=cfo/' -e 's/^FEATURE_FLAGS_ENABLED=.*/FEATURE_FLAGS_ENABLED=agent_management/' .switch/.env
  rm -f .switch/.env.bak
fi
(cd .switch && "${COMPOSE[@]}" up -d)

echo "Waiting for Switch..."
for _ in $(seq 1 60); do
  curl -sf -m 3 localhost:8300/health >/dev/null && \
    [ "$(docker inspect -f '{{.State.Status}}' "$PROYECTO-setup-1")" = exited ] && break
  sleep 3
done
[ "$(docker inspect -f '{{.State.ExitCode}}' "$PROYECTO-setup-1")" = 0 ] || { echo "Switch setup failed"; exit 1; }

uv sync -q
[ -f .state/agents.json ] || uv run -q python -m overruled.setup_court
