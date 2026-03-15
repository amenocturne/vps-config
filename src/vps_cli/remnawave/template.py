from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from .client import api_get, api_patch, api_post, create_client, load_config

TEMPLATE_TYPE = "MIHOMO"


async def push_template(template_path: Path, name: str) -> None:
    config = load_config()
    async with create_client(config["api_token"], config["panel_url"]) as client:
        content = template_path.read_text()
        encoded = base64.b64encode(content.encode()).decode()

        data = await api_get(client, "/subscription-templates")
        templates = data.get("templates", [])

        existing = next(
            (
                t
                for t in templates
                if t["name"] == name and t["templateType"] == TEMPLATE_TYPE
            ),
            None,
        )

        if existing:
            await api_patch(
                client,
                "/subscription-templates",
                {
                    "uuid": existing["uuid"],
                    "encodedTemplateYaml": encoded,
                },
            )
            print(f"Updated template '{name}'")
        else:
            result = await api_post(
                client,
                "/subscription-templates",
                {
                    "name": name,
                    "templateType": TEMPLATE_TYPE,
                },
            )
            await api_patch(
                client,
                "/subscription-templates",
                {
                    "uuid": result["uuid"],
                    "encodedTemplateYaml": encoded,
                },
            )
            print(f"Created template '{name}'")


def main(template_path: Path, name: str) -> int:
    asyncio.run(push_template(template_path, name))
    return 0
