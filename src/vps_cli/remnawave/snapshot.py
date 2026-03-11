from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx

from vps_cli import find_project_root
from vps_cli.errors import ConfigError, VpsError

from .client import api_get, create_client, load_config

USER_AGENTS = {
    "clash": "clash-verge/v2.0.0",
    "hiddify": "HiddifyNext/2.0.0",
}


def _snapshots_dir() -> Path:
    d = find_project_root() / "remnawave-config" / "snapshots"
    d.mkdir(exist_ok=True)
    return d


async def _fetch_users(config: dict, username: str | None) -> list[dict]:
    async with create_client(config["api_token"], config["panel_url"]) as client:
        users_data = await api_get(client, "/users")

    users = users_data.get("users", [])

    if username:
        targets = [u for u in users if u["username"].lower() == username.lower()]
        if not targets:
            raise VpsError(f"User '{username}' not found")
        return targets

    targets = [u for u in users if u.get("tag") == "MY"]
    if not targets:
        raise VpsError("No users with tag 'MY' found")
    return targets


async def _snapshot(username: str | None = None, fmt: str = "clash") -> None:
    config = load_config()
    sub_url = config.get("subscription_url")
    if not sub_url:
        raise ConfigError("'remnawave_subscription_url' not set in secrets.yml")

    targets = await _fetch_users(config, username)
    user_agent = USER_AGENTS.get(fmt, USER_AGENTS["clash"])

    if fmt == "hiddify":
        await _snapshot_hiddify(targets, sub_url, user_agent)
    else:
        await _snapshot_clash(targets, sub_url, user_agent)


async def _snapshot_clash(targets: list[dict], sub_url: str, user_agent: str) -> None:
    snapshots_dir = _snapshots_dir()
    root = find_project_root()
    saved = 0

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as http:
        for user in targets:
            short_uuid = user["shortUuid"]
            url = f"{sub_url.rstrip('/')}/{short_uuid}"

            try:
                resp = await http.get(url, headers={"User-Agent": user_agent})
                if resp.status_code != 200:
                    print(f"  x {user['username']}: HTTP {resp.status_code}")
                    continue
            except httpx.HTTPError as e:
                print(f"  x {user['username']}: {e}")
                continue

            save_path = snapshots_dir / f"{user['username'].lower()}.yml"
            save_path.write_text(resp.text)
            print(f"  v {user['username']} -> {save_path.relative_to(root)}")
            saved += 1

    if saved:
        print(f"\n{saved} snapshot(s) saved to {snapshots_dir.relative_to(root)}/")
        print("Import as local profile in Clash Verge for offline use.")
    else:
        raise VpsError("No snapshots saved.")


async def _snapshot_hiddify(targets: list[dict], sub_url: str, user_agent: str) -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as http:
        for user in targets:
            short_uuid = user["shortUuid"]
            url = f"{sub_url.rstrip('/')}/{short_uuid}"

            try:
                resp = await http.get(url, headers={"User-Agent": user_agent})
                if resp.status_code != 200:
                    print(f"  x {user['username']}: HTTP {resp.status_code}")
                    continue
            except httpx.HTTPError as e:
                print(f"  x {user['username']}: {e}")
                continue

            body = resp.text.strip()

            # Remnawave returns base64-encoded v2ray URIs for non-Clash clients
            try:
                decoded = base64.b64decode(body).decode()
            except Exception:
                decoded = body

            if len(targets) > 1:
                print(f"--- {user['username']} ---")
            print(decoded)


def main(username: str | None = None, fmt: str = "clash") -> None:
    asyncio.run(_snapshot(username, fmt))
