from __future__ import annotations

import argparse
import sys


def cmd_secrets(args: argparse.Namespace) -> int:
    action = args.action or "check"
    if action == "check":
        from vps_cli.secrets import check_secrets

        return check_secrets()
    elif action == "init":
        from vps_cli.secrets import init_secrets

        return init_secrets()
    print(f"Error: unknown action '{action}'", file=sys.stderr)
    return 1
