from __future__ import annotations

import argparse

from vps_cli import find_project_root


def cmd_setup(_args: argparse.Namespace) -> int:
    root = find_project_root()
    production_inv = root / "ansible" / "inventories" / "production.yml"
    template_inv = root / "ansible" / "inventories" / "hosts.yml"

    if not production_inv.exists() and template_inv.exists():
        import shutil

        shutil.copy2(template_inv, production_inv)
        print(f"Created {production_inv.relative_to(root)} — customize with your VPS IP and domain")

    from vps_cli.secrets import setup_secrets

    return setup_secrets()
