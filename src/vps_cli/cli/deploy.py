from __future__ import annotations

import argparse
import sys

from vps_cli.ansible import ROLE_TARGETS, TARGETS, run_ansible
from vps_cli.util import DIM, RESET


def _pick_deploy_target() -> str | None:
    options = []
    for name, cfg in TARGETS.items():
        options.append((name, cfg["description"]))
    for name, (_, desc) in ROLE_TARGETS.items():
        options.append((name, desc))

    print("Deploy target:\n")
    for i, (name, desc) in enumerate(options, 1):
        print(f"  {i}) {name:12s}  {DIM}{desc}{RESET}")
    print(f"\n  0) cancel\n")

    try:
        raw = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not raw or raw == "0":
        return None

    try:
        idx = int(raw)
        if 1 <= idx <= len(options):
            return options[idx - 1][0]
    except ValueError:
        if raw in TARGETS or raw in ROLE_TARGETS:
            return raw

    print(f"Invalid selection: {raw}", file=sys.stderr)
    return None


def cmd_deploy(args: argparse.Namespace) -> int:
    from vps_cli.secrets import check_secrets

    if check_secrets() != 0:
        print("\nSecrets check failed. Run 'vps secrets init' or 'vps setup' first.", file=sys.stderr)
        return 1
    print()

    target_name = args.target
    if target_name is None:
        target_name = _pick_deploy_target()
        if target_name is None:
            return 0

    node_limit = None
    if target_name.startswith("node-"):
        node_limit = target_name
        target_name = "nodes"

    if target_name in ROLE_TARGETS:
        tag = ROLE_TARGETS[target_name][0]
        cfg = TARGETS["vps"]
        return run_ansible(
            playbook=cfg["playbook"],
            inventory=cfg["inventory"],
            tags=tag,
            verbose=args.verbose,
            check=args.dry_run,
            syntax_check=args.check,
        )

    if target_name not in TARGETS:
        all_targets = list(TARGETS) + list(ROLE_TARGETS) + ["node-N"]
        print(f"Error: unknown target '{target_name}'", file=sys.stderr)
        print(f"Valid targets: {', '.join(all_targets)}", file=sys.stderr)
        return 1

    cfg = TARGETS[target_name]
    return run_ansible(
        playbook=cfg["playbook"],
        inventory=cfg["inventory"],
        limit=node_limit,
        verbose=args.verbose,
        check=args.dry_run,
        syntax_check=args.check,
    )
