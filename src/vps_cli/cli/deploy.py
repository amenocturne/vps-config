from __future__ import annotations

import argparse
import sys

from vps_cli.ansible import TARGET_COMPONENTS, TARGETS, run_ansible
from vps_cli.util import BOLD, DIM, RESET


def _show_targets() -> None:
    print(f"\n{BOLD}Available targets:{RESET}\n")
    for name, cfg in TARGETS.items():
        components = TARGET_COMPONENTS.get(name)
        if components:
            comp_list = ", ".join(components)
            print(f"  {name:12s}  {DIM}{cfg['description']}{RESET}  [{comp_list}, all]")
        else:
            print(f"  {name:12s}  {DIM}{cfg['description']}{RESET}")
    print(f"\n  {DIM}Use: vps deploy <target> <component>{RESET}")
    print(f"  {DIM}Node shortcut: vps deploy node-N{RESET}\n")


def _show_components(target_name: str) -> None:
    components = TARGET_COMPONENTS.get(target_name, {})
    cfg = TARGETS[target_name]
    print(f"\n{BOLD}{target_name}{RESET} {DIM}({cfg['description']}){RESET} — specify a component:\n")
    for name in components:
        print(f"  {name}")
    print(f"  all         {DIM}deploy everything{RESET}")
    print(f"\n  {DIM}Usage: vps deploy {target_name} <component>{RESET}\n")


def cmd_deploy(args: argparse.Namespace) -> int:
    target_name = args.target
    component = args.component

    if target_name is None:
        _show_targets()
        return 0

    # node-N shortcut → deploy nodes with limit
    node_limit = None
    if target_name.startswith("node-"):
        node_limit = target_name
        target_name = "nodes"

    if target_name not in TARGETS:
        all_targets = list(TARGETS) + ["node-N"]
        print(f"Error: unknown target '{target_name}'", file=sys.stderr)
        print(f"Valid targets: {', '.join(all_targets)}", file=sys.stderr)
        return 1

    components = TARGET_COMPONENTS.get(target_name, {})

    # Target has components but none specified → show available
    if components and component is None and node_limit is None:
        _show_components(target_name)
        return 0

    # Validate component
    if component is not None and component != "all":
        if not components:
            print(f"Error: target '{target_name}' has no components", file=sys.stderr)
            return 1
        if component not in components:
            valid = list(components) + ["all"]
            print(f"Error: unknown component '{component}' for target '{target_name}'", file=sys.stderr)
            print(f"Valid components: {', '.join(valid)}", file=sys.stderr)
            return 1

    # Secrets check before actual deploy
    from vps_cli.secrets import check_secrets

    if check_secrets() != 0:
        print("\nSecrets check failed. Run 'vps secrets init' or 'vps setup' first.", file=sys.stderr)
        return 1

    # Resolve tag for component-specific deploy
    tags = None
    if component and component != "all":
        tags = components[component]

    cfg = TARGETS[target_name]
    print()
    return run_ansible(
        playbook=cfg["playbook"],
        inventory=cfg["inventory"],
        tags=tags,
        limit=node_limit,
        verbose=args.verbose,
        check=args.dry_run,
        syntax_check=args.check,
    )
