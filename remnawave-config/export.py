"""
Export current Remnawave panel state to state.yml.

Connects to the panel API, fetches all resources, strips volatile fields,
and writes a clean YAML snapshot suitable for git-diffing.
"""

from __future__ import annotations

import asyncio
import sys

import yaml

from .client import (
    PANEL_URL,
    create_client,
    fetch_panel_state,
    get_state_output_path,
    load_api_token,
)
from .models import PanelState


def serialize_state(state: PanelState) -> str:
    """Serialize state to YAML with stable, human-readable output."""
    raw = state.model_dump(mode="json")

    return yaml.dump(
        raw,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


async def export_state() -> None:
    token = load_api_token()

    print(f"Connecting to {PANEL_URL}...")

    async with create_client(token) as client:
        try:
            state = await fetch_panel_state(client)
        except Exception as e:
            print(f"Failed to fetch panel state: {e}", file=sys.stderr)
            sys.exit(1)

    output = serialize_state(state)
    output_path = get_state_output_path()
    output_path.write_text(output)

    print(f"Exported {len(state.config_profiles)} profiles, {len(state.hosts)} hosts, "
          f"{len(state.nodes)} nodes, {len(state.users)} users")
    print(f"Written to {output_path}")


def main():
    asyncio.run(export_state())


if __name__ == "__main__":
    main()
