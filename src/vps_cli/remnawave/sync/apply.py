from __future__ import annotations

import asyncio
from typing import Any

from vps_cli.remnawave.client import api_delete, api_get, api_patch, api_post
from vps_cli.remnawave.models import ConfigProfileState, HostState, NodeState, PanelState
from vps_cli.util import bold, green, red, yellow, dim

from .diff import (
    ResourceDiff,
    SyncPlan,
    _build_inbound_tag_map,
    _compute_section_diff,
    _NODE_FIELDS,
    _to_dict,
)


async def _recreate_config_profile(
    client: Any,
    diff: ResourceDiff,
    desired_state: PanelState,
) -> tuple[dict[str, str], str | None]:
    uuid_remap: dict[str, str] = {}
    desired_by_uuid = {p.uuid: _to_dict(p) for p in desired_state.config_profiles}

    try:
        if diff.action == "create":
            d = desired_by_uuid.get(diff.uuid, {})
            result = await api_post(client, "/config-profiles", {
                "name": d.get("name", diff.name),
                "config": d.get("config", {}),
            })
            if diff.uuid:
                uuid_remap[diff.uuid] = result["uuid"]
            new_inbounds = result.get("inbounds", [])
            for new_inb in new_inbounds:
                for old_inb in d.get("inbounds", []):
                    if old_inb.get("tag") == new_inb["tag"]:
                        if old_inb.get("uuid"):
                            uuid_remap[old_inb["uuid"]] = new_inb["uuid"]
                        break
            print(green(f'  [ok] Created config profile "{diff.name}"'))
            return uuid_remap, None

        elif diff.action == "update":
            d = desired_by_uuid.get(diff.uuid, {})
            old_inbounds = d.get("inbounds", [])

            await api_delete(client, f"/config-profiles/{diff.uuid}")
            result = await api_post(client, "/config-profiles", {
                "name": d.get("name", diff.name),
                "config": d.get("config", {}),
            })

            new_profile_uuid = result["uuid"]
            uuid_remap[diff.uuid] = new_profile_uuid

            new_inbounds = result.get("inbounds", [])
            for new_inb in new_inbounds:
                for old_inb in old_inbounds:
                    if old_inb.get("tag") == new_inb["tag"]:
                        if old_inb.get("uuid"):
                            uuid_remap[old_inb["uuid"]] = new_inb["uuid"]
                        break

            print(green(f'  [ok] Updated config profile "{diff.name}" (delete + recreate)'))
            return uuid_remap, None

        elif diff.action == "delete":
            await api_delete(client, f"/config-profiles/{diff.uuid}")
            print(green(f'  [ok] Deleted config profile "{diff.name}"'))
            return uuid_remap, None

    except Exception as exc:
        msg = f'Config profile "{diff.name}": {exc}'
        print(red(f"  [err] {msg}"))
        return uuid_remap, msg

    return uuid_remap, None


async def _fix_squads_after_recreate(
    client: Any,
    uuid_remap: dict[str, str],
    new_inbound_uuids: list[str],
) -> str | None:
    try:
        resp = await api_get(client, "/internal-squads")
        squads = resp.get("internalSquads", [])
        if not squads:
            return None

        for squad in squads:
            current_uuids = [inb["uuid"] for inb in squad.get("inbounds", [])]
            remapped = [uuid_remap.get(u, u) for u in current_uuids]
            for uid in new_inbound_uuids:
                if uid not in remapped:
                    remapped.append(uid)

            if remapped != current_uuids:
                await api_patch(client, "/internal-squads", {
                    "uuid": squad["uuid"],
                    "inbounds": remapped,
                })
                print(green(f'  [ok] Updated squad "{squad["name"]}" ({len(remapped)} inbounds)'))

    except Exception as exc:
        msg = f"Squad fix: {exc}"
        print(red(f"  [err] {msg}"))
        return msg

    return None


async def _health_check_node(
    client: Any,
    node_uuid: str,
    node_name: str,
) -> bool:
    try:
        nodes_data = await api_get(client, "/nodes")
        for node in nodes_data:
            if node["uuid"] == node_uuid:
                is_connected = node.get("isConnected", False)
                is_disabled = node.get("isDisabled", False)
                xray_running = node.get("isXrayRunning", False)

                if is_connected and not is_disabled and xray_running:
                    print(green(f'  [ok] Node "{node_name}" healthy (connected, xray running)'))
                    return True

                status_parts = []
                if not is_connected:
                    status_parts.append("disconnected")
                if is_disabled:
                    status_parts.append("disabled")
                if not xray_running:
                    status_parts.append("xray not running")
                status = ", ".join(status_parts) if status_parts else "unknown"
                print(yellow(f'  [!] Node "{node_name}" not ready: {status}'))
                return False

        print(yellow(f'  [!] Node "{node_name}" not found in panel'))
        return False
    except Exception as exc:
        print(yellow(f'  [!] Health check failed for "{node_name}": {exc}'))
        return False


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

                profile_uuid = d.get("active_config_profile_uuid")
                inbound_tags = d.get("active_inbound_tags", [])
                if profile_uuid:
                    active_inbounds = [tag_to_uuid[t] for t in inbound_tags if t in tag_to_uuid]
                    payload["configProfile"] = {
                        "activeConfigProfileUuid": profile_uuid,
                        "activeInbounds": active_inbounds,
                    }

                await api_patch(client, "/nodes", payload)

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
                payload = {
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
                }
                payload = {k: v for k, v in payload.items() if v is not None}
                await api_post(client, "/hosts", payload)
                print(green(f'  [ok] Created host "{diff.name}"'))

            elif diff.action == "update":
                d = desired_by_uuid.get(diff.uuid, {})
                inbound = d.get("inbound", {})
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
    if not uuid_remap:
        return desired_state

    def remap(uuid: str | None) -> str | None:
        return uuid_remap.get(uuid, uuid) if uuid else uuid

    new_profiles = []
    for p in desired_state.config_profiles:
        d = _to_dict(p)
        d["uuid"] = remap(d.get("uuid"))
        new_inbounds = []
        for inb in d.get("inbounds", []):
            inb["uuid"] = remap(inb.get("uuid"))
            new_inbounds.append(inb)
        d["inbounds"] = new_inbounds
        new_profiles.append(ConfigProfileState(**d))

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
        config_profiles=new_profiles,
        nodes=new_nodes,
        hosts=new_hosts,
        users=desired_state.users,
    )


def _find_affected_nodes(profile_uuid: str, desired_state: PanelState) -> list[str]:
    return [
        _to_dict(n)["uuid"]
        for n in desired_state.nodes
        if _to_dict(n).get("active_config_profile_uuid") == profile_uuid
    ]


def _find_affected_hosts(
    profile_uuid: str,
    inbound_uuids: set[str],
    desired_state: PanelState,
) -> list[str]:
    affected = []
    for h in desired_state.hosts:
        d = _to_dict(h)
        inbound = d.get("inbound") or {}
        if (
            inbound.get("config_profile_uuid") == profile_uuid
            or inbound.get("config_profile_inbound_uuid") in inbound_uuids
        ):
            affected.append(d["uuid"])
    return affected


async def apply_plan(
    client: Any,
    plan: SyncPlan,
    desired_state: PanelState,
) -> list[str]:
    all_errors: list[str] = []
    full_uuid_remap: dict[str, str] = {}

    profile_diffs = [d for d in plan.config_profiles if d.action != "orphan"]

    for diff in profile_diffs:
        print(f"\n{bold(f'Config Profile: {diff.name}')}")

        old_inbound_uuids: set[str] = set()
        for p in desired_state.config_profiles:
            pd = _to_dict(p)
            if pd.get("uuid") == diff.uuid:
                old_inbound_uuids = {
                    inb["uuid"] for inb in pd.get("inbounds", []) if inb.get("uuid")
                }
                break

        affected_node_uuids = _find_affected_nodes(diff.uuid, desired_state)
        affected_host_uuids = _find_affected_hosts(
            diff.uuid, old_inbound_uuids, desired_state,
        )

        uuid_remap, error = await _recreate_config_profile(
            client, diff, desired_state,
        )
        if error:
            all_errors.append(error)
            print(red(f"\n  Profile recreate failed -- stopping rollout."))
            return all_errors

        full_uuid_remap.update(uuid_remap)

        if uuid_remap:
            desired_state = _remap_desired_state(desired_state, uuid_remap)

        new_profile_uuid = uuid_remap.get(diff.uuid, diff.uuid)
        new_inbound_uuids = []
        for p in desired_state.config_profiles:
            pd = _to_dict(p)
            if pd.get("uuid") == new_profile_uuid:
                new_inbound_uuids = [
                    inb["uuid"] for inb in pd.get("inbounds", []) if inb.get("uuid")
                ]
                break

        squad_err = await _fix_squads_after_recreate(
            client, uuid_remap, new_inbound_uuids,
        )
        if squad_err:
            all_errors.append(squad_err)

        if affected_node_uuids:
            tag_to_uuid = _build_inbound_tag_map(desired_state)
            desired_by_uuid = {n.uuid: _to_dict(n) for n in desired_state.nodes}

            for node_uuid in affected_node_uuids:
                d = desired_by_uuid.get(node_uuid)
                if not d:
                    continue
                try:
                    profile_uuid = d.get("active_config_profile_uuid")
                    inbound_tags = d.get("active_inbound_tags", [])
                    active_inbounds = [
                        tag_to_uuid[t] for t in inbound_tags if t in tag_to_uuid
                    ]

                    payload: dict[str, Any] = {
                        "uuid": node_uuid,
                        "name": d.get("name"),
                        "address": d.get("address"),
                        "port": d.get("port"),
                        "countryCode": d.get("country_code"),
                        "isTrafficTrackingActive": d.get("is_traffic_tracking_active"),
                        "consumptionMultiplier": d.get("consumption_multiplier"),
                        "tags": d.get("tags"),
                    }
                    if profile_uuid:
                        payload["configProfile"] = {
                            "activeConfigProfileUuid": profile_uuid,
                            "activeInbounds": active_inbounds,
                        }
                    await api_patch(client, "/nodes", payload)

                    if d.get("is_disabled") is False:
                        await api_post(client, f"/nodes/{node_uuid}/actions/enable", {})
                    elif d.get("is_disabled") is True:
                        await api_post(client, f"/nodes/{node_uuid}/actions/disable", {})

                    print(green(f'  [ok] Updated node "{d["name"]}"'))
                except Exception as exc:
                    msg = f'Node "{d.get("name", node_uuid)}": {exc}'
                    all_errors.append(msg)
                    print(red(f"  [err] {msg}"))
                    print(red(f"\n  Node update failed -- stopping rollout."))
                    return all_errors

        if affected_host_uuids:
            desired_hosts_by_uuid = {h.uuid: _to_dict(h) for h in desired_state.hosts}
            for host_uuid in affected_host_uuids:
                d = desired_hosts_by_uuid.get(host_uuid)
                if not d:
                    continue
                try:
                    inbound = d.get("inbound", {})
                    payload = {
                        "uuid": host_uuid,
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
                    payload = {k: v for k, v in payload.items() if v is not None}
                    await api_patch(client, "/hosts", payload)
                    print(green(f'  [ok] Updated host "{d["remark"]}"'))
                except Exception as exc:
                    msg = f'Host "{d.get("remark", host_uuid)}": {exc}'
                    all_errors.append(msg)
                    print(red(f"  [err] {msg}"))

        if affected_node_uuids:
            print(f"\n  {dim('Waiting for nodes to reconnect...')}")
            await asyncio.sleep(5)

            desired_by_uuid = {n.uuid: _to_dict(n) for n in desired_state.nodes}
            for node_uuid in affected_node_uuids:
                nd = desired_by_uuid.get(node_uuid, {})
                healthy = await _health_check_node(client, node_uuid, nd.get("name", "?"))
                if not healthy:
                    print(yellow(
                        f'\n  Node "{nd.get("name")}" not healthy after update.'
                        f" Pausing rollout -- check manually before continuing."
                    ))
                    if len(profile_diffs) > 1:
                        print(yellow("  Remaining profiles will NOT be updated."))
                        return all_errors

        print(green(f'  Profile "{diff.name}" rollout complete.'))

    remaining_sections: list[tuple[str, list[ResourceDiff], Any]] = [
        ("Nodes", plan.nodes, _apply_nodes),
        ("Hosts", plan.hosts, _apply_hosts),
        ("Users", plan.users, _apply_users),
    ]

    for title, diffs, apply_fn in remaining_sections:
        actionable = [d for d in diffs if d.action != "orphan"]
        if not actionable:
            continue
        print(f"\n{bold(title)}:")
        errors = await apply_fn(client, actionable, desired_state)
        all_errors.extend(errors)

    return all_errors
