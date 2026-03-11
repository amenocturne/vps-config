from __future__ import annotations

import asyncio

import yaml

from vps_cli.errors import ApiError

from .client import create_client, fetch_panel_state, get_state_output_path, load_config
from .models import PanelState


def serialize_state(state: PanelState) -> str:
    raw = state.model_dump(mode="json")

    return yaml.dump(
        raw,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


async def export_state() -> None:
    config = load_config()
    panel_url = config["panel_url"]

    print(f"Connecting to {panel_url}...")

    async with create_client(config["api_token"], panel_url) as client:
        try:
            state = await fetch_panel_state(client)
        except Exception as e:
            raise ApiError(f"Failed to fetch panel state: {e}") from e

    output = serialize_state(state)
    output_path = get_state_output_path()
    output_path.write_text(output)

    print(f"Exported {len(state.config_profiles)} profiles, {len(state.hosts)} hosts, "
          f"{len(state.nodes)} nodes, {len(state.users)} users")
    print(f"Written to {output_path}")


def main():
    asyncio.run(export_state())
