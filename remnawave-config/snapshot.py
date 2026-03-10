"""
Save Clash proxy configs locally for offline use.

Fetches subscription configs from the subscription page and saves them
as standalone Clash YAML files that can be imported directly into
Clash Verge as local profiles.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

from .client import create_client, api_get, find_project_root, load_config


def _snapshots_dir() -> Path:
    d = find_project_root() / "remnawave-config" / "snapshots"
    d.mkdir(exist_ok=True)
    return d


async def _snapshot(username: str | None = None) -> None:
    config = load_config()
    sub_url = config.get("subscription_url")
    if not sub_url:
        print("Error: 'remnawave_subscription_url' not set in secrets.yml", file=sys.stderr)
        sys.exit(1)

    async with create_client(config["api_token"], config["panel_url"]) as client:
        users_data = await api_get(client, "/users")

    users = users_data.get("users", [])

    if username:
        targets = [u for u in users if u["username"].lower() == username.lower()]
        if not targets:
            print(f"Error: user '{username}' not found", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [u for u in users if u.get("tag") == "MY"]
        if not targets:
            print("Error: no users with tag 'MY' found", file=sys.stderr)
            sys.exit(1)

    snapshots_dir = _snapshots_dir()
    root = find_project_root()
    saved = 0

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as http:
        for user in targets:
            short_uuid = user["shortUuid"]
            url = f"{sub_url.rstrip('/')}/{short_uuid}"

            try:
                resp = await http.get(url, headers={"User-Agent": "clash-verge/v2.0.0"})
                if resp.status_code != 200:
                    print(f"  ✗ {user['username']}: HTTP {resp.status_code}")
                    continue
            except httpx.HTTPError as e:
                print(f"  ✗ {user['username']}: {e}")
                continue

            save_path = snapshots_dir / f"{user['username'].lower()}.yml"
            save_path.write_text(resp.text)
            print(f"  ✓ {user['username']} → {save_path.relative_to(root)}")
            saved += 1

    if saved:
        print(f"\n{saved} snapshot(s) saved to {snapshots_dir.relative_to(root)}/")
        print("Import as local profile in Clash Verge for offline use.")
    else:
        print("\nNo snapshots saved.", file=sys.stderr)
        sys.exit(1)


def main(username: str | None = None) -> None:
    asyncio.run(_snapshot(username))
