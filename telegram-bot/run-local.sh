#!/usr/bin/env bash
set -euo pipefail

SECRETS_FILE="$(cd "$(dirname "$0")/.." && pwd)/secrets.yml"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "secrets.yml not found at $SECRETS_FILE"
    exit 1
fi

# Parse YAML without pyyaml — simple grep for top-level keys
_secret() { grep "^${1}:" "$SECRETS_FILE" | head -1 | sed 's/^[^:]*: *//; s/^"//; s/"$//' ; }

export BOT_TOKEN=$(_secret telegram_bot_token)
export REMNAWAVE_API_TOKEN=$(_secret remnawave_api_token)
export ADMIN_TELEGRAM_ID=$(_secret admin_telegram_id)
export REMNAWAVE_API_URL="https://panel.amenocturne.space/api"

cd "$(dirname "$0")"
exec uv run --no-project --with python-telegram-bot --with httpx bot.py
