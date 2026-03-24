import asyncio
import re
import struct
import logging

import httpx

from config import MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT, MINECRAFT_RCON_PASSWORD, MINECRAFT_MANAGER_PORT

logger = logging.getLogger(__name__)

_RCON_LOGIN = 3
_RCON_COMMAND = 2


async def _send_rcon(command: str) -> str:
    """Send an RCON command and return the response text."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(MINECRAFT_RCON_HOST, MINECRAFT_RCON_PORT),
            timeout=5.0,
        )
    except (OSError, asyncio.TimeoutError) as e:
        logger.warning("RCON connection failed: %s", e)
        raise ConnectionError("Cannot reach Minecraft server") from e

    try:
        # Login
        await _send_packet(writer, 1, _RCON_LOGIN, MINECRAFT_RCON_PASSWORD)
        resp_id, _ = await _read_packet(reader)
        if resp_id == -1:
            raise ConnectionError("RCON authentication failed")

        # Send command
        await _send_packet(writer, 2, _RCON_COMMAND, command)
        _, payload = await _read_packet(reader)
        return payload
    finally:
        writer.close()
        await writer.wait_closed()


async def _send_packet(writer: asyncio.StreamWriter, req_id: int, ptype: int, payload: str) -> None:
    data = struct.pack("<ii", req_id, ptype) + payload.encode("utf-8") + b"\x00\x00"
    writer.write(struct.pack("<i", len(data)) + data)
    await writer.drain()


async def _read_packet(reader: asyncio.StreamReader) -> tuple[int, str]:
    raw_len = await asyncio.wait_for(reader.readexactly(4), timeout=10.0)
    length = struct.unpack("<i", raw_len)[0]
    data = await asyncio.wait_for(reader.readexactly(length), timeout=10.0)
    req_id, ptype = struct.unpack("<ii", data[:8])
    payload = data[8:-2].decode("utf-8", errors="replace")
    return req_id, payload


async def whitelist_add(player: str) -> str:
    return await _send_rcon(f"whitelist add {player}")


async def whitelist_remove(player: str) -> str:
    return await _send_rcon(f"whitelist remove {player}")


async def whitelist_list() -> list[str]:
    response = await _send_rcon("whitelist list")
    # Response format: "There are N whitelisted players: player1, player2"
    # Or: "There are no whitelisted players"
    if ":" in response:
        names_part = response.split(":", 1)[1].strip()
        if names_part:
            return [n.strip() for n in names_part.split(",") if n.strip()]
    return []


async def list_online() -> tuple[int, list[str]]:
    response = await _send_rcon("list")
    # Response format: "There are N of a max of M players online: player1, player2"
    # Or: "There are 0 of a max of M players online:"
    parts = response.split(":", 1)
    players = []
    if len(parts) > 1 and parts[1].strip():
        players = [p.strip() for p in parts[1].split(",") if p.strip()]

    count = 0
    try:
        # Extract number from "There are N of a max..."
        count = int(parts[0].split()[2])
    except (IndexError, ValueError):
        count = len(players)

    return count, players


def _strip_color_codes(text: str) -> str:
    return re.sub(r"§[0-9a-fk-or]", "", text)


async def server_tps() -> tuple[float, float, float]:
    response = _strip_color_codes(await _send_rcon("tps"))
    # "TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0"
    try:
        values = response.split(":")[1].strip().split(",")
        return tuple(float(v.strip()) for v in values[:3])
    except (IndexError, ValueError):
        return (0.0, 0.0, 0.0)


async def server_mspt() -> tuple[float, float, float]:
    response = _strip_color_codes(await _send_rcon("mspt"))
    # "Server tick times (avg/min/max) from last 5s, 10s, 60s: ..."
    try:
        values_part = response.split(":")[1].strip()
        # Each segment looks like "avg/min/max" — we just want the avgs
        segments = [s.strip().split("/")[0] for s in values_part.split(",")]
        return tuple(float(s.strip()) for s in segments[:3])
    except (IndexError, ValueError):
        return (0.0, 0.0, 0.0)


async def server_status() -> dict:
    count, players = await list_online()
    tps = await server_tps()
    mspt = await server_mspt()
    return {
        "players_online": count,
        "players": players,
        "tps": tps,
        "mspt": mspt,
    }


async def check_rejected_logins() -> list[str]:
    """Query Prometheus for recent whitelist rejections."""
    import httpx
    from config import PROMETHEUS_URL
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": 'minecraft_rejected_login'},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                return []
            results = data.get("data", {}).get("result", [])
            return [r["metric"].get("player", "unknown") for r in results]
    except Exception:
        return []


_MANAGER_URL = f"http://{MINECRAFT_RCON_HOST}:{MINECRAFT_MANAGER_PORT}"


async def get_worlds() -> dict:
    """Get list of worlds and active world name."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_MANAGER_URL}/api/worlds")
        r.raise_for_status()
        return r.json()


async def get_seed() -> str:
    """Get current world seed."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_MANAGER_URL}/api/seed")
        r.raise_for_status()
        return r.json().get("seed", "unknown")


async def new_world(archive_name: str) -> dict:
    """Archive current world and generate a new one. Takes ~30-60s."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{_MANAGER_URL}/api/worlds/new", json={"archive_name": archive_name})
        r.raise_for_status()
        return r.json()


async def switch_world(name: str) -> dict:
    """Switch to a different world. Takes ~30-60s."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{_MANAGER_URL}/api/worlds/switch", json={"name": name})
        r.raise_for_status()
        return r.json()


async def delete_world(name: str) -> dict:
    """Delete an archived world."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(f"{_MANAGER_URL}/api/worlds/{name}")
        r.raise_for_status()
        return r.json()


async def is_online() -> bool:
    try:
        await _send_rcon("list")
        return True
    except (ConnectionError, asyncio.TimeoutError):
        return False
