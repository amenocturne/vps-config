from __future__ import annotations

import asyncio
import copy
import re
from pathlib import Path
from typing import Any

import httpx
import yaml

from vps_cli import find_project_root
from vps_cli.errors import ApiError, VpsError
from vps_cli.util import BOLD, DIM, GREEN, RED, RESET, YELLOW

from .client import api_get, api_patch, api_post, create_client, load_config

DEFAULT_VLESS_PORT = 443
DEFAULT_REALITY_PORT = 8443
DEFAULT_SS_PORT = 8388
DEFAULT_APP_PORT = 2222


def _step(n: int, msg: str) -> None:
    print(f"\n{BOLD}[{n}]{RESET} {msg}")


def _ok(msg: str) -> None:
    print(f"  {GREEN}v{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def _err(msg: str) -> None:
    print(f"  {RED}x{RESET} {msg}")


def _info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def _next_node_id(inventory_path: Path) -> str:
    if not inventory_path.exists():
        return "node-1"

    content = inventory_path.read_text()
    existing = re.findall(r"node-(\d+):", content)
    if not existing:
        return "node-1"

    max_n = max(int(n) for n in existing)
    return f"node-{max_n + 1}"


def _needs_custom_profile(vless_port: int, reality_port: int) -> bool:
    return vless_port != DEFAULT_VLESS_PORT or reality_port != DEFAULT_REALITY_PORT


def _clone_config_for_ports(
    base_config: dict[str, Any],
    vless_port: int,
    reality_port: int,
    ss_port: int,
) -> dict[str, Any]:
    config = copy.deepcopy(base_config)

    for inbound in config.get("inbounds", []):
        tag = inbound.get("tag", "").upper()

        if "WS" in tag and "VLESS" in tag:
            inbound["port"] = vless_port
            inbound["tag"] = f"VLESS_WS_TLS_{vless_port}"
        elif "REALITY" in tag or ("TCP" in tag and "VLESS" in tag):
            inbound["port"] = reality_port
            inbound["tag"] = f"VLESS_TCP_REALITY_{reality_port}"
        elif "SHADOWSOCKS" in tag or tag.startswith("SS"):
            inbound["port"] = ss_port

    return config


async def _fetch_inbounds(client: httpx.AsyncClient) -> list[dict]:
    data = await api_get(client, "/config-profiles/inbounds")
    return data.get("inbounds", [])


def _extract_profiles(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("configProfiles", [])
    return []


async def _find_or_create_profile(
    client: httpx.AsyncClient,
    profiles: list[dict],
    vless_port: int,
    reality_port: int,
    ss_port: int,
    profile_name: str,
) -> tuple[str, list[str]]:
    if not _needs_custom_profile(vless_port, reality_port):
        if not profiles:
            raise VpsError("No config profiles found in panel")

        profile = profiles[0]
        profile_uuid = profile["uuid"]
        inbound_uuids = [inb["uuid"] for inb in profile.get("inbounds", [])]
        _ok(f"Using existing profile: {profile['name']} ({len(inbound_uuids)} inbounds)")
        return profile_uuid, inbound_uuids

    for profile in profiles:
        inbounds = profile.get("inbounds", [])
        ports = {inb.get("port") for inb in inbounds}
        if vless_port in ports and reality_port in ports:
            profile_uuid = profile["uuid"]
            inbound_uuids = [inb["uuid"] for inb in inbounds]
            _ok(f"Found existing profile for ports {vless_port}/{reality_port}: {profile['name']}")
            return profile_uuid, inbound_uuids

    if not profiles:
        raise VpsError("No config profiles to clone from")

    base = profiles[0]
    new_config = _clone_config_for_ports(base["config"], vless_port, reality_port, ss_port)

    _info(f"Creating config profile '{profile_name}' with ports {vless_port}/{reality_port}...")

    try:
        result = await api_post(client, "/config-profiles", {
            "name": profile_name,
            "config": new_config,
        })
        profile_uuid = result["uuid"]
        inbound_uuids = [inb["uuid"] for inb in result.get("inbounds", [])]
        _ok(f"Created profile: {profile_name} ({len(inbound_uuids)} inbounds)")
        return profile_uuid, inbound_uuids
    except httpx.HTTPStatusError as e:
        raise ApiError(f"Failed to create config profile: {e.response.status_code} {e.response.text}") from e


async def _create_or_find_node(
    client: httpx.AsyncClient,
    name: str,
    ip: str,
    country: str,
    app_port: int,
    profile_uuid: str,
    inbound_uuids: list[str],
) -> tuple[str, str | None]:
    nodes_data = await api_get(client, "/nodes")
    for node in nodes_data:
        if node["address"] == ip:
            node_uuid = node["uuid"]
            _warn(f"Node already exists: {node['name']} ({node_uuid})")

            _info("Updating config profile assignment...")
            try:
                await api_patch(client, "/nodes", {
                    "uuid": node_uuid,
                    "configProfile": {
                        "activeConfigProfileUuid": profile_uuid,
                        "activeInbounds": inbound_uuids,
                    },
                })
                _ok(f"Assigned profile with {len(inbound_uuids)} active inbounds")
            except httpx.HTTPStatusError as e:
                _err(f"Failed to update node: {e.response.status_code} {e.response.text}")

            return node_uuid, None

    _info(f"Registering node '{name}' at {ip}...")
    try:
        result = await api_post(client, "/nodes", {
            "name": name,
            "address": ip,
            "port": app_port,
            "countryCode": country,
            "configProfile": {
                "activeConfigProfileUuid": profile_uuid,
                "activeInbounds": inbound_uuids,
            },
        })
        node_uuid = result["uuid"]
        connection_key = (
            result.get("secretKey")
            or result.get("connectionKey")
            or result.get("secret_key")
            or result.get("token")
        )
        _ok(f"Node created: {name} ({node_uuid})")
        return node_uuid, connection_key
    except httpx.HTTPStatusError as e:
        raise ApiError(f"Failed to create node: {e.response.status_code} {e.response.text}") from e


async def _ensure_squad_membership(
    client: httpx.AsyncClient,
    inbound_uuids: list[str],
) -> None:
    all_inbounds = await _fetch_inbounds(client)
    inbound_squads = {
        inb["uuid"]: inb.get("activeSquads", [])
        for inb in all_inbounds
    }

    missing = [uid for uid in inbound_uuids if not inbound_squads.get(uid)]
    if not missing:
        _ok("All inbounds already in a squad")
        return

    try:
        squads_data = await api_get(client, "/internal-squads")
    except httpx.HTTPStatusError:
        _warn("Could not fetch internal squads -- enable inbounds manually in panel UI")
        return

    squads = squads_data.get("internalSquads", [])
    if not squads:
        _warn("No internal squads found -- create one in panel UI and add inbounds")
        return

    squad = squads[0]
    squad_uuid = squad["uuid"]
    existing_inbound_uuids = [inb["uuid"] for inb in squad.get("inbounds", [])]
    all_uuids = existing_inbound_uuids + missing

    try:
        await api_patch(client, "/internal-squads", {
            "uuid": squad_uuid,
            "inbounds": all_uuids,
        })
        _ok(f"Added {len(missing)} inbound(s) to squad '{squad['name']}'")
    except httpx.HTTPStatusError as e:
        _err(f"Failed to update squad: {e.response.status_code} {e.response.text}")
        _warn("Enable inbounds manually: Panel -> Config Profiles -> check the inbounds")


def _domain_to_suffix(domain: str) -> str:
    return domain.split(".")[0]


async def _create_hosts(
    client: httpx.AsyncClient,
    node_uuid: str,
    ip: str,
    domain: str,
    profile_uuid: str,
    inbound_uuids: list[str],
    all_inbounds: list[dict],
    vless_port: int,
    reality_port: int,
) -> None:
    existing_hosts = await api_get(client, "/hosts")
    existing_by_remark = {h["remark"]: h for h in existing_hosts}

    inbound_map = {inb["uuid"]: inb for inb in all_inbounds if inb["uuid"] in inbound_uuids}

    suffix = _domain_to_suffix(domain)

    for inb_uuid in inbound_uuids:
        inb = inbound_map.get(inb_uuid)
        if not inb:
            continue

        tag = inb.get("tag", "").upper()
        network = inb.get("network", "").lower()
        security = inb.get("security", "").lower()

        is_ws = "ws" in network or "WS" in tag
        is_reality = "reality" in security or "REALITY" in tag

        if is_ws:
            remark = f"ws-{suffix}"
            host_config = {
                "inbound": {
                    "configProfileUuid": profile_uuid,
                    "configProfileInboundUuid": inb_uuid,
                },
                "remark": remark,
                "address": domain,
                "port": vless_port,
                "path": "/api/v2/ws",
                "sni": domain,
                "host": domain,
                "alpn": "h2,http/1.1",
                "fingerprint": "chrome",
                "securityLayer": "TLS",
                "nodes": [node_uuid],
            }
        elif is_reality:
            remark = f"reality-{suffix}"
            host_config = {
                "inbound": {
                    "configProfileUuid": profile_uuid,
                    "configProfileInboundUuid": inb_uuid,
                },
                "remark": remark,
                "address": ip,
                "port": reality_port,
                "sni": "search.brave.com",
                "fingerprint": "chrome",
                "securityLayer": "DEFAULT",
                "nodes": [node_uuid],
            }
        else:
            _info(f"Skipping host for inbound '{inb.get('tag', '?')}' (not WS or Reality)")
            continue

        if remark in existing_by_remark:
            existing = existing_by_remark[remark]
            existing_nodes = existing.get("nodes", [])
            node_ids = [n["uuid"] if isinstance(n, dict) else n for n in existing_nodes]

            if node_uuid in node_ids:
                _ok(f"Host '{remark}' already associated with this node")
                continue

            node_ids.append(node_uuid)
            try:
                await api_patch(client, "/hosts", {
                    "uuid": existing["uuid"],
                    "nodes": node_ids,
                })
                _ok(f"Added node to existing host '{remark}'")
            except httpx.HTTPStatusError as e:
                _err(f"Failed to update host '{remark}': {e.response.status_code}")
            continue

        try:
            await api_post(client, "/hosts", host_config)
            _ok(f"Created host: {remark}")
        except httpx.HTTPStatusError as e:
            _err(f"Failed to create host '{remark}': {e.response.status_code} {e.response.text}")


def _update_inventory(
    inventory_path: Path,
    node_id: str,
    ip: str,
    name: str,
    domain: str,
    vless_port: int,
    reality_port: int,
) -> None:
    if inventory_path.exists():
        content = inventory_path.read_text()
        if f"{node_id}:" in content:
            _warn(f"Node '{node_id}' already in inventory, skipping")
            return
    else:
        _err(f"Inventory not found: {inventory_path}")
        return

    lines = [
        "",
        f"        {node_id}:",
        f"          ansible_host: {ip}",
        f'          node_name: "{name}"',
        f'          vless_ws_domain: "{domain}"',
    ]

    if vless_port != DEFAULT_VLESS_PORT:
        lines.append(f"          remnawave_node_vless_port: {vless_port}")
    if reality_port != DEFAULT_REALITY_PORT:
        lines.append(f"          remnawave_node_reality_port: {reality_port}")

    block = "\n".join(lines) + "\n"

    content = inventory_path.read_text()
    vars_match = re.search(r"\n(\s+)vars:", content)
    if vars_match:
        insert_pos = vars_match.start()
        new_content = content[:insert_pos] + block + content[insert_pos:]
        inventory_path.write_text(new_content)
    else:
        inventory_path.write_text(content + block)

    _ok(f"Added {node_id} to inventory")


def _save_secret_key(secrets_path: Path, node_id: str, key: str) -> None:
    if not secrets_path.exists():
        _err(f"secrets.yml not found at {secrets_path}")
        return

    content = secrets_path.read_text()

    if f"{node_id}:" in content:
        _warn(f"Key for '{node_id}' already in secrets.yml")
        return

    pattern = r"(node_secret_keys:\s*\n(?:\s+\S+:.*\n)*)"
    match = re.search(pattern, content)
    if match:
        insert_pos = match.end()
        indent = "  "
        new_line = f'{indent}{node_id}: "{key}"\n'
        new_content = content[:insert_pos] + new_line + content[insert_pos:]
        secrets_path.write_text(new_content)
        _ok(f"Saved connection key for {node_id}")
    else:
        _warn("Could not find node_secret_keys section in secrets.yml")
        print(f'  Add manually: node_secret_keys.{node_id}: "{key}"')


def _get_existing_key(secrets_path: Path, node_id: str) -> str | None:
    if not secrets_path.exists():
        return None
    with open(secrets_path) as f:
        secrets = yaml.safe_load(f) or {}
    keys = secrets.get("node_secret_keys", {})
    val = keys.get(node_id)
    return val if val else None


async def _add_node(
    ip: str,
    name: str,
    country: str,
    domain: str,
    node_id: str | None = None,
    vless_port: int = DEFAULT_VLESS_PORT,
    reality_port: int = DEFAULT_REALITY_PORT,
    ss_port: int = DEFAULT_SS_PORT,
) -> None:
    root = find_project_root()
    config = load_config()
    inventory_path = root / "ansible" / "inventories" / "nodes.yml"
    secrets_path = root / "secrets.yml"

    if not node_id:
        node_id = _next_node_id(inventory_path)

    custom_ports = _needs_custom_profile(vless_port, reality_port)
    profile_name = f"{node_id}-altports" if custom_ports else "default"

    print(f"\n{BOLD}Adding node: {name}{RESET}")
    print(f"  IP: {ip}  |  Country: {country}  |  Domain: {domain}")
    print(f"  Ports: VLESS={vless_port}, Reality={reality_port}")
    print(f"  Node ID: {node_id}")

    async with create_client(config["api_token"], config["panel_url"]) as client:
        _step(1, "Config profile")
        profiles_data = await api_get(client, "/config-profiles")
        profiles = _extract_profiles(profiles_data)

        profile_uuid, inbound_uuids = await _find_or_create_profile(
            client, profiles, vless_port, reality_port, ss_port, profile_name,
        )

        all_inbounds = await _fetch_inbounds(client)

        _step(2, "Node registration")
        node_uuid, connection_key = await _create_or_find_node(
            client, name, ip, country, DEFAULT_APP_PORT,
            profile_uuid, inbound_uuids,
        )

        _step(3, "Connection key")
        if connection_key:
            _ok("Key obtained from API")
            _save_secret_key(secrets_path, node_id, connection_key)
        else:
            existing_key = _get_existing_key(secrets_path, node_id)
            if existing_key:
                _ok("Key already in secrets.yml")
            else:
                print(f"\n  {YELLOW}Manual step required:{RESET}")
                print(f"  1. Go to {BOLD}{config['panel_url']}{RESET} -> Nodes")
                print(f"  2. Find '{name}' and copy the connection key")
                print(f"  3. Paste it below\n")

                try:
                    key = input("  Connection key: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    raise VpsError("Aborted")

                if key:
                    _save_secret_key(secrets_path, node_id, key)
                else:
                    _warn("No key provided -- add manually to secrets.yml later")
                    print(f"  node_secret_keys:")
                    print(f'    {node_id}: "<connection-key>"')

        _step(4, "Internal squad")
        await _ensure_squad_membership(client, inbound_uuids)

        _step(5, "Subscription hosts")
        await _create_hosts(
            client, node_uuid, ip, domain,
            profile_uuid, inbound_uuids, all_inbounds,
            vless_port, reality_port,
        )

    _step(6, "Inventory")
    _update_inventory(
        inventory_path, node_id, ip, name, domain,
        vless_port, reality_port,
    )

    tags_note = ""
    if custom_ports:
        tags_note = " --tags node"
        print(f"\n  {DIM}Use --tags node to skip security role on shared servers{RESET}")

    print(f"\n{BOLD}Done!{RESET} Deploy with:\n")
    print(f"  {GREEN}vps deploy {node_id}{tags_note}{RESET}\n")


def main(
    ip: str,
    name: str,
    country: str,
    domain: str,
    node_id: str | None = None,
    vless_port: int = DEFAULT_VLESS_PORT,
    reality_port: int = DEFAULT_REALITY_PORT,
) -> None:
    asyncio.run(_add_node(
        ip=ip, name=name, country=country, domain=domain,
        node_id=node_id, vless_port=vless_port, reality_port=reality_port,
    ))
