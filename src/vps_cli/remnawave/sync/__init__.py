from __future__ import annotations

import asyncio
from pathlib import Path

from vps_cli import find_project_root
from vps_cli.remnawave.client import create_client, fetch_panel_state, load_config
from vps_cli.remnawave.models import load_state_file
from vps_cli.util import bold, green, red, yellow

from .apply import apply_plan
from .diff import FieldChange, ResourceDiff, SyncPlan, compute_sync_plan
from .render import render_plan


async def run_sync(
    mode: str = "plan",
    state_path: Path | None = None,
    delete_missing: bool = False,
) -> int:
    project_root = find_project_root()

    if state_path is None:
        state_path = project_root / "remnawave-config/state.yml"
    elif not state_path.is_absolute():
        state_path = project_root / state_path

    if not state_path.exists():
        print(red(f"State file not found: {state_path}"))
        return 1

    from vps_cli.util import dim
    print(dim(f"Loading desired state from {state_path}"))
    desired = load_state_file(state_path)

    config = load_config()
    panel_url = config["panel_url"]

    print(dim(f"Fetching current panel state from {panel_url}"))
    async with create_client(config["api_token"], panel_url) as client:
        try:
            current = await fetch_panel_state(client)
        except Exception as exc:
            print(red(f"Failed to fetch panel state: {exc}"))
            return 1

        plan = compute_sync_plan(desired, current, delete_missing=delete_missing)

        if mode == "plan":
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
