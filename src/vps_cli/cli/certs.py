from __future__ import annotations

import argparse

from vps_cli.certs import renew_certs


def cmd_certs_renew(_args: argparse.Namespace) -> int:
    renew_certs()
    return 0
