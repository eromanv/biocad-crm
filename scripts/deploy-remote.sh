#!/usr/bin/env bash
# Mirror of GitHub Actions deploy step — run from your laptop to debug VPS without CI.
#
# Required env:
#   DEPLOY_HOST   VPS IP or hostname
#   DEPLOY_USER   SSH login (same as GitHub secret DEPLOY_USER)
#   DEPLOY_PATH   absolute path to git clone on the server
#
# Optional:
#   DEPLOY_SSH_KEY   path to private key (default: ssh agent / default identity)
#   DEPLOY_SSH_PORT  default 22
#
# Example:
#   DEPLOY_HOST=1.2.3.4 DEPLOY_USER=user DEPLOY_PATH=/home/user/biocad-crm \
#     DEPLOY_SSH_KEY=~/.ssh/id_ed25519 ./scripts/deploy-remote.sh

set -euo pipefail

: "${DEPLOY_HOST:?Set DEPLOY_HOST}"
: "${DEPLOY_USER:?Set DEPLOY_USER}"
: "${DEPLOY_PATH:?Set DEPLOY_PATH (absolute path to clone on server)}"

PORT="${DEPLOY_SSH_PORT:-22}"
SSH_OPTS=(-p "$PORT" -o StrictHostKeyChecking=accept-new)

if [[ -n "${DEPLOY_SSH_KEY:-}" ]]; then
  if [[ ! -f "$DEPLOY_SSH_KEY" ]]; then
    echo "DEPLOY_SSH_KEY file not found: $DEPLOY_SSH_KEY" >&2
    exit 1
  fi
  SSH_OPTS+=(-i "$DEPLOY_SSH_KEY")
fi

REMOTE_PATH="$DEPLOY_PATH"

echo "==> SSH ${DEPLOY_USER}@${DEPLOY_HOST}:${PORT}"
echo "==> Remote path: ${REMOTE_PATH}"

# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "${DEPLOY_USER}@${DEPLOY_HOST}" \
  bash --noprofile --norc -euo pipefail -s -- "$REMOTE_PATH" <<'REMOTE'
path="$1"
if [[ ! -d "$path" ]]; then
  echo "DEPLOY_PATH does not exist: $path" >&2
  exit 1
fi
cd "$path"
if [[ ! -d .git ]]; then
  echo "Not a git repository: $path (clone the repo here first)" >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "Missing .env in $path (copy from .env.example and fill secrets)" >&2
  exit 1
fi
git fetch origin master
git reset --hard origin/master
docker compose -f docker-compose.prod.yml --env-file .env up --build -d
docker compose -f docker-compose.prod.yml --env-file .env ps
REMOTE

echo "==> Done"
