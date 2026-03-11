from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from vps_cli import find_project_root
from vps_cli.ansible import TARGETS, ping_target
from vps_cli.util import BOLD, DIM, GREEN, RED, RESET, YELLOW


def _secrets_summary() -> tuple[int, int]:
    from vps_cli.secrets import SCHEMA, _is_placeholder, secrets_path

    import yaml

    path = secrets_path()
    if not path.exists():
        total = sum(len(s["keys"]) for s in SCHEMA)
        return (0, total)

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    total = 0
    configured = 0
    for section in SCHEMA:
        for key in section["keys"]:
            total += 1
            if not _is_placeholder(data.get(key["name"])):
                configured += 1
    return (configured, total)


def cmd_status(_args: argparse.Namespace) -> int:
    root = find_project_root()
    ansible_dir = root / "ansible"

    print(f"\n{BOLD}VPS Status{RESET}\n")

    configured, total = _secrets_summary()
    if configured == total:
        color = GREEN
    elif configured == 0:
        color = RED
    else:
        color = YELLOW
    print(f"  Secrets        {color}{configured}/{total}{RESET} configured")

    available_targets = {
        name: cfg for name, cfg in TARGETS.items()
        if (ansible_dir / cfg["inventory"]).exists()
    }

    if available_targets:
        with ThreadPoolExecutor(max_workers=len(available_targets)) as pool:
            futures = {
                pool.submit(ping_target, name, cfg, ansible_dir): name
                for name, cfg in available_targets.items()
            }
            results = {}
            for future in as_completed(futures):
                name, ok = future.result()
                results[name] = ok

        parts = []
        for name in TARGETS:
            if name not in results:
                continue
            if results[name]:
                parts.append(f"{name}: {GREEN}ok{RESET}")
            else:
                parts.append(f"{name}: {RED}unreachable{RESET}")
        print(f"  Connectivity   {' | '.join(parts)}")
    else:
        print(f"  Connectivity   {DIM}no inventories configured{RESET}")

    print()
    return 0
