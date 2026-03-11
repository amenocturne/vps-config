import os
import sys

def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return value

BOT_TOKEN: str = _require("BOT_TOKEN")
REMNAWAVE_API_URL: str = _require("REMNAWAVE_API_URL").rstrip("/")
REMNAWAVE_API_TOKEN: str = _require("REMNAWAVE_API_TOKEN")
ADMIN_TELEGRAM_ID: int = int(_require("ADMIN_TELEGRAM_ID"))
