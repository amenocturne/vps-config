"""
Generate Reality x25519 keypair + short ID on a remote node and inject into state.yml.

Replaces placeholder patterns like __PREFIX_PRIVATE_KEY__, __PREFIX_SHORT_ID__,
and optionally __PREFIX_PUBLIC_KEY__ in the state file.

Usage: vps remnawave gen-keys --prefix REALITY2 [--node node-1]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

STATE_FILE = "remnawave-config/state.yml"


def _find_project_root() -> Path:
    """Walk up from cwd to find pyproject.toml."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def _load_inventory(root: Path) -> dict:
    """Load nodes inventory to get SSH connection details."""
    inv_path = root / "ansible" / "inventories" / "nodes.yml"
    with open(inv_path) as f:
        return yaml.safe_load(f)


def _get_node_ssh(inventory: dict, node_name: str | None) -> tuple[str, str, str]:
    """Get (host, user, key_file) for a node from inventory."""
    nodes_group = inventory["all"]["children"]["remnawave_nodes"]
    hosts = nodes_group["hosts"]
    group_vars = nodes_group.get("vars", {})

    if node_name:
        if node_name not in hosts:
            print(f"{RED}Node '{node_name}' not found in inventory{RESET}")
            sys.exit(1)
        node = hosts[node_name]
    else:
        node_name = next(iter(hosts))
        node = hosts[node_name]

    host = node["ansible_host"]
    user = node.get("ansible_user", group_vars.get("ansible_user", "root"))
    key_file = node.get(
        "ansible_ssh_private_key_file",
        group_vars.get("ansible_ssh_private_key_file", "~/.ssh/id_rsa"),
    )

    return host, user, key_file


def _ssh_cmd(host: str, user: str, key_file: str, command: str) -> str:
    """Run a command on a remote host via SSH."""
    result = subprocess.run(
        [
            "ssh",
            "-i", str(Path(key_file).expanduser()),
            "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"{RED}SSH command failed: {result.stderr.strip()}{RESET}")
        sys.exit(1)
    return result.stdout.strip()


def _generate_keys_on_node(host: str, user: str, key_file: str) -> dict[str, str]:
    """Generate x25519 keypair + short ID on a remote node."""
    print(f"{DIM}Generating keys on {host}...{RESET}")

    # Generate x25519 keypair via xray in the container
    output = _ssh_cmd(host, user, key_file, "docker exec remnanode xray x25519")

    keys: dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if "private" in key:
                keys["private_key"] = value
            elif "public" in key:
                keys["public_key"] = value

    if "private_key" not in keys:
        print(f"{RED}Failed to parse xray x25519 output:{RESET}")
        print(output)
        sys.exit(1)

    # Derive public key if not in output (some xray versions only show private)
    if "public_key" not in keys:
        derive_output = _ssh_cmd(
            host, user, key_file,
            f"docker exec remnanode xray x25519 -i {keys['private_key']}",
        )
        for line in derive_output.splitlines():
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                if "public" in k.strip().lower():
                    keys["public_key"] = v.strip()

    # Generate short ID
    short_id = _ssh_cmd(host, user, key_file, "openssl rand -hex 8")
    keys["short_id"] = short_id.strip()

    return keys


def _replace_placeholders(state_path: Path, prefix: str, keys: dict[str, str]) -> int:
    """Replace __PREFIX_*__ placeholders in state.yml. Returns count of replacements."""
    content = state_path.read_text()
    count = 0

    replacements = {
        f"__{prefix}_PRIVATE_KEY__": keys["private_key"],
        f"__{prefix}_SHORT_ID__": keys["short_id"],
    }
    if "public_key" in keys:
        replacements[f"__{prefix}_PUBLIC_KEY__"] = keys["public_key"]

    for placeholder, value in replacements.items():
        occurrences = content.count(placeholder)
        if occurrences > 0:
            content = content.replace(placeholder, value)
            count += occurrences

    if count > 0:
        state_path.write_text(content)

    return count


def _save_to_secrets(secrets_path: Path, prefix: str, keys: dict[str, str]) -> None:
    """Append generated keys to secrets.yml under a named section."""
    if not secrets_path.exists():
        print(f"{YELLOW}secrets.yml not found, skipping backup{RESET}")
        return

    content = secrets_path.read_text()
    section_key = f"reality_{prefix.lower()}"

    if section_key in content:
        print(f"  {YELLOW}'{section_key}' already in secrets.yml, skipping{RESET}")
        return

    block = f"\n# Reality keys: {prefix}\n"
    block += f"{section_key}_private_key: \"{keys['private_key']}\"\n"
    if "public_key" in keys:
        block += f"{section_key}_public_key: \"{keys['public_key']}\"\n"
    block += f"{section_key}_short_id: \"{keys['short_id']}\"\n"

    secrets_path.write_text(content + block)
    print(f"  {GREEN}✓{RESET} Keys saved to secrets.yml under '{section_key}_*'")


def main(prefix: str, node: str | None = None, save_secrets: bool = True) -> int:
    root = _find_project_root()
    state_path = root / STATE_FILE
    secrets_path = root / "secrets.yml"

    if not state_path.exists():
        print(f"{RED}State file not found: {state_path}{RESET}")
        return 1

    # Check if there are any placeholders to replace
    content = state_path.read_text()
    pattern = f"__{prefix}_"
    if pattern not in content:
        print(f"{YELLOW}No __{prefix}_*__ placeholders found in state.yml{RESET}")
        return 0

    # Get SSH details from inventory
    inventory = _load_inventory(root)
    host, user, key_file = _get_node_ssh(inventory, node)

    # Generate keys
    keys = _generate_keys_on_node(host, user, key_file)

    # Replace placeholders
    count = _replace_placeholders(state_path, prefix, keys)
    print(f"  {GREEN}✓{RESET} Replaced {count} placeholder(s) in state.yml")

    # Save to secrets.yml for reference
    if save_secrets:
        _save_to_secrets(secrets_path, prefix, keys)

    print(f"\n{BOLD}Done.{RESET} Run: vps remnawave sync --plan")
    return 0
