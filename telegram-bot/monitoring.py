import logging

import httpx
from config import PROMETHEUS_URL

logger = logging.getLogger(__name__)

SERVERS = ["vps", "remnawave", "node-2", "home"]

SERVER_EMOJI = {
    "vps": "\U0001f5a5",  # desktop computer
    "remnawave": "\U0001f310",  # globe with meridians
    "node-2": "\U0001f517",  # link
    "home": "\U0001f3e0",  # house
}

SERVER_DISPLAY = {
    "vps": "VPS",
    "remnawave": "Remnawave",
    "node-2": "Node-2",
    "home": "Home",
}

_ALERT_CPU_THRESHOLD = 90.0
_ALERT_MEMORY_THRESHOLD = 85.0
_ALERT_DISK_THRESHOLD = 85.0

# Per-server memory overrides. node-2 is a 1 GiB VPS with baseline ~80%,
# so 85% fires on normal fluctuations — use 90% there.
_MEMORY_THRESHOLD_OVERRIDES: dict[str, float] = {
    "node-2": 90.0,
}

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=PROMETHEUS_URL,
            timeout=10.0,
        )
    return _client


async def query(promql: str) -> list[dict]:
    try:
        r = await _get_client().get("/api/v1/query", params={"query": promql})
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            logger.warning("Prometheus query failed: %s", data)
            return []
        return data.get("data", {}).get("result", [])
    except (httpx.HTTPError, Exception) as e:
        logger.warning("Prometheus unreachable: %s", e)
        return []


async def query_value(promql: str) -> float | None:
    results = await query(promql)
    if not results:
        return None
    try:
        return float(results[0]["value"][1])
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    s = int(seconds)
    if s >= 7 * 24 * 3600:
        weeks = s / (7 * 24 * 3600)
        return f"{weeks:.1f} weeks"
    if s >= 24 * 3600:
        days = s / (24 * 3600)
        return f"{days:.1f} days"
    hours = s / 3600
    return f"{hours:.1f} hours"


def _fmt(val: float | None) -> str:
    if val is None:
        return "n/a"
    return f"{val:.1f}%"


async def get_server_health(server: str) -> dict:
    cpu_q = f'100 - (avg(irate(node_cpu_seconds_total{{mode="idle",server="{server}"}}[5m])) * 100)'
    mem_q = f'(1 - node_memory_MemAvailable_bytes{{server="{server}"}} / node_memory_MemTotal_bytes{{server="{server}"}}) * 100'
    disk_q = (
        f'100 - (node_filesystem_avail_bytes{{fstype=~"ext4|xfs|btrfs|zfs|exfat|ntfs",'
        f'mountpoint!~"/etc/.*|/boot/efi",server="{server}"}} / '
        f'node_filesystem_size_bytes{{fstype=~"ext4|xfs|btrfs|zfs|exfat|ntfs",'
        f'mountpoint!~"/etc/.*|/boot/efi",server="{server}"}} * 100)'
    )
    containers_q = f'sum(docker_container_state{{state="running",server="{server}"}})'
    uptime_q = f'time() - node_boot_time_seconds{{server="{server}"}}'

    cpu = await query_value(cpu_q)
    memory = await query_value(mem_q)

    disk_results = await query(disk_q)
    disk = None
    if disk_results:
        try:
            disk = max(float(r["value"][1]) for r in disk_results)
        except (KeyError, IndexError, ValueError, TypeError):
            pass

    containers = await query_value(containers_q)
    uptime_seconds = await query_value(uptime_q)

    return {
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "containers": int(containers) if containers is not None else None,
        "uptime": _format_uptime(uptime_seconds),
    }


async def get_all_servers_health() -> dict[str, dict]:
    result = {}
    for server in SERVERS:
        result[server] = await get_server_health(server)
    return result


async def check_alerts() -> list[str]:
    alerts = []

    for server in SERVERS:
        name = SERVER_DISPLAY[server]

        cpu_q = f'100 - (avg(irate(node_cpu_seconds_total{{mode="idle",server="{server}"}}[5m])) * 100)'
        cpu = await query_value(cpu_q)
        if cpu is not None and cpu > _ALERT_CPU_THRESHOLD:
            alerts.append(
                f"{name}: CPU at {cpu:.1f}% (threshold: {_ALERT_CPU_THRESHOLD:.0f}%)"
            )

        mem_q = f'(1 - node_memory_MemAvailable_bytes{{server="{server}"}} / node_memory_MemTotal_bytes{{server="{server}"}}) * 100'
        memory = await query_value(mem_q)
        mem_threshold = _MEMORY_THRESHOLD_OVERRIDES.get(server, _ALERT_MEMORY_THRESHOLD)
        if memory is not None and memory > mem_threshold:
            alerts.append(
                f"{name}: Memory at {memory:.1f}% (threshold: {mem_threshold:.0f}%)"
            )

        disk_q = (
            f'100 - (node_filesystem_avail_bytes{{fstype=~"ext4|xfs|btrfs|zfs|exfat|ntfs",'
            f'mountpoint!~"/etc/.*|/boot/efi",server="{server}"}} / '
            f'node_filesystem_size_bytes{{fstype=~"ext4|xfs|btrfs|zfs|exfat|ntfs",'
            f'mountpoint!~"/etc/.*|/boot/efi",server="{server}"}} * 100)'
        )
        disk_results = await query(disk_q)
        for r in disk_results:
            try:
                val = float(r["value"][1])
                mount = r["metric"].get("mountpoint", "unknown")
                if val > _ALERT_DISK_THRESHOLD:
                    alerts.append(
                        f"{name}: Disk at {val:.1f}% on {mount} (threshold: {_ALERT_DISK_THRESHOLD:.0f}%)"
                    )
            except (KeyError, IndexError, ValueError, TypeError):
                continue

        exited_q = f'docker_container_state{{state="exited",server="{server}"}}'
        exited = await query(exited_q)
        for r in exited:
            container = r.get("metric", {}).get("container_name", "unknown")
            alerts.append(f'{name}: Container "{container}" is down')

    return alerts


def format_server_health(health: dict[str, dict]) -> str:
    lines = []
    for server in SERVERS:
        h = health.get(server, {})
        emoji = SERVER_EMOJI.get(server, "")
        name = SERVER_DISPLAY.get(server, server)
        cpu = _fmt(h.get("cpu"))
        ram = _fmt(h.get("memory"))
        disk = _fmt(h.get("disk"))
        containers = h.get("containers")
        containers_str = str(containers) if containers is not None else "n/a"
        uptime = h.get("uptime", "n/a")

        lines.append(f"{emoji} {name}")
        lines.append(f"  CPU: {cpu} | RAM: {ram} | Disk: {disk}")
        lines.append(f"  Containers: {containers_str} | Uptime: {uptime}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_alerts(alerts: list[str]) -> str:
    if not alerts:
        return "\u2705 No active alerts"
    parts = ["\U0001f6a8 Active Alerts:"]
    for a in alerts:
        parts.append(f"\u2022 {a}")
    return "\n".join(parts)


def format_daily_digest(health: dict[str, dict], alerts: list[str]) -> str:
    lines = ["\U0001f4cb Daily Infrastructure Report", ""]
    for server in SERVERS:
        h = health.get(server, {})
        emoji = SERVER_EMOJI.get(server, "")
        name = SERVER_DISPLAY.get(server, server)
        cpu = _fmt(h.get("cpu"))
        ram = _fmt(h.get("memory"))
        disk = _fmt(h.get("disk"))
        lines.append(f"{emoji} {name} \u2014 CPU: {cpu} | RAM: {ram} | Disk: {disk}")
    lines.append("")
    lines.append(format_alerts(alerts))
    return "\n".join(lines)
