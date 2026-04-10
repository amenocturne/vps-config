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
SUBSCRIPTION_BASE_URL: str = _require("SUBSCRIPTION_BASE_URL").rstrip("/")
PROMETHEUS_URL: str = os.environ.get("PROMETHEUS_URL", "http://168.100.11.130:9090").rstrip("/")
MINECRAFT_RCON_HOST: str = os.environ.get("MINECRAFT_RCON_HOST", "168.100.11.130")
MINECRAFT_RCON_PORT: int = int(os.environ.get("MINECRAFT_RCON_PORT", "25575"))
MINECRAFT_RCON_PASSWORD: str = os.environ.get("MINECRAFT_RCON_PASSWORD", "")
MINECRAFT_MANAGER_PORT: int = int(os.environ.get("MINECRAFT_MANAGER_PORT", "9001"))

# Mirrors remnawave.enums.ClientType — update when Remnawave adds new types
# "raw" is a special type: fetches default sub and base64-decodes to vless:// links
CLIENT_TYPES: list[list[tuple[str, str]]] = [
    [("VLESS ссылки", "raw"), ("Hiddify", "singbox")],
    [("V2Ray/Streisand", "v2ray-json"), ("Clash", "clash")],
    [("Sing-Box", "singbox"), ("Mihomo", "mihomo")],
    [("Stash", "stash"), ("JSON", "json")],
]
