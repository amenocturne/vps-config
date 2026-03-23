from __future__ import annotations

import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from vps_cli import find_project_root
from vps_cli.ansible import TARGETS, ping_target
from vps_cli.cli.status import _secrets_summary
from vps_cli.util import BOLD, DIM, GREEN, RED, RESET, YELLOW


def cmd_doctor(args: argparse.Namespace) -> int:
    root = find_project_root()
    ansible_dir = root / "ansible"

    run_all = not any([args.secrets, args.syntax, args.connectivity, args.services])
    results = []

    print(f"\n{BOLD}VPS Doctor{RESET} {DIM}— runs all checks. Use --help for individual ones.{RESET}\n")

    if run_all or args.secrets:
        configured, total = _secrets_summary()
        ok = configured == total
        mark = f"{GREEN}v{RESET}" if ok else f"{RED}x{RESET}"
        print(f"  {mark} Secrets          {configured}/{total} present")
        results.append(ok)

    if run_all or args.syntax:
        inv = "inventories/production.yml" if (ansible_dir / "inventories/production.yml").exists() else "inventories/hosts.yml"
        r = subprocess.run(
            ["ansible-playbook", "playbooks/site.yml", "--syntax-check", "-i", inv],
            cwd=ansible_dir,
            capture_output=True,
        )
        ok = r.returncode == 0
        mark = f"{GREEN}v{RESET}" if ok else f"{RED}x{RESET}"
        print(f"  {mark} Ansible syntax   {'playbooks valid' if ok else 'syntax errors found'}")
        results.append(ok)

    if run_all or args.connectivity:
        available = {
            name: cfg for name, cfg in TARGETS.items()
            if cfg.get("enabled", True) and (ansible_dir / cfg["inventory"]).exists()
        }
        if available:
            with ThreadPoolExecutor(max_workers=len(available)) as pool:
                futures = {
                    pool.submit(ping_target, name, cfg, ansible_dir): name
                    for name, cfg in available.items()
                }
                reachable, unreachable = [], []
                for future in as_completed(futures):
                    name, ok = future.result()
                    (reachable if ok else unreachable).append(name)

            all_ok = len(unreachable) == 0
            mark = f"{GREEN}v{RESET}" if all_ok else f"{RED}x{RESET}"
            if unreachable:
                detail = f"{', '.join(sorted(reachable))} ok; {RED}{', '.join(sorted(unreachable))} unreachable{RESET}"
            else:
                detail = ", ".join(sorted(reachable))
            print(f"  {mark} Connectivity     {detail}")
            results.append(all_ok)

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
                mark = f"{GREEN}v{RESET}" if ok else f"{RED}x{RESET}"
                if ok:
                    lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
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
                mark = f"{RED}x{RESET}"
                detail = "timed out"
            print(f"  {mark} Services         {detail}")
            results.append(ok)
        else:
            print(f"  {DIM}- Services         no production inventory{RESET}")

    passed = sum(results)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed\n")
    return 0 if all(results) else 1
