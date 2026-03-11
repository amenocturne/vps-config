from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict


model_config = ConfigDict(frozen=True)


class InboundState(BaseModel):
    model_config = model_config

    uuid: Optional[str] = None
    tag: str
    type: str
    network: Optional[str] = None
    security: Optional[str] = None
    port: Optional[int] = None


class ConfigProfileState(BaseModel):
    model_config = model_config

    uuid: str
    name: str
    config: dict[str, Any]
    inbounds: list[InboundState]


class HostInboundRef(BaseModel):
    model_config = model_config

    config_profile_uuid: Optional[str] = None
    config_profile_inbound_uuid: Optional[str] = None


class HostState(BaseModel):
    model_config = model_config

    uuid: str
    remark: str
    address: str
    port: int
    path: Optional[str] = None
    sni: Optional[str] = None
    host: Optional[str] = None
    alpn: Optional[str] = None
    fingerprint: Optional[str] = None
    security_layer: str
    is_disabled: bool
    is_hidden: bool
    override_sni_from_address: bool
    allow_insecure: bool
    shuffle_host: bool
    mihomo_x25519: bool
    server_description: Optional[str] = None
    tag: Optional[str] = None
    inbound: HostInboundRef
    x_http_extra_params: Optional[dict[str, Any]] = None
    mux_params: Optional[dict[str, Any]] = None
    sockopt_params: Optional[dict[str, Any]] = None
    nodes: list[str]


class NodeState(BaseModel):
    model_config = model_config

    uuid: str
    name: str
    address: str
    port: Optional[int] = None
    country_code: str
    is_disabled: bool
    is_traffic_tracking_active: bool
    traffic_reset_day: Optional[int] = None
    traffic_limit_bytes: Optional[int] = None
    notify_percent: Optional[int] = None
    consumption_multiplier: float
    active_config_profile_uuid: Optional[str] = None
    active_inbound_tags: list[str]
    tags: list[str]


class UserState(BaseModel):
    model_config = model_config

    uuid: str
    short_uuid: str
    username: str
    status: str
    traffic_limit_bytes: int
    traffic_limit_strategy: str
    expire_at: datetime
    telegram_id: Optional[int] = None
    email: Optional[str] = None
    description: Optional[str] = None
    tag: Optional[str] = None
    hwid_device_limit: Optional[int] = None


class PanelState(BaseModel):
    model_config = model_config

    config_profiles: list[ConfigProfileState]
    hosts: list[HostState]
    nodes: list[NodeState]
    users: list[UserState]


def load_state_file(path: Path) -> PanelState:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return PanelState.model_validate(raw)
