"""
Unified CLI for VPS configuration management.

Replaces the justfile with a clean subcommand hierarchy.
Entry point: `vps` (via pyproject.toml scripts).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Target configuration
# ---------------------------------------------------------------------------

TARGETS = {
    "vps": {
        "playbook": "playbooks/site.yml",
        "inventory": "inventories/production.yml",
        "host": "vps",
    },
    "remnawave": {
        "playbook": "playbooks/remnawave.yml",
        "inventory": "inventories/remnawave-test.yml",
        "host": "remnawave",
    },
    "nodes": {
        "playbook": "playbooks/node.yml",
        "inventory": "inventories/nodes.yml",
        "host": "remnawave_nodes",
    },
}

# Role-specific deploys on main VPS (target name -> ansible tag)
ROLE_TARGETS = {
    "caddy": "caddy",
    "authelia": "authelia",
    "grafana": "grafana",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from CWD to find the project root (contains pyproject.toml)."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    print("Error: could not find project root (no pyproject.toml found)", file=sys.stderr)
    sys.exit(1)


def _resolve_on_target(target_name: str | None) -> dict:
    """Resolve an --on target to its config dict."""
    name = target_name or "vps"
    if name not in TARGETS:
        print(f"Error: unknown target '{name}'. Valid targets: {', '.join(TARGETS)}", file=sys.stderr)
        sys.exit(1)
    return TARGETS[name]


def _run_ansible(
    *,
    playbook: str | None = None,
    inventory: str,
    host: str | None = None,
    module: str | None = None,
    module_args: str | None = None,
    tags: str | None = None,
    limit: str | None = None,
    verbose: bool = False,
    check: bool = False,
    syntax_check: bool = False,
) -> int:
    """Build and execute an ansible command from the ansible/ directory."""
    root = _find_project_root()
    ansible_dir = root / "ansible"

    if playbook:
        cmd = ["ansible-playbook", playbook, "-i", inventory]
        if tags:
            cmd.extend(["--tags", tags])
        if limit:
            cmd.extend(["--limit", limit])
        if verbose:
            cmd.append("-v")
        if check:
            cmd.append("--check")
        if syntax_check:
            cmd.append("--syntax-check")
    elif host and module:
        cmd = ["ansible", host, "-i", inventory, "-m", module]
        if module_args:
            cmd.extend(["-a", module_args])
    else:
        print("Error: must specify either playbook or host+module", file=sys.stderr)
        return 1

    result = subprocess.run(cmd, cwd=ansible_dir)
    return result.returncode


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_setup(_args: argparse.Namespace) -> int:
    """Interactive setup: create inventory if missing + run secrets setup."""
    root = _find_project_root()
    production_inv = root / "ansible" / "inventories" / "production.yml"
    template_inv = root / "ansible" / "inventories" / "hosts.yml"

    if not production_inv.exists() and template_inv.exists():
        import shutil
        shutil.copy2(template_inv, production_inv)
        print(f"Created {production_inv.relative_to(root)} -- customize with your VPS IP and domain")

    from scripts.secrets import cmd_setup as secrets_setup
    return secrets_setup()


def cmd_secrets(args: argparse.Namespace) -> int:
    """Secrets management: check or init."""
    action = args.action or "check"

    if action == "check":
        from scripts.secrets import cmd_check
        return cmd_check()
    elif action == "init":
        from scripts.secrets import cmd_init
        return cmd_init()
    else:
        print(f"Error: unknown secrets action '{action}'", file=sys.stderr)
        return 1


def cmd_deploy(args: argparse.Namespace) -> int:
    """Deploy via Ansible."""
    # Always check secrets first
    from scripts.secrets import cmd_check
    if cmd_check() != 0:
        print("\nSecrets check failed. Run 'vps secrets init' or 'vps setup' first.", file=sys.stderr)
        return 1
    print()

    target_name = args.target or "vps"

    # Check for single-node deploys (node-1, node-2, etc.)
    node_limit = None
    if target_name.startswith("node-"):
        node_limit = target_name
        target_name = "nodes"

    # Check for role-specific deploys
    if target_name in ROLE_TARGETS:
        tag = ROLE_TARGETS[target_name]
        cfg = TARGETS["vps"]
        return _run_ansible(
            playbook=cfg["playbook"],
            inventory=cfg["inventory"],
            tags=tag,
            verbose=args.verbose,
            check=args.dry_run,
            syntax_check=args.check,
        )

    if target_name not in TARGETS:
        print(f"Error: unknown deploy target '{target_name}'", file=sys.stderr)
        print(f"Valid targets: {', '.join(list(TARGETS) + list(ROLE_TARGETS))}, node-N", file=sys.stderr)
        return 1

    cfg = TARGETS[target_name]
    return _run_ansible(
        playbook=cfg["playbook"],
        inventory=cfg["inventory"],
        limit=node_limit,
        verbose=args.verbose,
        check=args.dry_run,
        syntax_check=args.check,
    )


def cmd_logs(args: argparse.Namespace) -> int:
    """View docker logs for a service."""
    cfg = _resolve_on_target(args.on)
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker logs --tail 50 {args.service}",
    )


def cmd_restart(args: argparse.Namespace) -> int:
    """Restart a docker service."""
    cfg = _resolve_on_target(args.on)
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker restart {args.service}",
    )


def cmd_ssh(args: argparse.Namespace) -> int:
    """Run a shell command on the server."""
    cfg = _resolve_on_target(args.on)
    command = args.command or "uptime"
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=command,
    )


def cmd_ping(args: argparse.Namespace) -> int:
    """Test connectivity to a target."""
    target_name = args.target or "vps"
    if target_name not in TARGETS:
        print(f"Error: unknown target '{target_name}'. Valid targets: {', '.join(TARGETS)}", file=sys.stderr)
        return 1
    cfg = TARGETS[target_name]
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="ping",
    )


def cmd_health(_args: argparse.Namespace) -> int:
    """Run health checks."""
    from scripts.utilities.health_check import main as health_main
    try:
        health_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def cmd_config_export(_args: argparse.Namespace) -> int:
    """Export panel state to state.yml."""
    from remnawave_config.export import main as export_main
    try:
        export_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def cmd_config_sync(args: argparse.Namespace) -> int:
    """Sync state.yml to panel."""
    # Build argv for sync's own parser
    argv = []
    if args.mode == "apply":
        argv.append("--apply")
    else:
        argv.append("--plan")

    # Temporarily replace sys.argv for the sync module's parser
    old_argv = sys.argv
    sys.argv = ["sync-config"] + argv
    try:
        from remnawave_config.sync import main as sync_main
        sync_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old_argv


def cmd_validate(args: argparse.Namespace) -> int:
    """Run validation tests."""
    env = os.environ.copy()
    if not args.full:
        env["SKIP_DOCKER_PULL"] = "true"

    from scripts.validate import main as validate_main
    old_env = os.environ.get("SKIP_DOCKER_PULL")
    if not args.full:
        os.environ["SKIP_DOCKER_PULL"] = "true"
    try:
        validate_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    finally:
        if old_env is None:
            os.environ.pop("SKIP_DOCKER_PULL", None)
        else:
            os.environ["SKIP_DOCKER_PULL"] = old_env


def cmd_test(args: argparse.Namespace) -> int:
    """Local Docker testing."""
    if args.clean:
        root = _find_project_root()
        compose_dir = root / "docker" / "test-environment"
        result = subprocess.run(
            ["docker-compose", "down", "--remove-orphans", "-v"],
            cwd=compose_dir,
        )
        return result.returncode

    from scripts.test_local import main as test_main
    try:
        test_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vps",
        description="VPS configuration management CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Interactive secrets + inventory setup")

    # secrets
    secrets_p = sub.add_parser("secrets", help="Secrets management")
    secrets_p.add_argument(
        "action",
        nargs="?",
        choices=["check", "init"],
        default="check",
        help="Action to perform (default: check)",
    )

    # deploy
    deploy_p = sub.add_parser("deploy", help="Deploy via Ansible")
    deploy_p.add_argument(
        "target",
        nargs="?",
        default="vps",
        help="Deploy target: vps, remnawave, nodes, node-N, caddy, authelia, grafana (default: vps)",
    )
    deploy_p.add_argument("-v", "--verbose", action="store_true", help="Verbose ansible output")
    deploy_p.add_argument("--dry-run", action="store_true", help="Ansible check mode (no changes)")
    deploy_p.add_argument("--check", action="store_true", help="Ansible syntax check only")

    # logs
    logs_p = sub.add_parser("logs", help="View docker logs")
    logs_p.add_argument("service", help="Docker service name")
    logs_p.add_argument("--on", default=None, help="Target: vps, remnawave, nodes (default: vps)")

    # restart
    restart_p = sub.add_parser("restart", help="Restart docker service")
    restart_p.add_argument("service", help="Docker service name")
    restart_p.add_argument("--on", default=None, help="Target: vps, remnawave, nodes (default: vps)")

    # ssh
    ssh_p = sub.add_parser("ssh", help="Run shell command on server")
    ssh_p.add_argument("command", nargs="?", default=None, help="Command to run (default: uptime)")
    ssh_p.add_argument("--on", default=None, help="Target: vps, remnawave, nodes (default: vps)")

    # ping
    ping_p = sub.add_parser("ping", help="Test connectivity")
    ping_p.add_argument("target", nargs="?", default="vps", help="Target: vps, remnawave, nodes (default: vps)")

    # health
    sub.add_parser("health", help="Run health checks")

    # config
    config_p = sub.add_parser("config", help="Remnawave config management")
    config_sub = config_p.add_subparsers(dest="config_command")

    config_sub.add_parser("export", help="Export panel state to state.yml")

    sync_p = config_sub.add_parser("sync", help="Sync state.yml to panel")
    sync_mode = sync_p.add_mutually_exclusive_group()
    sync_mode.add_argument("--plan", action="store_const", const="plan", dest="mode", help="Show what would change (default)")
    sync_mode.add_argument("--apply", action="store_const", const="apply", dest="mode", help="Apply changes")
    sync_p.set_defaults(mode="plan")

    # validate
    validate_p = sub.add_parser("validate", help="Run validation tests")
    validate_p.add_argument("--full", action="store_true", help="Include Docker image pulls")

    # test
    test_p = sub.add_parser("test", help="Local Docker testing")
    test_p.add_argument("--clean", action="store_true", help="Clean up test environment")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "setup": cmd_setup,
        "secrets": cmd_secrets,
        "deploy": cmd_deploy,
        "logs": cmd_logs,
        "restart": cmd_restart,
        "ssh": cmd_ssh,
        "ping": cmd_ping,
        "health": cmd_health,
        "config": _dispatch_config,
        "validate": cmd_validate,
        "test": cmd_test,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


def _dispatch_config(args: argparse.Namespace) -> int:
    """Dispatch config subcommands."""
    if not args.config_command:
        # Show config help
        print("Usage: vps config {export,sync}", file=sys.stderr)
        return 1

    if args.config_command == "export":
        return cmd_config_export(args)
    elif args.config_command == "sync":
        return cmd_config_sync(args)
    return 1


if __name__ == "__main__":
    main()
