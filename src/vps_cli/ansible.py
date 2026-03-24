from __future__ import annotations

import subprocess
from pathlib import Path

from vps_cli import find_project_root
from vps_cli.errors import ConfigError

TARGETS = {
    "vps": {
        "playbook": "playbooks/site.yml",
        "inventory": "inventories/production.yml",
        "host": "vps",
        "description": "main server",
    },
    "home": {
        "playbook": "playbooks/home_server.yml",
        "inventory": "inventories/hosts.yml",
        "host": "home_server",
        "description": "home server (MacBook)",
    },
    "remnawave": {
        "playbook": "playbooks/remnawave.yml",
        "inventory": "inventories/remnawave-test.yml",
        "host": "remnawave",
        "description": "panel server",
    },
    "nodes": {
        "playbook": "playbooks/node.yml",
        "inventory": "inventories/nodes.yml",
        "host": "remnawave_nodes",
        "description": "all VPN nodes",
    },
    "claudecodeui": {
        "playbook": "playbooks/claudecodeui.yml",
        "inventory": "inventories/claudecodeui.yml",
        "host": "claudecodeui",
        "description": "Claude Code UI server",
        "enabled": False,
    },
}

# Per-target deployable components (name → ansible tag)
TARGET_COMPONENTS: dict[str, dict[str, str]] = {
    "vps": {
        "caddy": "caddy",
        "authelia": "authelia",
        "monitoring": "monitoring",
        "personal-website": "personal-website",
        "coturn": "coturn",
        "briefing": "briefing",
        "tunnel": "tunnel",
        "projects": "projects",
        "dashboard": "dashboard",
    },
    "home": {
        "tunnel": "tunnel",
        "radicale": "radicale",
        "dwayne": "dwayne",
        "jellyfin": "jellyfin",
        "navidrome": "navidrome",
        "webdav": "webdav",
        "send": "send",
    },
    "remnawave": {
        "panel": "remnawave",
        "subscription": "remnawave-subscription",
        "telegram-bot": "remnawave-telegram-bot",
    },
    "claudecodeui": {
        "claudecodeui": "claudecodeui",
    },
}


def resolve_target(target_name: str | None) -> dict:
    name = target_name or "vps"
    if name not in TARGETS:
        raise ConfigError(f"Unknown target '{name}'. Valid: {', '.join(TARGETS)}")
    return TARGETS[name]


def run_ansible(
    *,
    playbook: str | None = None,
    inventory: str,
    host: str | None = None,
    module: str | None = None,
    module_args: str | None = None,
    tags: str | None = None,
    limit: str | None = None,
    verbose: bool = False,
    check: bool = False,
    syntax_check: bool = False,
) -> int:
    root = find_project_root()
    ansible_dir = root / "ansible"

    if playbook:
        cmd = ["ansible-playbook", playbook, "-i", inventory]
        if tags:
            cmd.extend(["--tags", tags])
        if limit:
            cmd.extend(["--limit", limit])
        if verbose:
            cmd.append("-v")
        if check:
            cmd.append("--check")
        if syntax_check:
            cmd.append("--syntax-check")
    elif host and module:
        cmd = ["ansible", host, "-i", inventory, "-m", module]
        if module_args:
            cmd.extend(["-a", module_args])
    else:
        print("Error: must specify either playbook or host+module")
        return 1

    result = subprocess.run(cmd, cwd=ansible_dir)
    return result.returncode


def ping_target(name: str, cfg: dict, ansible_dir: Path) -> tuple[str, bool]:
    try:
        result = subprocess.run(
            ["ansible", cfg["host"], "-i", cfg["inventory"],
             "-m", "ping", "-T", "5", "--one-line"],
            cwd=ansible_dir,
            capture_output=True,
            timeout=10,
        )
        return (name, result.returncode == 0)
    except (subprocess.TimeoutExpired, Exception):
        return (name, False)
