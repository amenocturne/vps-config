from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vps_cli.remnawave.models import PanelState


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class ResourceDiff:
    action: str  # "create", "update", "delete", "orphan"
    name: str
    uuid: str | None = None
    changes: tuple[FieldChange, ...] = ()


@dataclass
class SyncPlan:
    config_profiles: list[ResourceDiff] = field(default_factory=list)
    nodes: list[ResourceDiff] = field(default_factory=list)
    hosts: list[ResourceDiff] = field(default_factory=list)
    users: list[ResourceDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(
            len(getattr(self, sec)) > 0
            for sec in ("config_profiles", "nodes", "hosts", "users")
        )

    @property
    def has_mutations(self) -> bool:
        for section in ("config_profiles", "nodes", "hosts", "users"):
            for diff in getattr(self, section):
                if diff.action != "orphan":
                    return True
        return False


_CONFIG_PROFILE_FIELDS = ("name", "config")
_HOST_FIELDS = (
    "remark",
    "address",
    "port",
    "sni",
    "security_layer",
    "fingerprint",
    "alpn",
    "inbound",
    "nodes",
    "sockopt_params",
)
_NODE_FIELDS = (
    "name",
    "address",
    "port",
    "country_code",
    "is_disabled",
    "is_traffic_tracking_active",
    "consumption_multiplier",
    "active_config_profile_uuid",
    "active_inbound_tags",
    "tags",
)
_USER_FIELDS = (
    "username",
    "status",
    "traffic_limit_bytes",
    "traffic_limit_strategy",
    "expire_at",
    "short_uuid",
    "telegram_id",
    "email",
    "description",
    "tag",
    "hwid_device_limit",
)


def _diff_fields(
    desired: dict[str, Any],
    current: dict[str, Any],
    fields: tuple[str, ...],
) -> tuple[FieldChange, ...]:
    changes: list[FieldChange] = []
    for f in fields:
        d_val = desired.get(f)
        c_val = current.get(f)
        if d_val != c_val:
            changes.append(FieldChange(field=f, old=c_val, new=d_val))
    return tuple(changes)


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot convert {type(obj)} to dict")


def _compute_section_diff(
    desired_items: list[Any],
    current_items: list[Any],
    fields: tuple[str, ...],
    name_field: str,
    delete_missing: bool,
) -> list[ResourceDiff]:
    desired_by_uuid = {_to_dict(i)["uuid"]: _to_dict(i) for i in desired_items if _to_dict(i).get("uuid")}
    current_by_uuid = {_to_dict(i)["uuid"]: _to_dict(i) for i in current_items if _to_dict(i).get("uuid")}

    diffs: list[ResourceDiff] = []

    for item in desired_items:
        d = _to_dict(item)
        uuid = d.get("uuid")
        name = d.get(name_field, "<unnamed>")

        if not uuid or uuid not in current_by_uuid:
            diffs.append(ResourceDiff(action="create", name=name, uuid=uuid))
        else:
            changes = _diff_fields(d, current_by_uuid[uuid], fields)
            if changes:
                diffs.append(
                    ResourceDiff(action="update", name=name, uuid=uuid, changes=changes)
                )

    desired_uuids = {_to_dict(i)["uuid"] for i in desired_items if _to_dict(i).get("uuid")}
    for uuid, cur in current_by_uuid.items():
        if uuid not in desired_uuids:
            name = cur.get(name_field, "<unnamed>")
            action = "delete" if delete_missing else "orphan"
            diffs.append(ResourceDiff(action=action, name=name, uuid=uuid))

    return diffs


def compute_sync_plan(
    desired: PanelState,
    current: PanelState,
    delete_missing: bool = False,
) -> SyncPlan:
    return SyncPlan(
        config_profiles=_compute_section_diff(
            desired.config_profiles, current.config_profiles,
            _CONFIG_PROFILE_FIELDS, name_field="name", delete_missing=delete_missing,
        ),
        nodes=_compute_section_diff(
            desired.nodes, current.nodes,
            _NODE_FIELDS, name_field="name", delete_missing=delete_missing,
        ),
        hosts=_compute_section_diff(
            desired.hosts, current.hosts,
            _HOST_FIELDS, name_field="remark", delete_missing=delete_missing,
        ),
        users=_compute_section_diff(
            desired.users, current.users,
            _USER_FIELDS, name_field="username", delete_missing=delete_missing,
        ),
    )


def _build_inbound_tag_map(desired_state: PanelState) -> dict[str, str]:
    tag_map: dict[str, str] = {}
    for p in desired_state.config_profiles:
        d = _to_dict(p)
        for inb in d.get("inbounds", []):
            tag_map[inb["tag"]] = inb["uuid"]
    return tag_map
