import base64

import httpx
from config import REMNAWAVE_API_URL, REMNAWAVE_API_TOKEN

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=REMNAWAVE_API_URL,
            headers={
                "Authorization": f"Bearer {REMNAWAVE_API_TOKEN}",
                "X-Forwarded-For": "127.0.0.1",
                "X-Forwarded-Proto": "https",
            },
            timeout=15.0,
        )
    return _client


async def get_users_by_telegram_id(tg_id: int) -> list[dict] | None:
    try:
        r = await _get_client().get(f"/users/by-telegram-id/{tg_id}")
        if r.status_code != 200:
            return None
        return r.json().get("response")
    except httpx.HTTPError:
        return None


async def get_subscription(short_uuid: str, client_type: str | None = None) -> str:
    if client_type == "raw":
        r = await _get_client().get(f"/sub/{short_uuid}")
        r.raise_for_status()
        return base64.b64decode(r.text.strip()).decode()
    path = f"/sub/{short_uuid}/{client_type}" if client_type else f"/sub/{short_uuid}"
    r = await _get_client().get(path)
    r.raise_for_status()
    return r.text


async def get_all_users() -> list[dict]:
    r = await _get_client().get("/users")
    r.raise_for_status()
    return r.json()["response"]["users"]


async def get_user_by_username(username: str) -> dict | None:
    try:
        r = await _get_client().get(f"/users/by-username/{username}")
        if r.status_code != 200:
            return None
        return r.json().get("response")
    except httpx.HTTPError:
        return None


async def ping() -> bool:
    try:
        r = await _get_client().get("/users?size=1")
        return r.status_code == 200
    except httpx.HTTPError:
        return False
