from __future__ import annotations

import argparse
import sys

from vps_cli.errors import VpsError


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

    # remnawave
    rw_p = sub.add_parser("remnawave", help="Remnawave panel config (export, sync)")
    rw_p.set_defaults(_parser=rw_p)
    rw_sub = rw_p.add_subparsers(dest="remnawave_command", metavar="<command>")

    rw_sub.add_parser("export", help="Export panel state to state.yml")

    rw_sync = rw_sub.add_parser("sync", help="Sync state.yml to panel")
    sync_mode = rw_sync.add_mutually_exclusive_group()
    sync_mode.add_argument("--plan", action="store_const", const="plan", dest="mode", help="Show what would change (default)")
    sync_mode.add_argument("--apply", action="store_const", const="apply", dest="mode", help="Apply changes")
    rw_sync.add_argument("--delete-missing", action="store_true", help="Delete resources in panel but not in state.yml")
    rw_sync.set_defaults(mode="plan")

    rw_add = rw_sub.add_parser("add-node", help="Add a new VPN node (guided workflow)")
    rw_add.add_argument("--ip", required=True, help="Node IP address")
    rw_add.add_argument("--name", required=True, help="Display name (e.g., 'Netherlands 2')")
    rw_add.add_argument("--country", required=True, help="Country code (e.g., NL)")
    rw_add.add_argument("--domain", required=True, help="VLESS WS domain (e.g., nl2.rutube.dad)")
    rw_add.add_argument("--node-id", default=None, help="Inventory hostname (default: auto node-N)")
    rw_add.add_argument("--vless-port", type=int, default=443, help="VLESS+WS port (default: 443)")
    rw_add.add_argument("--reality-port", type=int, default=8443, help="Reality port (default: 8443)")

    rw_snapshot = rw_sub.add_parser("snapshot", help="Save configs locally for offline use")
    rw_snapshot.add_argument("--user", default=None, help="Username (default: all 'MY' tagged users)")
    rw_snapshot.add_argument("--format", choices=["clash", "hiddify"], default="clash", dest="fmt", help="Output format (default: clash)")

    rw_genkeys = rw_sub.add_parser("gen-keys", help="Generate Reality keypair and inject into state.yml placeholders")
    rw_genkeys.add_argument("--prefix", required=True, help="Placeholder prefix (e.g., REALITY2 for __REALITY2_PRIVATE_KEY__)")
    rw_genkeys.add_argument("--node", default=None, help="Node to generate keys on (default: first in inventory)")
    rw_genkeys.add_argument("--no-save", action="store_true", help="Don't save keys to secrets.yml")

    # certs
    certs_p = sub.add_parser("certs", help="SSL certificate management")
    certs_p.set_defaults(_parser=certs_p)
    certs_sub = certs_p.add_subparsers(dest="certs_command", metavar="<command>")
    certs_sub.add_parser("renew", help="Renew *.rutube.dad wildcard cert via Cloudflare Origin CA")

    # secrets
    secrets_p = sub.add_parser("secrets", help="Secrets management")
    secrets_p.add_argument("action", nargs="?", choices=["check", "init"], default="check", help="Action (default: check)")

    return parser


def _dispatch_server(args: argparse.Namespace) -> int:
    from vps_cli.cli.server import cmd_server_logs, cmd_server_restart, cmd_server_ssh, cmd_server_test

    if not args.server_command:
        args._parser.print_help()
        return 0
    return {
        "logs": cmd_server_logs,
        "restart": cmd_server_restart,
        "ssh": cmd_server_ssh,
        "test": cmd_server_test,
    }[args.server_command](args)


def _dispatch_certs(args: argparse.Namespace) -> int:
    from vps_cli.cli.certs import cmd_certs_renew

    if not args.certs_command:
        args._parser.print_help()
        return 0
    return {
        "renew": cmd_certs_renew,
    }[args.certs_command](args)


def _dispatch_remnawave(args: argparse.Namespace) -> int:
    from vps_cli.cli.remnawave import (
        cmd_remnawave_add_node,
        cmd_remnawave_export,
        cmd_remnawave_gen_keys,
        cmd_remnawave_snapshot,
        cmd_remnawave_sync,
    )

    if not args.remnawave_command:
        args._parser.print_help()
        return 0
    return {
        "export": cmd_remnawave_export,
        "sync": cmd_remnawave_sync,
        "snapshot": cmd_remnawave_snapshot,
        "add-node": cmd_remnawave_add_node,
        "gen-keys": cmd_remnawave_gen_keys,
    }[args.remnawave_command](args)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        from vps_cli.cli.status import cmd_status
        sys.exit(cmd_status(args))

    handlers = {
        "setup": lambda a: __import__("vps_cli.cli.setup", fromlist=["cmd_setup"]).cmd_setup(a),
        "deploy": lambda a: __import__("vps_cli.cli.deploy", fromlist=["cmd_deploy"]).cmd_deploy(a),
        "doctor": lambda a: __import__("vps_cli.cli.doctor", fromlist=["cmd_doctor"]).cmd_doctor(a),
        "server": _dispatch_server,
        "remnawave": _dispatch_remnawave,
        "certs": _dispatch_certs,
        "secrets": lambda a: __import__("vps_cli.cli.secrets", fromlist=["cmd_secrets"]).cmd_secrets(a),
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            sys.exit(handler(args))
        except VpsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
