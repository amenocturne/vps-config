"""
Sync Remnawave panel state to match a declarative state.yml.

Modes:
  --plan (default): dry-run diff -- shows what would change
  --apply:          execute changes via httpx API calls
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import (
    api_delete,
    api_get,
    api_patch,
    api_post,
    create_client,
    fetch_panel_state,
    load_config,
)
from .models import HostState, NodeState, PanelState, load_state_file

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_SUPPORTS_COLOR: bool | None = None


def _color_supported() -> bool:
    global _SUPPORTS_COLOR
    if _SUPPORTS_COLOR is None:
        _SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return _SUPPORTS_COLOR


def _c(code: str, text: str) -> str:
    if not _color_supported():
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("1;33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def dim(t: str) -> str:
    return _c("2", t)


def bold(t: str) -> str:
    return _c("1", t)


# ---------------------------------------------------------------------------
# Diff data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class ResourceDiff:
    """Represents a single resource change."""

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
        """True when there are creates/updates/deletes (not just orphans)."""
        for section in ("config_profiles", "nodes", "hosts", "users"):
            for diff in getattr(self, section):
                if diff.action != "orphan":
                    return True
        return False


# ---------------------------------------------------------------------------
# Pure diff functions
# ---------------------------------------------------------------------------

# Fields to compare for each resource type. Only these trigger an "update".
# Transient / server-managed fields are excluded.

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
    """Return the list of field-level changes between desired and current."""
    changes: list[FieldChange] = []
    for f in fields:
        d_val = desired.get(f)
        c_val = current.get(f)
        if d_val != c_val:
            changes.append(FieldChange(field=f, old=c_val, new=d_val))
    return tuple(changes)


def _to_dict(obj: Any) -> dict[str, Any]:
    """Normalize a Pydantic model or dict to a plain dict for comparison."""
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
    """Generic diff for a resource section.

    Matching is by UUID. Items in desired that have no UUID are treated as
    creates. Items in current that are absent from desired are orphans (or
    deletes when --delete-missing is set).
    """
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
    """Compute the diff between desired (state.yml) and current (panel) state."""
    return SyncPlan(
        config_profiles=_compute_section_diff(
            desired.config_profiles,
            current.config_profiles,
            _CONFIG_PROFILE_FIELDS,
            name_field="name",
            delete_missing=delete_missing,
        ),
        nodes=_compute_section_diff(
            desired.nodes,
            current.nodes,
            _NODE_FIELDS,
            name_field="name",
            delete_missing=delete_missing,
        ),
        hosts=_compute_section_diff(
            desired.hosts,
            current.hosts,
            _HOST_FIELDS,
            name_field="remark",
            delete_missing=delete_missing,
        ),
        users=_compute_section_diff(
            desired.users,
            current.users,
            _USER_FIELDS,
            name_field="username",
            delete_missing=delete_missing,
        ),
    )


# ---------------------------------------------------------------------------
# Plan rendering
# ---------------------------------------------------------------------------

_ACTION_SYMBOLS = {
    "create": ("+", "32"),  # green
    "update": ("~", "33"),  # yellow
    "delete": ("-", "31"),  # red
    "orphan": ("?", "36"),  # cyan
}


def _format_field_change(fc: FieldChange) -> str:
    return f"{fc.field}: {fc.old!r} -> {fc.new!r}"


def _render_diff(diff: ResourceDiff) -> str:
    sym, color = _ACTION_SYMBOLS[diff.action]
    prefix = _c(color, f"  {sym}")
    label = diff.action

    detail_parts: list[str] = []
    if diff.action == "update" and diff.changes:
        detail_parts = [_format_field_change(c) for c in diff.changes]
    elif diff.action == "create":
        detail_parts = ["new"]
    elif diff.action == "orphan":
        detail_parts = ["exists in panel but not in state.yml"]

    detail = f" ({', '.join(detail_parts)})" if detail_parts else ""

    return f'{prefix} {label} "{diff.name}"{dim(detail)}'


def render_plan(plan: SyncPlan) -> str:
    lines: list[str] = []

    sections = [
        ("Config Profiles", plan.config_profiles),
        ("Nodes", plan.nodes),
        ("Hosts", plan.hosts),
        ("Users", plan.users),
    ]

    for title, diffs in sections:
        lines.append(f"\n{bold(title)}:")
        if not diffs:
            lines.append(dim("  (no changes)"))
        else:
            for d in diffs:
                lines.append(_render_diff(d))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apply logic -- all via httpx, no SDK imports
# ---------------------------------------------------------------------------


async def _apply_config_profiles(
    client: Any,
    diffs: list[ResourceDiff],
    desired_state: PanelState,
) -> tuple[list[str], dict[str, str]]:
    """Apply config profile changes. Returns (errors, uuid_remap).

    The Remnawave API has no PATCH endpoint for config profiles, so updates
    are performed as delete → create. This changes UUIDs, so a remapping dict
    is returned: {old_uuid → new_uuid} for both profile and inbound UUIDs.
    Callers must remap host/node references before applying them.
    """
    errors: list[str] = []
    uuid_remap: dict[str, str] = {}
    desired_by_uuid = {p.uuid: _to_dict(p) for p in desired_state.config_profiles}

    for diff in diffs:
        try:
            if diff.action == "create":
                d = desired_by_uuid.get(diff.uuid, {})
                await api_post(client, "/config-profiles", {
                    "name": d.get("name", diff.name),
                    "config": d.get("config", {}),
                })
                print(green(f'  [ok] Created config profile "{diff.name}"'))

            elif diff.action == "update":
                d = desired_by_uuid.get(diff.uuid, {})
                old_inbounds = d.get("inbounds", [])

                # Delete old profile (API has no PATCH for config profiles)
                await api_delete(client, f"/config-profiles/{diff.uuid}")

                # Recreate with desired config
                result = await api_post(client, "/config-profiles", {
                    "name": d.get("name", diff.name),
                    "config": d.get("config", {}),
                })

                # Build UUID remapping: old → new
                new_profile_uuid = result["uuid"]
                uuid_remap[diff.uuid] = new_profile_uuid

                new_inbounds = result.get("inbounds", [])
                for new_inb in new_inbounds:
                    for old_inb in old_inbounds:
                        if old_inb.get("tag") == new_inb["tag"]:
                            uuid_remap[old_inb["uuid"]] = new_inb["uuid"]
                            break

                print(green(f'  [ok] Updated config profile "{diff.name}" (delete + recreate)'))

            elif diff.action == "delete":
                await api_delete(client, f"/config-profiles/{diff.uuid}")
                print(green(f'  [ok] Deleted config profile "{diff.name}"'))

        except Exception as exc:
            msg = f'Config profile "{diff.name}": {exc}'
            errors.append(msg)
            print(red(f"  [err] {msg}"))

    # Update internal squads that reference old inbound UUIDs
    if uuid_remap:
        try:
            resp = await api_get(client, "/internal-squads")
            squads = resp.get("internalSquads", [])
            for squad in squads:
                old_inbound_uuids = [inb["uuid"] for inb in squad.get("inbounds", [])]
                new_inbound_uuids = [uuid_remap.get(u, u) for u in old_inbound_uuids]
                if old_inbound_uuids != new_inbound_uuids:
                    await api_patch(client, "/internal-squads", {
                        "uuid": squad["uuid"],
                        "inbounds": new_inbound_uuids,
                    })
                    print(green(f'  [ok] Updated internal squad "{squad["name"]}" with new inbound UUIDs'))
        except Exception as exc:
            msg = f"Internal squads update: {exc}"
            errors.append(msg)
            print(red(f"  [err] {msg}"))

    return errors, uuid_remap


def _build_inbound_tag_map(desired_state: PanelState) -> dict[str, str]:
    """Build a mapping of inbound tag → inbound UUID from all config profiles."""
    tag_map: dict[str, str] = {}
    for p in desired_state.config_profiles:
        d = _to_dict(p)
        for inb in d.get("inbounds", []):
            tag_map[inb["tag"]] = inb["uuid"]
    return tag_map


async def _apply_nodes(
    client: Any,
    diffs: list[ResourceDiff],
    desired_state: PanelState,
) -> list[str]:
    errors: list[str] = []
    desired_by_uuid = {n.uuid: _to_dict(n) for n in desired_state.nodes}
    tag_to_uuid = _build_inbound_tag_map(desired_state)

    for diff in diffs:
        try:
            if diff.action == "create":
                d = desired_by_uuid.get(diff.uuid, {})
                await api_post(client, "/nodes", {
                    "name": d["name"],
                    "address": d["address"],
                    "port": d.get("port"),
                    "countryCode": d.get("country_code", "XX"),
                    "isTrafficTrackingActive": d.get("is_traffic_tracking_active", False),
                    "consumptionMultiplier": d.get("consumption_multiplier", 1.0),
                })
                print(green(f'  [ok] Created node "{diff.name}"'))

            elif diff.action == "update":
                d = desired_by_uuid.get(diff.uuid, {})

                payload: dict[str, Any] = {
                    "uuid": diff.uuid,
                    "name": d.get("name"),
                    "address": d.get("address"),
                    "port": d.get("port"),
                    "countryCode": d.get("country_code"),
                    "isTrafficTrackingActive": d.get("is_traffic_tracking_active"),
                    "consumptionMultiplier": d.get("consumption_multiplier"),
                    "tags": d.get("tags"),
                }

                # Include config profile assignment if present
                profile_uuid = d.get("active_config_profile_uuid")
                inbound_tags = d.get("active_inbound_tags", [])
                if profile_uuid:
                    active_inbounds = [tag_to_uuid[t] for t in inbound_tags if t in tag_to_uuid]
                    payload["configProfile"] = {
                        "activeConfigProfileUuid": profile_uuid,
                        "activeInbounds": active_inbounds,
                    }

                await api_patch(client, "/nodes", payload)

                # Handle enable/disable via dedicated endpoints
                if d.get("is_disabled") is False:
                    await api_post(client, f"/nodes/{diff.uuid}/actions/enable", {})
                elif d.get("is_disabled") is True:
                    await api_post(client, f"/nodes/{diff.uuid}/actions/disable", {})

                print(green(f'  [ok] Updated node "{diff.name}"'))

            elif diff.action == "delete":
                await api_delete(client, f"/nodes/{diff.uuid}")
                print(green(f'  [ok] Deleted node "{diff.name}"'))

        except Exception as exc:
            msg = f'Node "{diff.name}": {exc}'
            errors.append(msg)
            print(red(f"  [err] {msg}"))

    return errors


async def _apply_hosts(
    client: Any,
    diffs: list[ResourceDiff],
    desired_state: PanelState,
) -> list[str]:
    errors: list[str] = []
    desired_by_uuid = {h.uuid: _to_dict(h) for h in desired_state.hosts}

    for diff in diffs:
        try:
            if diff.action == "create":
                d = desired_by_uuid.get(diff.uuid, {})
                inbound = d.get("inbound", {})
                await api_post(client, "/hosts", {
                    "remark": d.get("remark", diff.name),
                    "address": d.get("address", ""),
                    "port": d.get("port", 443),
                    "path": d.get("path"),
                    "sni": d.get("sni"),
                    "host": d.get("host"),
                    "alpn": d.get("alpn"),
                    "fingerprint": d.get("fingerprint"),
                    "securityLayer": d.get("security_layer", "DEFAULT"),
                    "isDisabled": d.get("is_disabled", False),
                    "isHidden": d.get("is_hidden", False),
                    "inbound": {
                        "configProfileUuid": inbound.get("config_profile_uuid"),
                        "configProfileInboundUuid": inbound.get("config_profile_inbound_uuid"),
                    },
                    "nodes": d.get("nodes", []),
                })
                print(green(f'  [ok] Created host "{diff.name}"'))

            elif diff.action == "update":
                d = desired_by_uuid.get(diff.uuid, {})
                inbound = d.get("inbound", {})
                # Strip None values — API rejects null for optional string fields
                payload = {
                    "uuid": diff.uuid,
                    "remark": d.get("remark"),
                    "address": d.get("address"),
                    "port": d.get("port"),
                    "path": d.get("path"),
                    "sni": d.get("sni"),
                    "host": d.get("host"),
                    "alpn": d.get("alpn"),
                    "fingerprint": d.get("fingerprint"),
                    "securityLayer": d.get("security_layer"),
                    "isDisabled": d.get("is_disabled"),
                    "isHidden": d.get("is_hidden"),
                    "inbound": {
                        "configProfileUuid": inbound.get("config_profile_uuid"),
                        "configProfileInboundUuid": inbound.get("config_profile_inbound_uuid"),
                    },
                    "nodes": d.get("nodes"),
                }
                # Strip None values — API rejects null for optional string fields
                payload = {k: v for k, v in payload.items() if v is not None}
                await api_patch(client, "/hosts", payload)
                print(green(f'  [ok] Updated host "{diff.name}"'))

            elif diff.action == "delete":
                await api_delete(client, f"/hosts/{diff.uuid}")
                print(green(f'  [ok] Deleted host "{diff.name}"'))

        except Exception as exc:
            msg = f'Host "{diff.name}": {exc}'
            errors.append(msg)
            print(red(f"  [err] {msg}"))

    return errors


async def _apply_users(
    client: Any,
    diffs: list[ResourceDiff],
    desired_state: PanelState,
) -> list[str]:
    errors: list[str] = []
    desired_by_uuid = {u.uuid: _to_dict(u) for u in desired_state.users}

    for diff in diffs:
        try:
            if diff.action == "create":
                d = desired_by_uuid.get(diff.uuid, {})
                await api_post(client, "/users", {
                    "username": d.get("username", diff.name),
                    "status": d.get("status"),
                    "trafficLimitBytes": d.get("traffic_limit_bytes", 0),
                    "trafficLimitStrategy": d.get("traffic_limit_strategy", "NO_RESET"),
                    "expireAt": d.get("expire_at"),
                    "telegramId": d.get("telegram_id"),
                    "email": d.get("email"),
                    "description": d.get("description"),
                    "tag": d.get("tag"),
                    "hwidDeviceLimit": d.get("hwid_device_limit"),
                })
                print(green(f'  [ok] Created user "{diff.name}"'))

            elif diff.action == "update":
                d = desired_by_uuid.get(diff.uuid, {})
                await api_patch(client, f"/users/{diff.uuid}", {
                    "uuid": diff.uuid,
                    "username": d.get("username"),
                    "status": d.get("status"),
                    "trafficLimitBytes": d.get("traffic_limit_bytes"),
                    "trafficLimitStrategy": d.get("traffic_limit_strategy"),
                    "expireAt": d.get("expire_at"),
                    "telegramId": d.get("telegram_id"),
                    "email": d.get("email"),
                    "description": d.get("description"),
                    "tag": d.get("tag"),
                    "hwidDeviceLimit": d.get("hwid_device_limit"),
                })
                print(green(f'  [ok] Updated user "{diff.name}"'))

            elif diff.action == "delete":
                await api_delete(client, f"/users/{diff.uuid}")
                print(green(f'  [ok] Deleted user "{diff.name}"'))

        except Exception as exc:
            msg = f'User "{diff.name}": {exc}'
            errors.append(msg)
            print(red(f"  [err] {msg}"))

    return errors


def _remap_desired_state(desired_state: PanelState, uuid_remap: dict[str, str]) -> PanelState:
    """Return a new PanelState with config profile/inbound UUIDs remapped.

    After a config profile delete+recreate, all UUIDs change. This updates
    host and node references so subsequent apply steps use the new UUIDs.
    """
    if not uuid_remap:
        return desired_state

    def remap(uuid: str | None) -> str | None:
        return uuid_remap.get(uuid, uuid) if uuid else uuid

    new_nodes = []
    for n in desired_state.nodes:
        d = _to_dict(n)
        d["active_config_profile_uuid"] = remap(d.get("active_config_profile_uuid"))
        new_nodes.append(NodeState(**d))

    new_hosts = []
    for h in desired_state.hosts:
        d = _to_dict(h)
        inbound = d.get("inbound") or {}
        inbound["config_profile_uuid"] = remap(inbound.get("config_profile_uuid"))
        inbound["config_profile_inbound_uuid"] = remap(inbound.get("config_profile_inbound_uuid"))
        d["inbound"] = inbound
        new_hosts.append(HostState(**d))

    return PanelState(
        config_profiles=desired_state.config_profiles,
        nodes=new_nodes,
        hosts=new_hosts,
        users=desired_state.users,
    )


async def apply_plan(
    client: Any,
    plan: SyncPlan,
    desired_state: PanelState,
) -> list[str]:
    """Execute the sync plan in dependency order. Returns all errors."""
    all_errors: list[str] = []

    # 1. Config profiles first (may produce UUID remapping from delete+recreate)
    profile_diffs = [d for d in plan.config_profiles if d.action != "orphan"]
    uuid_remap: dict[str, str] = {}
    if profile_diffs:
        print(f"\n{bold('Config Profiles')}:")
        errors, uuid_remap = await _apply_config_profiles(
            client, profile_diffs, desired_state,
        )
        all_errors.extend(errors)

    # Remap UUIDs in desired state if profiles were recreated
    if uuid_remap:
        print(f"\n  Remapping {len(uuid_remap)} UUID(s) after profile recreate...")
        desired_state = _remap_desired_state(desired_state, uuid_remap)

    # 2. Remaining resources in dependency order
    sections: list[tuple[str, list[ResourceDiff], Any]] = [
        ("Nodes", plan.nodes, _apply_nodes),
        ("Hosts", plan.hosts, _apply_hosts),
        ("Users", plan.users, _apply_users),
    ]

    for title, diffs, apply_fn in sections:
        actionable = [d for d in diffs if d.action != "orphan"]
        if not actionable:
            continue
        print(f"\n{bold(title)}:")
        errors = await apply_fn(client, actionable, desired_state)
        all_errors.extend(errors)

    return all_errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync-config",
        description="Sync Remnawave panel config to match a declarative state.yml",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--plan",
        action="store_const",
        const="plan",
        dest="mode",
        help="Show what would change without making mutations (default)",
    )
    mode.add_argument(
        "--apply",
        action="store_const",
        const="apply",
        dest="mode",
        help="Apply changes to make the panel match state.yml",
    )

    parser.add_argument(
        "--state",
        type=Path,
        default=Path("remnawave-config/state.yml"),
        help="Path to state.yml (default: remnawave-config/state.yml)",
    )
    parser.add_argument(
        "--delete-missing",
        action="store_true",
        default=False,
        help="Delete resources present in panel but absent from state.yml",
    )

    parser.set_defaults(mode="plan")
    return parser


async def _run(args: argparse.Namespace) -> int:
    from .client import find_project_root

    project_root = find_project_root()

    # Load desired state from YAML
    state_path = args.state
    if not state_path.is_absolute():
        state_path = project_root / state_path

    if not state_path.exists():
        print(red(f"State file not found: {state_path}"))
        return 1

    print(dim(f"Loading desired state from {state_path}"))
    desired = load_state_file(state_path)

    # Fetch current panel state via httpx
    config = load_config()
    panel_url = config["panel_url"]

    print(dim(f"Fetching current panel state from {panel_url}"))
    async with create_client(config["api_token"], panel_url) as client:
        try:
            current = await fetch_panel_state(client)
        except Exception as exc:
            print(red(f"Failed to fetch panel state: {exc}"))
            return 1

        # Compute diff
        plan = compute_sync_plan(desired, current, delete_missing=args.delete_missing)

        if args.mode == "plan":
            if not plan.has_changes:
                print(green("\nPanel is in sync with state.yml -- no changes needed."))
                return 0

            print(render_plan(plan))

            orphans = sum(
                1
                for section in ("config_profiles", "nodes", "hosts", "users")
                for d in getattr(plan, section)
                if d.action == "orphan"
            )
            if orphans:
                print(
                    yellow(
                        f"\n{orphans} resource(s) exist in panel but not in state.yml. "
                        "Use --delete-missing to include them in deletions."
                    )
                )
            return 0

        # --apply
        if not plan.has_mutations:
            print(green("\nPanel is in sync with state.yml -- nothing to apply."))
            return 0

        print(render_plan(plan))
        print()

        orphans_list = [
            d
            for section in ("config_profiles", "nodes", "hosts", "users")
            for d in getattr(plan, section)
            if d.action == "orphan"
        ]
        if orphans_list:
            print(
                yellow(
                    f"Warning: {len(orphans_list)} resource(s) in panel not in state.yml "
                    "(will NOT be deleted without --delete-missing):"
                )
            )
            for o in orphans_list:
                print(yellow(f'  ? "{o.name}" ({o.uuid})'))
            print()

        print(bold("Applying changes..."))
        errors = await apply_plan(client, plan, desired)

    if errors:
        print(red(f"\n{len(errors)} error(s) during apply:"))
        for e in errors:
            print(red(f"  - {e}"))
        return 1

    print(green("\nAll changes applied successfully."))
    return 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
