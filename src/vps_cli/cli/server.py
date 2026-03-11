from __future__ import annotations

import argparse
import subprocess

from vps_cli import find_project_root
from vps_cli.ansible import resolve_target, run_ansible


def cmd_server_logs(args: argparse.Namespace) -> int:
    cfg = resolve_target(args.on)
    return run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker logs --tail 50 {args.service}",
    )


def cmd_server_restart(args: argparse.Namespace) -> int:
    cfg = resolve_target(args.on)
    return run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker restart {args.service}",
    )


def cmd_server_ssh(args: argparse.Namespace) -> int:
    cfg = resolve_target(args.on)
    command = args.shell_command or "uptime"
    return run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=command,
    )


def cmd_server_test(args: argparse.Namespace) -> int:
    if args.clean:
        root = find_project_root()
        compose_dir = root / "docker" / "test-environment"
        result = subprocess.run(
            ["docker-compose", "down", "--remove-orphans", "-v"],
            cwd=compose_dir,
        )
        return result.returncode

    from vps_cli.test_local import main as test_main

    test_main()
    return 0
