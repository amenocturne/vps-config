from __future__ import annotations

import argparse
import asyncio


def cmd_remnawave_export(_args: argparse.Namespace) -> int:
    from vps_cli.remnawave.export import main as export_main

    export_main()
    return 0


def cmd_remnawave_snapshot(args: argparse.Namespace) -> int:
    from vps_cli.remnawave.snapshot import main as snapshot_main

    snapshot_main(username=args.user, fmt=args.fmt)
    return 0


def cmd_remnawave_add_node(args: argparse.Namespace) -> int:
    from vps_cli.remnawave.add_node import main as add_node_main

    add_node_main(
        ip=args.ip,
        name=args.name,
        country=args.country,
        domain=args.domain,
        node_id=args.node_id,
        vless_port=args.vless_port,
        reality_port=args.reality_port,
    )
    return 0


def cmd_remnawave_gen_keys(args: argparse.Namespace) -> int:
    from vps_cli.remnawave.gen_keys import main as gen_keys_main

    return gen_keys_main(
        prefix=args.prefix,
        node=args.node,
        save_secrets=not args.no_save,
    )


def cmd_remnawave_sync(args: argparse.Namespace) -> int:
    from vps_cli.remnawave.sync import run_sync

    return asyncio.run(run_sync(
        mode=args.mode,
        delete_missing=args.delete_missing,
    ))
