"""
Centralized secrets management for the VPS config project.

The SCHEMA below is the single source of truth for all secret keys.
Commands: init, check, distribute.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Schema definition — every secret key, grouped by feature
# ---------------------------------------------------------------------------

SCHEMA = [
    {
        "section": "Remnawave Panel",
        "keys": [
            {
                "name": "remnawave_panel_url",
                "description": "Panel URL for API access",
                "used_by": ["remnawave playbook", "export-config", "sync-config"],
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
                "used_by": ["remnawave playbook"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "jwt_api_tokens_secret",
                "description": "JWT secret for API token signing",
                "used_by": ["remnawave playbook"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "metrics_pass",
                "description": "Password for metrics endpoint auth",
                "used_by": ["remnawave playbook"],
                "default": "",
                "generate": "openssl rand -hex 10",
            },
            {
                "name": "webhook_secret",
                "description": "Webhook signing secret",
                "used_by": ["remnawave playbook"],
                "default": "",
                "generate": "openssl rand -hex 32",
            },
            {
                "name": "postgres_password",
                "description": "PostgreSQL database password",
                "used_by": ["remnawave playbook"],
                "default": "",
                "generate": "openssl rand -hex 10",
            },
        ],
    },
    {
        "section": "VPN Nodes",
        "keys": [
            {
                "name": "node_secret_keys",
                "description": "Per-node secret keys from Remnawave Panel (dict: node-1, node-2, ...)",
                "used_by": ["remnawave playbook", "node playbook"],
                "default": None,
                "generate": None,
                "type": "dict",
            },
            {
                "name": "reality_private_key",
                "description": "Reality X25519 private key (server side)",
                "used_by": ["remnawave playbook", "node playbook"],
                "default": "",
                "generate": "docker run --rm teddysun/xray:latest xray x25519",
            },
            {
                "name": "reality_public_key",
                "description": "Reality X25519 public key (client side)",
                "used_by": ["remnawave playbook", "node playbook"],
                "default": "",
                "generate": None,
            },
            {
                "name": "reality_short_id",
                "description": "Reality short ID",
                "used_by": ["remnawave playbook", "node playbook"],
                "default": "",
                "generate": "openssl rand -hex 8",
            },
        ],
    },
    {
        "section": "Cloudflare",
        "keys": [
            {
                "name": "cloudflare_api_token",
                "description": "Cloudflare API token for DNS-01 challenge (Zone:DNS:Edit)",
                "used_by": ["remnawave playbook"],
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
                "used_by": ["site playbook", "home_server playbook"],
                "default": "",
                "generate": "uuidgen",
            },
            {
                "name": "xray_tunnel_private_key",
                "description": "X25519 private key for Xray tunnel",
                "used_by": ["site playbook", "home_server playbook"],
                "default": "",
                "generate": "docker run --rm teddysun/xray:latest xray x25519",
            },
            {
                "name": "xray_tunnel_public_key",
                "description": "X25519 public key for Xray tunnel",
                "used_by": ["site playbook", "home_server playbook"],
                "default": "",
                "generate": None,
            },
            {
                "name": "xray_tunnel_short_id",
                "description": "Short ID for Xray tunnel",
                "used_by": ["site playbook", "home_server playbook"],
                "default": "",
                "generate": "openssl rand -hex 8",
            },
        ],
    },
    {
        "section": "Radicale",
        "keys": [
            {
                "name": "radicale_user",
                "description": "Radicale CalDAV username",
                "used_by": ["home_server playbook"],
                "default": "admin",
                "generate": None,
            },
            {
                "name": "radicale_password_hash",
                "description": "Radicale CalDAV password hash (apr1 format)",
                "used_by": ["home_server playbook"],
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
                "used_by": ["site playbook"],
                "default": "",
                "generate": None,
            },
            {
                "name": "coturn_password",
                "description": "coturn TURN/STUN password",
                "used_by": ["site playbook"],
                "default": "",
                "generate": "openssl rand -hex 16",
            },
        ],
    },
    {
        "section": "Authelia",
        "keys": [
            {
                "name": "authelia_jwt_secret",
                "description": "JWT secret (min 32 chars)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_session_secret",
                "description": "Session secret (min 32 chars)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_storage_encryption_key",
                "description": "Storage encryption key (min 32 chars)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_admin_user",
                "description": "Admin username",
                "used_by": ["site playbook", "authelia role"],
                "default": "admin",
                "generate": None,
            },
            {
                "name": "authelia_admin_displayname",
                "description": "Admin display name",
                "used_by": ["site playbook", "authelia role"],
                "default": "Administrator",
                "generate": None,
            },
            {
                "name": "authelia_admin_email",
                "description": "Admin email address",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": None,
            },
            {
                "name": "authelia_admin_password_hash",
                "description": "Admin password hash (argon2id)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "docker run --rm authelia/authelia:latest authelia crypto hash generate --password 'yourpassword'",
            },
            {
                "name": "authelia_oidc_hmac_secret",
                "description": "OIDC HMAC secret (min 32 chars)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "openssl rand -base64 32",
            },
            {
                "name": "authelia_oidc_jwks_rsa_private_key",
                "description": "OIDC JWKS RSA private key (PEM format)",
                "used_by": ["site playbook", "authelia role"],
                "default": "",
                "generate": "openssl genrsa 2048",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_project_root() -> Path:
    """Walk up from CWD to find the project root (contains pyproject.toml)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    print("Error: could not find project root (no pyproject.toml found)", file=sys.stderr)
    sys.exit(1)


def secrets_path() -> Path:
    return find_project_root() / "secrets.yml"


def all_keys() -> list[dict]:
    """Flatten all keys from all sections."""
    return [key for section in SCHEMA for key in section["keys"]]


def section_for_key(key_name: str) -> str | None:
    for section in SCHEMA:
        for key in section["keys"]:
            if key["name"] == key_name:
                return section["section"]
    return None


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------


def _render_secrets_yml(existing: dict | None = None) -> str:
    """Build the full secrets.yml content as a string with comments."""
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

            # Use existing value if present, otherwise use schema default
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
                    lines.append(f"  # node-1: \"SECRET_KEY_FROM_PANEL\"")
            else:
                lines.append(f"{name}: {_yaml_quote(value)}")

    lines.append("")
    return "\n".join(lines), added_keys


def _yaml_quote(value) -> str:
    """Quote a value for YAML output."""
    if value is None or value == "":
        return '""'
    s = str(value)
    # Multi-line values (RSA keys) need special handling
    if "\n" in s:
        return f"'{s}'"
    # Values with special chars get double-quoted
    if any(c in s for c in ":#{}[]!|>&*?$'\"\\"):
        # Use single quotes for values containing dollar signs (password hashes)
        if "$" in s:
            return f"'{s}'"
        return f'"{s}"'
    return f'"{s}"'


def cmd_init() -> int:
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


# ---------------------------------------------------------------------------
# Check command
# ---------------------------------------------------------------------------


def _is_placeholder(value) -> bool:
    """Return True if a value looks like a placeholder (empty or None)."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def cmd_check(feature: str | None = None) -> int:
    path = secrets_path()
    if not path.exists():
        print(f"Error: {path} not found. Run 'just secrets-init' first.", file=sys.stderr)
        return 1

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    all_ok = True

    for section in SCHEMA:
        if feature and section["section"].lower() != feature.lower():
            continue

        keys = section["keys"]
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


# ---------------------------------------------------------------------------
# Distribute command
# ---------------------------------------------------------------------------


def cmd_distribute() -> int:
    """Distribute secrets to consumer locations.

    Currently a no-op since all consumers (Ansible playbooks, Python scripts)
    read directly from secrets.yml. Kept as a hook for future consumers.
    """
    result = cmd_check()
    if result == 0:
        print("All secrets available to consumers.")
    return result


# ---------------------------------------------------------------------------
# Setup command (interactive)
# ---------------------------------------------------------------------------


def _prompt(message: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        raw = input(f"  {message} [{default}]: ").strip()
        return raw if raw else default
    else:
        return input(f"  {message}: ").strip()


def _confirm(message: str) -> bool:
    raw = input(f"{message} [y/N]: ").strip().lower()
    return raw in ("y", "yes")


def cmd_setup() -> int:
    """Interactive setup: walk through each section, prompt for missing secrets."""
    path = secrets_path()

    # Load or create
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

        # Check which keys in this section are missing
        missing = [
            k for k in keys
            if _is_placeholder(data.get(k["name"], k.get("default")))
        ]

        if not missing:
            print(f"[ok] {section_name} -- all {len(keys)} key(s) configured")
            continue

        configured_count = len(keys) - len(missing)
        print(f"\n[{configured_count}/{len(keys)}] {section_name}")

        if not _confirm(f"  Configure {section_name}?"):
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
                # Dict keys need special handling -- just inform the user
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
            # Generate the file even if nothing was entered so the structure exists
            content, _ = _render_secrets_yml(data)
            path.write_text(content)
            print(f"Generated {path} with defaults. Edit manually to add secrets.")
        else:
            print("No changes made.")

    # Final status
    print()
    return cmd_check()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secrets",
        description="Manage project secrets from a single source of truth",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Generate or update secrets.yml from schema")

    check_p = sub.add_parser("check", help="Validate that all secrets are present")
    check_p.add_argument(
        "--feature",
        type=str,
        default=None,
        help="Check only a specific section (e.g., 'remnawave panel', 'authelia')",
    )

    sub.add_parser("distribute", help="Push secrets to consumer locations")

    sub.add_parser("setup", help="Interactive setup -- walks through each section and prompts for missing secrets")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init":
        sys.exit(cmd_init())
    elif args.command == "check":
        sys.exit(cmd_check(args.feature))
    elif args.command == "distribute":
        sys.exit(cmd_distribute())
    elif args.command == "setup":
        sys.exit(cmd_setup())


if __name__ == "__main__":
    main()
