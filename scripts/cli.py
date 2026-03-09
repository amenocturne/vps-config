"""
Unified CLI for VPS configuration management.

Entry point: `vps` (via pyproject.toml scripts).

Structure:
  vps                    status dashboard
  vps setup              first-time setup
  vps deploy [TARGET]    deploy via Ansible
  vps doctor             check everything
  vps server             server operations (logs, restart, ssh, test)
  vps panel              remnawave panel config (export, sync)
  vps secrets            secrets management (check, init)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ---------------------------------------------------------------------------
# Target configuration
# ---------------------------------------------------------------------------

TARGETS = {
    "vps": {
        "playbook": "playbooks/site.yml",
        "inventory": "inventories/production.yml",
        "host": "vps",
        "description": "main server",
    },
    "remnawave": {
        "playbook": "playbooks/remnawave.yml",
        "inventory": "inventories/remnawave-test.yml",
        "host": "remnawave",
        "description": "panel server",
    },
    "nodes": {
        "playbook": "playbooks/node.yml",
        "inventory": "inventories/nodes.yml",
        "host": "remnawave_nodes",
        "description": "all VPN nodes",
    },
}

ROLE_TARGETS = {
    "caddy": ("caddy", "role only (on vps)"),
    "authelia": ("authelia", "role only (on vps)"),
    "grafana": ("grafana", "role only (on vps)"),
}

# ANSI
DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    print("Error: could not find project root", file=sys.stderr)
    sys.exit(1)


def _resolve_on_target(target_name: str | None) -> dict:
    name = target_name or "vps"
    if name not in TARGETS:
        print(f"Error: unknown target '{name}'. Valid: {', '.join(TARGETS)}", file=sys.stderr)
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


def _ping_target(name: str, cfg: dict, ansible_dir: Path) -> tuple[str, bool]:
    """Ping a single target with short timeout."""
    try:
        result = subprocess.run(
            ["ansible", cfg["host"], "-i", cfg["inventory"],
             "-m", "ping", "-T", "5", "--one-line"],
            cwd=ansible_dir,
            capture_output=True,
            timeout=10,
        )
        return (name, result.returncode == 0)
    except (subprocess.TimeoutExpired, Exception):
        return (name, False)


def _secrets_summary() -> tuple[int, int]:
    """Return (configured, total) without printing."""
    from scripts.secrets import SCHEMA, _is_placeholder, secrets_path

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


def _pick_deploy_target() -> str | None:
    """Interactive target picker."""
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


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_status(_args: argparse.Namespace) -> int:
    """Status dashboard."""
    root = _find_project_root()
    ansible_dir = root / "ansible"

    print(f"\n{BOLD}VPS{RESET} {DIM}— use --help to see available commands{RESET}\n")

    # Secrets (local, fast)
    configured, total = _secrets_summary()
    if configured == total:
        color = GREEN
    elif configured == 0:
        color = RED
    else:
        color = YELLOW
    print(f"  Secrets        {color}{configured}/{total}{RESET} configured")

    # Connectivity (parallel)
    available_targets = {
        name: cfg for name, cfg in TARGETS.items()
        if (ansible_dir / cfg["inventory"]).exists()
    }

    if available_targets:
        with ThreadPoolExecutor(max_workers=len(available_targets)) as pool:
            futures = {
                pool.submit(_ping_target, name, cfg, ansible_dir): name
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


def cmd_setup(_args: argparse.Namespace) -> int:
    """First-time setup: inventory + secrets."""
    root = _find_project_root()
    production_inv = root / "ansible" / "inventories" / "production.yml"
    template_inv = root / "ansible" / "inventories" / "hosts.yml"

    if not production_inv.exists() and template_inv.exists():
        import shutil

        shutil.copy2(template_inv, production_inv)
        print(f"Created {production_inv.relative_to(root)} — customize with your VPS IP and domain")

    from scripts.secrets import cmd_setup as secrets_setup

    return secrets_setup()


def cmd_deploy(args: argparse.Namespace) -> int:
    """Deploy via Ansible."""
    from scripts.secrets import cmd_check

    if cmd_check() != 0:
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
        return _run_ansible(
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
    return _run_ansible(
        playbook=cfg["playbook"],
        inventory=cfg["inventory"],
        limit=node_limit,
        verbose=args.verbose,
        check=args.dry_run,
        syntax_check=args.check,
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run all checks: secrets, syntax, connectivity, services."""
    root = _find_project_root()
    ansible_dir = root / "ansible"

    run_all = not any([args.secrets, args.syntax, args.connectivity, args.services])
    results = []

    print(f"\n{BOLD}VPS Doctor{RESET} {DIM}— runs all checks. Use --help for individual ones.{RESET}\n")

    # Secrets
    if run_all or args.secrets:
        configured, total = _secrets_summary()
        ok = configured == total
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {mark} Secrets          {configured}/{total} present")
        results.append(ok)

    # Ansible syntax
    if run_all or args.syntax:
        inv = "inventories/production.yml" if (ansible_dir / "inventories/production.yml").exists() else "inventories/hosts.yml"
        r = subprocess.run(
            ["ansible-playbook", "playbooks/site.yml", "--syntax-check", "-i", inv],
            cwd=ansible_dir,
            capture_output=True,
        )
        ok = r.returncode == 0
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {mark} Ansible syntax   {'playbooks valid' if ok else 'syntax errors found'}")
        results.append(ok)

    # Connectivity
    if run_all or args.connectivity:
        available = {
            name: cfg for name, cfg in TARGETS.items()
            if (ansible_dir / cfg["inventory"]).exists()
        }
        if available:
            with ThreadPoolExecutor(max_workers=len(available)) as pool:
                futures = {
                    pool.submit(_ping_target, name, cfg, ansible_dir): name
                    for name, cfg in available.items()
                }
                reachable, unreachable = [], []
                for future in as_completed(futures):
                    name, ok = future.result()
                    (reachable if ok else unreachable).append(name)

            all_ok = len(unreachable) == 0
            mark = f"{GREEN}✓{RESET}" if all_ok else f"{RED}✗{RESET}"
            if unreachable:
                detail = f"{', '.join(sorted(reachable))} ok; {RED}{', '.join(sorted(unreachable))} unreachable{RESET}"
            else:
                detail = ', '.join(sorted(reachable))
            print(f"  {mark} Connectivity     {detail}")
            results.append(all_ok)

    # Services
    if run_all or args.services:
        inv_path = ansible_dir / "inventories/production.yml"
        if inv_path.exists():
            try:
                r = subprocess.run(
                    ["ansible", "vps", "-i", "inventories/production.yml", "-m", "shell", "-a",
                     "docker ps -a --format 'table {% raw %}{{.Names}}\t{{.Status}}{% endraw %}' | tail -n +2 | head -10"],
                    cwd=ansible_dir,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                ok = r.returncode == 0
                mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
                if ok:
                    lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
                    # Filter to actual container lines (skip ansible preamble)
                    running = [l for l in lines if "Up" in l]
                    stopped = [l for l in lines if "Exited" in l]
                    parts = []
                    if running:
                        parts.append(f"{len(running)} running")
                    if stopped:
                        parts.append(f"{YELLOW}{len(stopped)} stopped{RESET}")
                    detail = ", ".join(parts) if parts else "no containers"
                else:
                    detail = "could not check"
            except subprocess.TimeoutExpired:
                ok = False
                mark = f"{RED}✗{RESET}"
                detail = "timed out"
            print(f"  {mark} Services         {detail}")
            results.append(ok)
        else:
            print(f"  {DIM}- Services         no production inventory{RESET}")

    passed = sum(results)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed\n")
    return 0 if all(results) else 1


def cmd_secrets(args: argparse.Namespace) -> int:
    """Secrets management."""
    action = args.action or "check"
    if action == "check":
        from scripts.secrets import cmd_check

        return cmd_check()
    elif action == "init":
        from scripts.secrets import cmd_init

        return cmd_init()
    print(f"Error: unknown action '{action}'", file=sys.stderr)
    return 1


# -- server subcommands ---------------------------------------------------


def cmd_server_logs(args: argparse.Namespace) -> int:
    cfg = _resolve_on_target(args.on)
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker logs --tail 50 {args.service}",
    )


def cmd_server_restart(args: argparse.Namespace) -> int:
    cfg = _resolve_on_target(args.on)
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=f"docker restart {args.service}",
    )


def cmd_server_ssh(args: argparse.Namespace) -> int:
    cfg = _resolve_on_target(args.on)
    command = args.shell_command or "uptime"
    return _run_ansible(
        host=cfg["host"],
        inventory=cfg["inventory"],
        module="shell",
        module_args=command,
    )


def cmd_server_test(args: argparse.Namespace) -> int:
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


# -- panel subcommands ----------------------------------------------------


def cmd_panel_export(_args: argparse.Namespace) -> int:
    from remnawave_config.export import main as export_main

    try:
        export_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def cmd_panel_sync(args: argparse.Namespace) -> int:
    argv = ["--apply"] if args.mode == "apply" else ["--plan"]
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


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vps",
        description="VPS configuration management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # setup
    sub.add_parser("setup", help="First-time secrets + inventory setup")

    # deploy
    deploy_p = sub.add_parser("deploy", help="Deploy via Ansible")
    deploy_p.add_argument("target", nargs="?", default=None, help="Target (interactive picker if omitted)")
    deploy_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    deploy_p.add_argument("--dry-run", action="store_true", help="Check mode (no changes)")
    deploy_p.add_argument("--check", action="store_true", help="Syntax check only")

    # doctor
    doctor_p = sub.add_parser("doctor", help="Check everything")
    doctor_p.add_argument("--secrets", action="store_true", help="Check secrets only")
    doctor_p.add_argument("--syntax", action="store_true", help="Check Ansible syntax only")
    doctor_p.add_argument("--connectivity", action="store_true", help="Check connectivity only")
    doctor_p.add_argument("--services", action="store_true", help="Check services only")

    # server
    server_p = sub.add_parser("server", help="Server operations")
    server_p.set_defaults(_parser=server_p)
    server_sub = server_p.add_subparsers(dest="server_command", metavar="<command>")

    s_logs = server_sub.add_parser("logs", help="View docker logs")
    s_logs.add_argument("service", help="Service name")
    s_logs.add_argument("--on", default=None, help="Target (default: vps)")

    s_restart = server_sub.add_parser("restart", help="Restart docker service")
    s_restart.add_argument("service", help="Service name")
    s_restart.add_argument("--on", default=None, help="Target (default: vps)")

    s_ssh = server_sub.add_parser("ssh", help="Run shell command")
    s_ssh.add_argument("shell_command", nargs="?", default=None, metavar="COMMAND", help="Command (default: uptime)")
    s_ssh.add_argument("--on", default=None, help="Target (default: vps)")

    s_test = server_sub.add_parser("test", help="Local Docker testing")
    s_test.add_argument("--clean", action="store_true", help="Clean up test environment")

    # panel
    panel_p = sub.add_parser("panel", help="Remnawave panel config")
    panel_p.set_defaults(_parser=panel_p)
    panel_sub = panel_p.add_subparsers(dest="panel_command", metavar="<command>")

    panel_sub.add_parser("export", help="Export panel state to state.yml")

    p_sync = panel_sub.add_parser("sync", help="Sync state.yml to panel")
    sync_mode = p_sync.add_mutually_exclusive_group()
    sync_mode.add_argument("--plan", action="store_const", const="plan", dest="mode", help="Show what would change (default)")
    sync_mode.add_argument("--apply", action="store_const", const="apply", dest="mode", help="Apply changes")
    p_sync.set_defaults(mode="plan")

    # secrets
    secrets_p = sub.add_parser("secrets", help="Secrets management")
    secrets_p.add_argument("action", nargs="?", choices=["check", "init"], default="check", help="Action (default: check)")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        sys.exit(cmd_status(args))

    handlers = {
        "setup": cmd_setup,
        "deploy": cmd_deploy,
        "doctor": cmd_doctor,
        "server": _dispatch_server,
        "panel": _dispatch_panel,
        "secrets": cmd_secrets,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


def _dispatch_server(args: argparse.Namespace) -> int:
    if not args.server_command:
        args._parser.print_help()
        return 0
    return {
        "logs": cmd_server_logs,
        "restart": cmd_server_restart,
        "ssh": cmd_server_ssh,
        "test": cmd_server_test,
    }[args.server_command](args)


def _dispatch_panel(args: argparse.Namespace) -> int:
    if not args.panel_command:
        args._parser.print_help()
        return 0
    return {
        "export": cmd_panel_export,
        "sync": cmd_panel_sync,
    }[args.panel_command](args)


if __name__ == "__main__":
    main()
