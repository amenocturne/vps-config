"""
Shared API client helpers for Remnawave panel.

Provides token loading, httpx client creation, and panel state fetching.
Uses httpx directly rather than the remnawave SDK because the SDK models
don't match the panel API responses.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

from .models import (
    ConfigProfileState,
    HostInboundRef,
    HostState,
    InboundState,
    NodeState,
    PanelState,
    UserState,
)


def find_project_root() -> Path:
    """Walk up from CWD to find the project root (contains pyproject.toml)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    print("Error: could not find project root (no pyproject.toml found)", file=sys.stderr)
    sys.exit(1)


def get_secrets_path() -> Path:
    return find_project_root() / "secrets.yml"


def get_state_output_path() -> Path:
    return find_project_root() / "remnawave-config/state.yml"


def load_config() -> dict[str, str]:
    """Load panel_url and api_token from the root secrets.yml."""
    path = get_secrets_path()
    if not path.exists():
        print(f"Error: secrets file not found at {path}", file=sys.stderr)
        print("Run 'just secrets-init' to generate it.", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        secrets = yaml.safe_load(f)

    token = secrets.get("remnawave_api_token")
    if not token:
        print("Error: 'remnawave_api_token' not found in secrets file", file=sys.stderr)
        sys.exit(1)

    panel_url = secrets.get("remnawave_panel_url", "https://panel.amenocturne.space")
    if not panel_url:
        print("Error: 'remnawave_panel_url' not found in secrets file", file=sys.stderr)
        sys.exit(1)

    subscription_url = secrets.get("remnawave_subscription_url")

    return {"panel_url": str(panel_url), "api_token": str(token), "subscription_url": str(subscription_url) if subscription_url else None}


def create_client(token: str, panel_url: str) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with bearer auth and base_url configured."""
    return httpx.AsyncClient(
        base_url=f"{panel_url}/api",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


async def api_get(client: httpx.AsyncClient, endpoint: str) -> Any:
    """Fetch from the panel API, extracting the response payload."""
    resp = await client.get(endpoint)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", data)


async def api_post(client: httpx.AsyncClient, endpoint: str, payload: dict) -> Any:
    """POST to the panel API."""
    resp = await client.post(endpoint, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", data)


async def api_patch(client: httpx.AsyncClient, endpoint: str, payload: dict) -> Any:
    """PATCH the panel API."""
    resp = await client.patch(endpoint, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", data)


async def api_delete(client: httpx.AsyncClient, endpoint: str) -> Any:
    """DELETE from the panel API."""
    resp = await client.delete(endpoint)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", data)


# -- Mapping functions: raw API dicts -> Pydantic models --


def map_config_profile(raw: dict) -> ConfigProfileState:
    return ConfigProfileState(
        uuid=raw["uuid"],
        name=raw["name"],
        config=raw.get("config", {}),
        inbounds=[
            InboundState(
                uuid=inb["uuid"],
                tag=inb["tag"],
                type=inb["type"],
                network=inb.get("network"),
                security=inb.get("security"),
                port=int(inb["port"]) if inb.get("port") is not None else None,
            )
            for inb in raw.get("inbounds", [])
        ],
    )


def map_host(raw: dict) -> HostState:
    inbound_data = raw.get("inbound", {})
    return HostState(
        uuid=raw["uuid"],
        remark=raw["remark"],
        address=raw["address"],
        port=raw["port"],
        path=raw.get("path"),
        sni=raw.get("sni"),
        host=raw.get("host"),
        alpn=raw.get("alpn"),
        fingerprint=raw.get("fingerprint"),
        security_layer=raw.get("securityLayer", "DEFAULT"),
        is_disabled=raw.get("isDisabled", False),
        is_hidden=raw.get("isHidden", False),
        override_sni_from_address=raw.get("overrideSniFromAddress", False),
        allow_insecure=raw.get("allowInsecure", False),
        shuffle_host=raw.get("shuffleHost", False),
        mihomo_x25519=raw.get("mihomoX25519", False),
        server_description=raw.get("serverDescription"),
        tag=raw.get("tag"),
        inbound=HostInboundRef(
            config_profile_uuid=inbound_data.get("configProfileUuid"),
            config_profile_inbound_uuid=inbound_data.get("configProfileInboundUuid"),
        ),
        x_http_extra_params=raw.get("xHttpExtraParams"),
        mux_params=raw.get("muxParams"),
        sockopt_params=raw.get("sockoptParams"),
        nodes=raw.get("nodes", []),
    )


def map_node(raw: dict) -> NodeState:
    config_profile = raw.get("configProfile") or {}
    active_inbounds = config_profile.get("activeInbounds", [])

    return NodeState(
        uuid=raw["uuid"],
        name=raw["name"],
        address=raw["address"],
        port=raw.get("port"),
        country_code=raw["countryCode"],
        is_disabled=raw.get("isDisabled", False),
        is_traffic_tracking_active=raw.get("isTrafficTrackingActive", False),
        traffic_reset_day=raw.get("trafficResetDay"),
        traffic_limit_bytes=int(raw["trafficLimitBytes"]) if raw.get("trafficLimitBytes") is not None else None,
        notify_percent=raw.get("notifyPercent"),
        consumption_multiplier=raw.get("consumptionMultiplier", 1.0),
        active_config_profile_uuid=config_profile.get("activeConfigProfileUuid"),
        active_inbound_tags=[inb["tag"] for inb in active_inbounds],
        tags=raw.get("tags", []),
    )


def map_user(raw: dict) -> UserState:
    return UserState(
        uuid=raw["uuid"],
        short_uuid=raw["shortUuid"],
        username=raw["username"],
        status=raw["status"],
        traffic_limit_bytes=raw["trafficLimitBytes"],
        traffic_limit_strategy=raw["trafficLimitStrategy"],
        expire_at=raw["expireAt"],
        telegram_id=raw.get("telegramId"),
        email=raw.get("email"),
        description=raw.get("description"),
        tag=raw.get("tag"),
        hwid_device_limit=raw.get("hwidDeviceLimit"),
    )


async def fetch_panel_state(client: httpx.AsyncClient) -> PanelState:
    """Fetch all resources from the panel and build a PanelState."""
    profiles_data = await api_get(client, "/config-profiles")
    hosts_data = await api_get(client, "/hosts")
    nodes_data = await api_get(client, "/nodes")
    users_data = await api_get(client, "/users")

    return PanelState(
        config_profiles=[map_config_profile(p) for p in profiles_data.get("configProfiles", [])],
        hosts=[map_host(h) for h in hosts_data],
        nodes=[map_node(n) for n in nodes_data],
        users=[map_user(u) for u in users_data.get("users", [])],
    )
