from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

from vps_cli import find_project_root
from vps_cli.errors import ApiError, SecretsError, VpsError
from vps_cli.util import BOLD, DIM, GREEN, RED, RESET, YELLOW, confirm

HOSTNAMES = ["*.rutube.dad", "rutube.dad"]
VALIDITY_DAYS = 5475  # 15 years


def _load_secret(key: str) -> str:
    root = find_project_root()
    path = root / "secrets.yml"
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    value = data.get(key, "")
    if not value:
        raise SecretsError(
            f"'{key}' not configured in secrets.yml. "
            "Get your Origin CA Key from: Cloudflare Dashboard > My Profile > API Tokens > Origin CA Key"
        )
    return value


def _certs_dir() -> Path:
    return find_project_root() / "ansible" / "inventories" / "nodes" / "certs"


def _generate_key(key_path: Path) -> None:
    result = subprocess.run(
        ["openssl", "genrsa", "-out", str(key_path), "2048"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise VpsError(f"Error generating private key:\n{result.stderr}")


def _generate_csr(key_path: Path, csr_path: Path) -> str:
    subj = "/CN=rutube.dad"
    san = ",".join(f"DNS:{h}" for h in HOSTNAMES)
    result = subprocess.run(
        [
            "openssl", "req", "-new", "-key", str(key_path),
            "-out", str(csr_path), "-subj", subj,
            "-addext", f"subjectAltName={san}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise VpsError(f"Error generating CSR:\n{result.stderr}")
    return csr_path.read_text()


def _request_certificate(csr: str, origin_ca_key: str) -> str:
    payload = {
        "csr": csr,
        "hostnames": HOSTNAMES,
        "request_type": "origin-rsa",
        "requested_validity": VALIDITY_DAYS,
    }
    resp = httpx.post(
        "https://api.cloudflare.com/client/v4/certificates",
        headers={"X-Auth-User-Service-Key": origin_ca_key},
        json=payload,
        timeout=30,
    )
    data = resp.json()
    if not data.get("success"):
        errors = data.get("errors", [])
        raise ApiError(f"Cloudflare API error: {errors}")
    return data["result"]["certificate"]


def _get_cert_expiry(cert_path: Path) -> datetime | None:
    result = subprocess.run(
        ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    line = result.stdout.strip()
    if "=" not in line:
        return None
    date_str = line.split("=", 1)[1]
    try:
        return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def renew_certs() -> None:
    certs = _certs_dir()
    cert_path = certs / "fullchain.pem"
    key_path = certs / "key.pem"

    if cert_path.exists():
        expiry = _get_cert_expiry(cert_path)
        if expiry:
            remaining = expiry - datetime.now(timezone.utc)
            color = GREEN if remaining.days > 90 else YELLOW if remaining.days > 0 else RED
            print(
                f"Existing cert expires: {color}{expiry:%Y-%m-%d}{RESET}"
                f" ({remaining.days} days remaining)"
            )
        else:
            print(f"{YELLOW}Existing cert found but could not read expiry{RESET}")

        if not confirm("Overwrite existing certificates?"):
            print("Aborted.")
            return

    origin_ca_key = _load_secret("cloudflare_origin_ca_key")

    print(f"\n{BOLD}Creating Cloudflare Origin CA certificate{RESET}")
    print(f"  Hostnames: {', '.join(HOSTNAMES)}")
    print(f"  Validity:  {VALIDITY_DAYS} days (~15 years)\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tmp_key = tmp / "key.pem"
        tmp_csr = tmp / "request.csr"

        print(f"  {DIM}Generating RSA 2048 private key...{RESET}")
        _generate_key(tmp_key)

        print(f"  {DIM}Generating CSR...{RESET}")
        csr = _generate_csr(tmp_key, tmp_csr)

        print(f"  {DIM}Requesting certificate from Cloudflare...{RESET}")
        certificate = _request_certificate(csr, origin_ca_key)

        certs.mkdir(parents=True, exist_ok=True)
        for p in (cert_path, key_path):
            if p.exists():
                bak = p.with_suffix(p.suffix + ".bak")
                shutil.copy2(p, bak)
                print(f"  Backed up {p.name} -> {bak.name}")

        cert_path.write_text(certificate)
        tmp_key_content = tmp_key.read_text()
        key_path.write_text(tmp_key_content)
        key_path.chmod(0o600)

    print(f"\n{GREEN}Certificate created successfully{RESET}")
    print(f"  {cert_path}")
    print(f"  {key_path}")
    print(f"\n{BOLD}Next steps:{RESET}")
    print(f"  Deploy to nodes:  vps deploy nodes")
