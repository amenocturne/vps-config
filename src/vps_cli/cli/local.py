from __future__ import annotations

import argparse
import platform
import subprocess
import tempfile
from pathlib import Path

from vps_cli import find_project_root
from vps_cli.errors import VpsError
from vps_cli.util import bold, green, red, yellow, confirm

RESOLVER_DIR = Path("/etc/resolver")
FALLBACK_DNS = "1.1.1.1"
DNS_TIMEOUT = 2


def _load_home_config() -> tuple[str, str]:
    """Load home server IP and domain from inventory."""
    import yaml

    root = find_project_root()
    inv_path = root / "ansible" / "inventories" / "hosts.yml"
    with open(inv_path) as f:
        inv = yaml.safe_load(f)

    home_ip = inv["all"]["children"]["home_server"]["hosts"]["home_server"]["ansible_host"]
    home_domain = inv["all"]["vars"]["home_domain"]
    return home_ip, home_domain


def cmd_local_setup(_args: argparse.Namespace) -> int:
    if platform.system() != "Darwin":
        raise VpsError("Local setup is only supported on macOS")

    home_ip, home_domain = _load_home_config()
    resolver_file = RESOLVER_DIR / home_domain

    print(bold("Setting up LAN access to home server\n"))

    _setup_resolver(home_ip, home_domain, resolver_file)
    _trust_caddy_ca(home_ip)
    _verify_setup(home_ip, home_domain)

    print(f"\n{green('Done!')} Home services now use LAN when at home.")
    print(f"  WebDAV in Finder: {bold(f'https://files.{home_domain}')}")
    return 0


def cmd_local_status(_args: argparse.Namespace) -> int:
    if platform.system() != "Darwin":
        raise VpsError("Local status is only supported on macOS")

    home_ip, home_domain = _load_home_config()
    resolver_file = RESOLVER_DIR / home_domain

    print(bold("LAN access status\n"))

    if resolver_file.exists():
        print(f"  {green('✓')} Resolver: {resolver_file}")
    else:
        print(f"  {red('✗')} Resolver: not configured")

    reachable = _is_reachable(home_ip)
    if reachable:
        print(f"  {green('✓')} Home server: reachable on LAN ({home_ip})")
    else:
        print(f"  {yellow('−')} Home server: not reachable (not on home network?)")

    resolved_ip = _resolve_domain(f"files.{home_domain}", home_ip)
    if resolved_ip:
        if resolved_ip == home_ip:
            print(f"  {green('✓')} DNS: files.{home_domain} → {resolved_ip} (local)")
        else:
            print(f"  {yellow('−')} DNS: files.{home_domain} → {resolved_ip} (remote)")
    else:
        print(f"  {red('✗')} DNS: resolution failed")

    return 0


def cmd_local_remove(_args: argparse.Namespace) -> int:
    if platform.system() != "Darwin":
        raise VpsError("Local setup is only supported on macOS")

    _, home_domain = _load_home_config()
    resolver_file = RESOLVER_DIR / home_domain

    if not resolver_file.exists():
        print("LAN access is not configured.")
        return 0

    if not confirm("Remove LAN access configuration?"):
        return 0

    subprocess.run(["sudo", "rm", str(resolver_file)], check=True)
    print(f"{green('✓')} Removed {resolver_file}")
    return 0


def _setup_resolver(home_ip: str, home_domain: str, resolver_file: Path) -> None:
    content = f"nameserver {home_ip}\nnameserver {FALLBACK_DNS}\ntimeout {DNS_TIMEOUT}\n"

    if resolver_file.exists():
        existing = resolver_file.read_text()
        if existing == content:
            print(f"  {green('✓')} Resolver already configured")
            return
        print(f"  Updating {resolver_file}")
    else:
        print(f"  Creating {resolver_file}")

    subprocess.run(["sudo", "mkdir", "-p", str(RESOLVER_DIR)], check=True)
    subprocess.run(
        ["sudo", "tee", str(resolver_file)],
        input=content.encode(),
        stdout=subprocess.DEVNULL,
        check=True,
    )
    print(f"  {green('✓')} Resolver configured (primary: {home_ip}, fallback: {FALLBACK_DNS})")


def _trust_caddy_ca(home_ip: str) -> None:
    print("  Fetching Caddy internal CA from home server...")

    if not _is_reachable(home_ip):
        print(f"  {yellow('⚠')} Home server not reachable — skipping CA trust")
        print(f"    Run again on home network: {bold('vps local setup')}")
        return

    result = subprocess.run(
        [
            "ssh",
            f"root@{home_ip}",
            "docker exec caddy-home cat /data/caddy/pki/authorities/local/root.crt",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  {yellow('⚠')} Could not fetch CA cert — deploy home server first")
        if result.stderr.strip():
            print(f"    {result.stderr.strip()}")
        return

    ca_cert = result.stdout
    if "BEGIN CERTIFICATE" not in ca_cert:
        print(f"  {yellow('⚠')} Invalid CA cert — deploy the tunnel role first")
        return

    with tempfile.NamedTemporaryFile(suffix=".crt", delete=False, mode="w") as f:
        f.write(ca_cert)
        cert_path = f.name

    try:
        if not confirm("  Trust Caddy's internal CA in macOS Keychain?"):
            print(f"  {yellow('−')} Skipped CA trust")
            return

        subprocess.run(
            [
                "sudo",
                "security",
                "add-trusted-cert",
                "-d",
                "-r",
                "trustRoot",
                "-k",
                "/Library/Keychains/System.keychain",
                cert_path,
            ],
            check=True,
        )
        print(f"  {green('✓')} Caddy CA trusted in macOS Keychain")
    finally:
        Path(cert_path).unlink(missing_ok=True)


def _verify_setup(home_ip: str, home_domain: str) -> None:
    print("\n  Verifying...")

    if not _is_reachable(home_ip):
        print(f"  {yellow('−')} Not on home network — can't verify DNS")
        return

    resolved = _resolve_domain(f"files.{home_domain}", home_ip)
    if resolved == home_ip:
        print(f"  {green('✓')} files.{home_domain} → {home_ip}")
    elif resolved:
        print(f"  {yellow('−')} files.{home_domain} → {resolved} (expected {home_ip})")
        print(f"    Try flushing DNS: {bold('sudo dscacheutil -flushcache')}")
    else:
        print(f"  {red('✗')} DNS resolution failed — is dnsmasq running on the server?")


def _is_reachable(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "1", ip],
        capture_output=True,
    )
    return result.returncode == 0


def _resolve_domain(domain: str, dns_server: str) -> str | None:
    result = subprocess.run(
        ["dig", "+short", "+time=2", domain, f"@{dns_server}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\n")[0]
    return None
