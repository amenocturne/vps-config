from __future__ import annotations

import argparse


def cmd_secrets_check(_args: argparse.Namespace) -> int:
    from vps_cli.secrets import check_secrets

    return check_secrets()


def cmd_secrets_init(_args: argparse.Namespace) -> int:
    from vps_cli.secrets import init_secrets

    return init_secrets()


def cmd_secrets_hash_password(args: argparse.Namespace) -> int:
    from argon2 import PasswordHasher

    ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    print(ph.hash(args.password))
    return 0
