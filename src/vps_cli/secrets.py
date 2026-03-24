from __future__ import annotations

from pathlib import Path

import yaml

from vps_cli import find_project_root
from vps_cli.util import confirm

SCHEMA = [
    {
        "section": "Remnawave Panel",
        "keys": [
            {
                "name": "remnawave_panel_url",
                "description": "Panel URL for API access",
                "used_by": ["remnawave", "export-config", "sync-config"],
                "default": "https://panel.amenocturne.space",
                "generate": None,
            },
            {
                "name": "remnawave_api_token",
                "description": "API token from Panel > API Tokens",
                "used_by": ["export-config", "sync-config"],
                "default": "",
                "generate": None,
            },
            {
                "name": "jwt_auth_secret",
                "description": "JWT auth secret for panel backend",
                "used_by": ["remnawave"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "jwt_api_tokens_secret",
                "description": "JWT secret for API token signing",
                "used_by": ["remnawave"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "metrics_pass",
                "description": "Password for metrics endpoint auth",
                "used_by": ["remnawave"],
                "default": "",
                "generate": "openssl rand -hex 10",
            },
            {
                "name": "webhook_secret",
                "description": "Webhook signing secret",
                "used_by": ["remnawave"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "postgres_password",
                "description": "PostgreSQL database password",
                "used_by": ["remnawave"],
                "default": "",
                "generate": "openssl rand -hex 10",
            },
            {
                "name": "remnawave_subscription_url",
                "description": "Subscription page URL for fetching user configs",
                "used_by": ["vps remnawave snapshot"],
                "default": "https://sub.amenocturne.space",
                "generate": None,
            },
            {
                "name": "telegram_bot_token",
                "description": "Telegram bot token from BotFather",
                "used_by": ["remnawave"],
                "default": "",
                "generate": None,
            },
            {
                "name": "admin_telegram_id",
                "description": "Admin's Telegram user ID (integer)",
                "used_by": ["remnawave"],
                "default": "",
                "generate": None,
            },
        ],
    },
    {
        "section": "VPN Nodes",
        "keys": [
            {
                "name": "node_secret_keys",
                "description": "Per-node secret keys from Remnawave Panel (dict: node-1, node-2, ...)",
                "used_by": ["remnawave", "nodes"],
                "default": None,
                "generate": None,
                "type": "dict",
            },
            {
                "name": "reality_private_key",
                "description": "Reality X25519 private key (server side)",
                "used_by": ["remnawave", "nodes"],
                "default": "",
                "generate": "docker run --rm teddysun/xray:latest xray x25519",
            },
            {
                "name": "reality_public_key",
                "description": "Reality X25519 public key (client side)",
                "used_by": ["remnawave", "nodes"],
                "default": "",
                "generate": None,
            },
            {
                "name": "reality_short_id",
                "description": "Reality short ID",
                "used_by": ["remnawave", "nodes"],
                "default": "",
                "generate": "openssl rand -hex 8",
            },
        ],
    },
    {
        "section": "Outline Shadowbox",
        "keys": [
            {
                "name": "outline_api_prefix",
                "description": "Management API path secret (from access.txt on server)",
                "used_by": ["nodes"],
                "default": "",
                "generate": None,
            },
        ],
    },
    {
        "section": "Cloudflare",
        "keys": [
            {
                "name": "cloudflare_api_token",
                "description": "Cloudflare API token for DNS-01 challenge (Zone:DNS:Edit)",
                "used_by": ["remnawave"],
                "default": "",
                "generate": None,
            },
            {
                "name": "cloudflare_origin_ca_key",
                "description": "Cloudflare Origin CA Key for certificate creation (My Profile > API Tokens)",
                "used_by": ["vps certs renew"],
                "default": "",
                "generate": None,
            },
        ],
    },
    {
        "section": "Xray Tunnel",
        "keys": [
            {
                "name": "xray_tunnel_uuid",
                "description": "UUID for Xray reverse proxy tunnel",
                "used_by": ["vps", "home_server"],
                "default": "",
                "generate": "uuidgen",
            },
            {
                "name": "xray_tunnel_private_key",
                "description": "X25519 private key for Xray tunnel",
                "used_by": ["vps", "home_server"],
                "default": "",
                "generate": "docker run --rm teddysun/xray:latest xray x25519",
            },
            {
                "name": "xray_tunnel_public_key",
                "description": "X25519 public key for Xray tunnel",
                "used_by": ["vps", "home_server"],
                "default": "",
                "generate": None,
            },
            {
                "name": "xray_tunnel_short_id",
                "description": "Short ID for Xray tunnel",
                "used_by": ["vps", "home_server"],
                "default": "",
                "generate": "openssl rand -hex 8",
            },
        ],
    },
    {
        "section": "Minecraft",
        "keys": [
            {
                "name": "minecraft_rcon_password",
                "description": "RCON password for Minecraft server management",
                "used_by": ["home_server", "remnawave"],
                "default": "",
                "generate": "openssl rand -hex 16",
            },
        ],
    },
    {
        "section": "WebDAV",
        "keys": [
            {
                "name": "webdav_user",
                "description": "WebDAV username",
                "used_by": ["home_server"],
                "default": "",
                "generate": None,
            },
            {
                "name": "webdav_password",
                "description": "WebDAV password",
                "used_by": ["home_server"],
                "default": "",
                "generate": "openssl rand -hex 16",
            },
        ],
    },
    {
        "section": "Radicale",
        "keys": [
            {
                "name": "radicale_user",
                "description": "Radicale CalDAV username",
                "used_by": ["home_server"],
                "default": "admin",
                "generate": None,
            },
            {
                "name": "radicale_password_hash",
                "description": "Radicale CalDAV password hash (apr1 format)",
                "used_by": ["home_server"],
                "default": "",
                "generate": "htpasswd -nbBC 5 '' 'yourpassword' | cut -d: -f2",
            },
        ],
    },
    {
        "section": "TURN/STUN",
        "keys": [
            {
                "name": "coturn_user",
                "description": "coturn TURN/STUN username",
                "used_by": ["vps"],
                "default": "",
                "generate": None,
            },
            {
                "name": "coturn_password",
                "description": "coturn TURN/STUN password",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl rand -hex 16",
            },
        ],
    },
    {
        "section": "Claude Code UI",
        "keys": [
            {
                "name": "claudecodeui_anthropic_api_key",
                "description": "Anthropic API key for Claude Code UI (optional — can use CLI login instead)",
                "used_by": ["claudecodeui"],
                "default": "optional",
                "generate": None,
            },
        ],
    },
    {
        "section": "Authelia",
        "keys": [
            {
                "name": "authelia_jwt_secret",
                "description": "JWT secret (min 32 chars)",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_session_secret",
                "description": "Session secret (min 32 chars)",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_storage_encryption_key",
                "description": "Storage encryption key (min 32 chars)",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_admin_user",
                "description": "Admin username",
                "used_by": ["vps"],
                "default": "admin",
                "generate": None,
            },
            {
                "name": "authelia_admin_displayname",
                "description": "Admin display name",
                "used_by": ["vps"],
                "default": "Administrator",
                "generate": None,
            },
            {
                "name": "authelia_admin_email",
                "description": "Admin email address",
                "used_by": ["vps"],
                "default": "",
                "generate": None,
            },
            {
                "name": "authelia_admin_password_hash",
                "description": "Admin password hash (argon2id)",
                "used_by": ["vps"],
                "default": "",
                "generate": "docker run --rm authelia/authelia:latest authelia crypto hash generate --password 'yourpassword'",
            },
            {
                "name": "authelia_shared_password_hash",
                "description": "Shared user password hash (argon2id) — for friends accessing shared services",
                "used_by": ["vps"],
                "default": "",
                "generate": "docker run --rm authelia/authelia:latest authelia crypto hash generate --password 'yourpassword'",
            },
            {
                "name": "authelia_oidc_hmac_secret",
                "description": "OIDC HMAC secret (min 32 chars)",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_oidc_jwks_rsa_private_key",
                "description": "OIDC JWKS RSA private key (PEM format)",
                "used_by": ["vps"],
                "default": "",
                "generate": "openssl genrsa 2048",
            },
        ],
    },
]


def secrets_path() -> Path:
    return find_project_root() / "secrets.yml"


def all_keys() -> list[dict]:
    return [key for section in SCHEMA for key in section["keys"]]


def keys_for_target(target_name: str) -> list[dict]:
    """Return schema keys whose used_by includes the given target name."""
    return [
        key
        for section in SCHEMA
        for key in section["keys"]
        if target_name in key["used_by"]
    ]


def section_for_key(key_name: str) -> str | None:
    for section in SCHEMA:
        for key in section["keys"]:
            if key["name"] == key_name:
                return section["section"]
    return None


def _render_secrets_yml(existing: dict | None = None) -> tuple[str, list[str]]:
    lines = [
        "---",
        "# Project secrets -- single source of truth",
        "# Generated by: just secrets-init",
        "# Do NOT commit this file",
    ]

    added_keys: list[str] = []

    for section in SCHEMA:
        lines.append("")
        lines.append(f"# {'=' * 77}")
        lines.append(f"# {section['section']}")
        lines.append(f"# {'=' * 77}")

        for key in section["keys"]:
            lines.append("")
            lines.append(f"# {key['description']}")
            lines.append(f"# Used by: {', '.join(key['used_by'])}")
            if key.get("generate"):
                lines.append(f"# Generate: {key['generate']}")

            name = key["name"]
            is_dict = key.get("type") == "dict"

            if existing and name in existing:
                value = existing[name]
            else:
                value = key["default"]
                if existing is not None:
                    added_keys.append(name)

            if is_dict:
                lines.append(f"{name}:")
                if isinstance(value, dict):
                    for k, v in value.items():
                        lines.append(f"  {k}: {_yaml_quote(v)}")
                else:
                    lines.append(f'  # node-1: "SECRET_KEY_FROM_PANEL"')
            else:
                lines.append(f"{name}: {_yaml_quote(value)}")

    lines.append("")
    return "\n".join(lines), added_keys


def _yaml_quote(value) -> str:
    if value is None or value == "":
        return '""'
    s = str(value)
    if "\n" in s:
        return f"'{s}'"
    if any(c in s for c in ":#{}[]!|>&*?$'\"\\"):
        if "$" in s:
            return f"'{s}'"
        return f'"{s}"'
    return f'"{s}"'


def _is_placeholder(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def _prompt(message: str, default: str = "") -> str:
    if default:
        raw = input(f"  {message} [{default}]: ").strip()
        return raw if raw else default
    else:
        return input(f"  {message}: ").strip()


def init_secrets() -> int:
    path = secrets_path()
    existing = None

    if path.exists():
        with open(path) as f:
            existing = yaml.safe_load(f) or {}
        print(f"Updating existing {path.name}...")
    else:
        print(f"Creating {path.name}...")

    content, added_keys = _render_secrets_yml(existing)
    path.write_text(content)

    if added_keys:
        print(f"Added {len(added_keys)} new key(s):")
        for k in added_keys:
            sec = section_for_key(k)
            print(f"  [{sec}] {k}")
    elif existing is not None:
        print("No new keys to add -- secrets.yml is up to date.")
    else:
        print(f"Generated {path} with placeholder values.")
        print("Fill in your secrets and re-run 'just secrets-check' to verify.")

    return 0


def check_secrets(feature: str | None = None, target: str | None = None) -> int:
    path = secrets_path()
    if not path.exists():
        print(f"Error: {path} not found. Run 'just secrets-init' first.")
        return 1

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    relevant_names = {k["name"] for k in keys_for_target(target)} if target else None

    all_ok = True

    for section in SCHEMA:
        if feature and section["section"].lower() != feature.lower():
            continue

        keys = section["keys"]
        if relevant_names is not None:
            keys = [k for k in keys if k["name"] in relevant_names]
        if not keys:
            continue
        configured = 0
        missing_items = []

        for key in keys:
            name = key["name"]
            value = data.get(name)
            if not _is_placeholder(value):
                configured += 1
            else:
                hint = ""
                if key.get("generate"):
                    hint = f" -- Generate: {key['generate']}"
                missing_items.append(f"  [missing] {name} -- {key['description']}{hint}")

        total = len(keys)
        status = f"{section['section']}: {configured}/{total} configured"

        if missing_items:
            all_ok = False
            print(status)
            for item in missing_items:
                print(item)
        else:
            print(status)

        print()

    if all_ok:
        print("All secrets configured.")
        return 0
    else:
        print("Some secrets are missing. Fill them in at: " + str(path))
        return 1


def distribute_secrets() -> int:
    result = check_secrets()
    if result == 0:
        print("All secrets available to consumers.")
    return result


def setup_secrets() -> int:
    path = secrets_path()

    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        print(f"Found existing {path.name}\n")
    else:
        data = {}
        print(f"No {path.name} found -- starting fresh\n")

    changed = False

    for section in SCHEMA:
        section_name = section["section"]
        keys = section["keys"]

        missing = [
            k for k in keys
            if _is_placeholder(data.get(k["name"], k.get("default")))
        ]

        if not missing:
            print(f"[ok] {section_name} -- all {len(keys)} key(s) configured")
            continue

        configured_count = len(keys) - len(missing)
        print(f"\n[{configured_count}/{len(keys)}] {section_name}")

        if not confirm(f"  Configure {section_name}?"):
            print(f"  Skipped")
            continue

        for key in missing:
            name = key["name"]
            is_dict = key.get("type") == "dict"
            desc = key["description"]
            gen_hint = key.get("generate")

            print(f"\n  {name}")
            print(f"    {desc}")
            if gen_hint:
                print(f"    Generate: {gen_hint}")

            if is_dict:
                print(f"    (dict value -- edit secrets.yml manually for this one)")
                continue

            value = _prompt("Value (empty to skip)")
            if value:
                data[name] = value
                changed = True
                print(f"    Set.")
            else:
                print(f"    Skipped.")

    print()

    if changed:
        content, _ = _render_secrets_yml(data)
        path.write_text(content)
        print(f"Saved to {path}")
    else:
        if not path.exists():
            content, _ = _render_secrets_yml(data)
            path.write_text(content)
            print(f"Generated {path} with defaults. Edit manually to add secrets.")
        else:
            print("No changes made.")

    print()
    return check_secrets()
