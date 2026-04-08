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
        ssh_key=args.ssh_key,
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

    return asyncio.run(
        run_sync(
            mode=args.mode,
            delete_missing=args.delete_missing,
        )
    )


def cmd_remnawave_template_push(args: argparse.Namespace) -> int:
    from pathlib import Path

    from vps_cli import find_project_root
    from vps_cli.remnawave.template import main as template_main

    template_path = (
        Path(args.file)
        if args.file
        else find_project_root() / "remnawave-config/templates/mihomo-ru-split.yaml"
    )
    if not template_path.exists():
        print(f"Template not found: {template_path}")
        return 1

    return template_main(template_path=template_path, name=args.name)
