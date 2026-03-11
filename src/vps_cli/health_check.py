#!/usr/bin/env python3

import subprocess
from pathlib import Path
from typing import Optional

from vps_cli import find_project_root
from vps_cli.util import GREEN, RED, YELLOW, RESET, BOLD
from vps_cli.errors import VpsError

BLUE = '\033[0;34m'


def print_colored(message: str, color: str = RESET):
    print(f"{color}{message}{RESET}")


def run_ansible_command(command: str, inventory_file: Path, cwd: Optional[Path] = None) -> bool:
    full_command = f"ansible {command} -i {inventory_file.name}"

    try:
        result = subprocess.run(
            full_command,
            shell=True,
            cwd=cwd,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_colored(f"❌ Command failed: {full_command}", RED)
        return False


def check_connectivity(environment: str, ansible_dir: Path) -> bool:
    print_colored("📡 Checking server connectivity...", BLUE)

    inventory_file = ansible_dir / f"inventories/{environment}.yml"

    if not inventory_file.exists():
        print_colored(f"❌ Inventory file not found: {inventory_file}", RED)
        return False

    return run_ansible_command("all -m ping", inventory_file, ansible_dir)


def check_system_resources(environment: str, ansible_dir: Path) -> bool:
    print_colored("💾 Checking system resources...", BLUE)

    inventory_file = ansible_dir / f"inventories/{environment}.yml"

    if not inventory_file.exists():
        print_colored(f"❌ Inventory file not found: {inventory_file}", RED)
        return False

    commands = [
        ('disk usage', 'all -m shell -a "df -h | head -5"'),
        ('memory usage', 'all -m shell -a "free -h"'),
        ('system uptime', 'all -m shell -a "uptime"'),
        ('load average', 'all -m shell -a "cat /proc/loadavg"')
    ]

    success = True
    for description, command in commands:
        print_colored(f"  Checking {description}...", YELLOW)
        if not run_ansible_command(command, inventory_file, ansible_dir):
            success = False

    return success


def check_services(environment: str, ansible_dir: Path) -> bool:
    print_colored("🔧 Checking critical services...", BLUE)

    inventory_file = ansible_dir / f"inventories/{environment}.yml"

    if not inventory_file.exists():
        print_colored(f"❌ Inventory file not found: {inventory_file}", RED)
        return False

    services = [
        ('SSH service', 'all -m service -a "name=ssh state=started"'),
        ('Docker service', 'all -m service -a "name=docker state=started"'),
    ]

    success = True
    for description, command in services:
        print_colored(f"  Checking {description}...", YELLOW)
        if not run_ansible_command(command, inventory_file, ansible_dir):
            success = False

    return success


def check_docker_containers(environment: str, ansible_dir: Path) -> bool:
    print_colored("🐳 Checking Docker containers...", BLUE)

    inventory_file = ansible_dir / f"inventories/{environment}.yml"

    if not inventory_file.exists():
        print_colored(f"❌ Inventory file not found: {inventory_file}", RED)
        return False

    commands = [
        ('container status', 'all -m shell -a "docker ps --format \'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\'"'),
        ('container health', 'all -m shell -a "docker ps --filter health=healthy --format \'table {{.Names}}\\t{{.Status}}\'"'),
    ]

    success = True
    for description, command in commands:
        print_colored(f"  Checking {description}...", YELLOW)
        if not run_ansible_command(command, inventory_file, ansible_dir):
            success = False

    return success


def check_monitoring_endpoints(environment: str, ansible_dir: Path) -> bool:
    print_colored("📊 Checking monitoring endpoints...", BLUE)

    inventory_file = ansible_dir / f"inventories/{environment}.yml"

    if not inventory_file.exists():
        print_colored(f"❌ Inventory file not found: {inventory_file}", RED)
        return False

    # Check if services are responding on their ports
    endpoints = [
        ('Grafana (port 3000)', 'all -m uri -a "url=http://localhost:3000/api/health timeout=10"'),
        ('Prometheus (port 9090)', 'all -m uri -a "url=http://localhost:9090/-/ready timeout=10"'),
        ('Loki (port 3100)', 'all -m uri -a "url=http://localhost:3100/ready timeout=10"'),
    ]

    success = True
    for description, command in endpoints:
        print_colored(f"  Checking {description}...", YELLOW)
        if not run_ansible_command(command, inventory_file, ansible_dir):
            print_colored(f"    ⚠️ {description} may not be responding", YELLOW)
            # Don't fail the whole check for endpoint issues

    return success


def run_health_checks(environment: str = 'dev', skip_endpoints: bool = False) -> bool:
    print_colored(f"🔍 Running health checks for environment: {environment}", BLUE)

    # Get project root directory
    project_root = find_project_root()
    ansible_dir = project_root / "ansible"

    if not ansible_dir.exists():
        raise VpsError(f"Ansible directory not found: {ansible_dir}")

    # Run all health checks
    checks = [
        ("connectivity", check_connectivity),
        ("system resources", check_system_resources),
        ("services", check_services),
        ("docker containers", check_docker_containers),
    ]

    if not skip_endpoints:
        checks.append(("monitoring endpoints", check_monitoring_endpoints))

    failed_checks = []

    for check_name, check_function in checks:
        try:
            print_colored(f"\n--- Running {check_name} check ---", BLUE)
            if not check_function(environment, ansible_dir):
                failed_checks.append(check_name)
        except Exception as e:
            print_colored(f"❌ {check_name} check failed with error: {e}", RED)
            failed_checks.append(check_name)

    # Print summary
    print_colored("\n📊 Health Check Summary:", BLUE)

    if not failed_checks:
        print_colored("✅ All health checks passed!", GREEN)
        return True
    else:
        print_colored(f"❌ {len(failed_checks)} health check(s) failed:", RED)
        for check in failed_checks:
            print_colored(f"  • {check}", RED)

        print_colored("\n💡 Tips:", YELLOW)
        print_colored("  • Check server connectivity and SSH access", YELLOW)
        print_colored("  • Verify services are running: systemctl status <service>", YELLOW)
        print_colored("  • Check logs: journalctl -u <service> --tail 50", YELLOW)

        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Infrastructure Health Check Script')
    parser.add_argument('environment', nargs='?', default='dev',
                       help='Environment to check (default: dev)')
    parser.add_argument('--skip-endpoints', action='store_true',
                       help='Skip monitoring endpoint checks')

    args = parser.parse_args()

    success = run_health_checks(args.environment, args.skip_endpoints)
    if not success:
        raise VpsError("Health checks failed")
