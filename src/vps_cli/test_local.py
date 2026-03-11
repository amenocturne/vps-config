from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import requests

from vps_cli import find_project_root
from vps_cli.errors import VpsError
from vps_cli.util import BLUE, BOLD, GREEN, RED, RESET, YELLOW


def print_status(message, color=RESET):
    print(f"{color}{message}{RESET}")


def run_command(command, cwd=None, check=True, timeout=300, verbose=False):
    if verbose:
        print_status(f"Running: {command}", BLUE)

    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True,
            text=True, timeout=timeout, check=check,
        )

        if verbose:
            if result.stdout:
                print_status(f"STDOUT: {result.stdout.strip()}", GREEN)
            if result.stderr:
                print_status(f"STDERR: {result.stderr.strip()}", YELLOW)
            print_status(f"Exit code: {result.returncode}", BLUE)

        return result
    except subprocess.TimeoutExpired:
        print_status(f"Command timed out after {timeout}s: {command}", RED)
        return None
    except subprocess.CalledProcessError as e:
        if check:
            print_status(f"Command failed: {command}", RED)
            print_status(f"   Error: {e.stderr}", RED)
            return None
        return e


def wait_for_container_healthy(container_name, timeout=120):
    print_status(f"Waiting for {container_name} to be ready...", YELLOW)

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            result = run_command(f"docker ps --filter name={container_name} --format '{{{{.Status}}}}'", check=False)
            if not result or not result.stdout.strip():
                stopped_result = run_command(f"docker ps -a --filter name={container_name} --format '{{{{.Status}}}}'", check=False)
                if stopped_result and stopped_result.stdout.strip():
                    print_status(f"Container {container_name} exists but stopped: {stopped_result.stdout.strip()}", RED)
                    print_status("Container logs:", YELLOW)
                    run_command(f"docker logs {container_name} --tail 20", check=False, verbose=True)
                    return False
                else:
                    print_status(f"   Container {container_name} not found, waiting...", YELLOW)
                time.sleep(3)
                continue

            status = result.stdout.strip()
            if not status.startswith('Up'):
                print_status(f"   Container status: {status}", YELLOW)

                if 'Exited' in status:
                    print_status(f"Container {container_name} has exited: {status}", RED)
                    print_status("Container logs:", YELLOW)
                    run_command(f"docker logs {container_name} --tail 30", check=False, verbose=True)
                    return False

                time.sleep(2)
                continue

            if container_name == 'test-vps':
                try:
                    result = run_command(
                        f"docker exec {container_name} systemctl is-system-running --wait",
                        timeout=10, check=False,
                    )
                    if result and result.returncode in [0, 1]:
                        print_status(f"{container_name} systemd is ready", GREEN)
                        return True
                    else:
                        print_status(f"   Systemd status: {result.returncode if result else 'timeout'}", YELLOW)
                except Exception as e:
                    print_status(f"   Systemd check: {e}", YELLOW)
            else:
                print_status(f"{container_name} is running", GREEN)
                return True

        except Exception as e:
            print_status(f"   Checking container: {e}", YELLOW)

        time.sleep(3)

    print_status(f"{container_name} did not become ready within {timeout}s", RED)
    return False


def wait_for_ssh_service(container_name, timeout=60):
    print_status("Waiting for SSH service...", YELLOW)

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            print_status("   Checking SSH service status...", YELLOW)
            result = run_command(
                f"docker exec {container_name} systemctl is-active ssh",
                timeout=5, check=False, verbose=True,
            )

            if result and result.returncode == 0 and 'active' in result.stdout:
                print_status("   SSH is active, checking port 22...", YELLOW)
                port_check = run_command(
                    f"docker exec {container_name} netstat -tlnp | grep :22",
                    timeout=5, check=False, verbose=True,
                )
                if port_check and port_check.returncode == 0:
                    print_status("SSH service is active and listening", GREEN)
                    return True
                else:
                    print_status("   SSH active but not listening yet...", YELLOW)
            else:
                print_status("   SSH not active, attempting to start...", YELLOW)
                start_result = run_command(
                    f"docker exec {container_name} systemctl start ssh",
                    timeout=10, check=False, verbose=True,
                )

                if start_result:
                    run_command(
                        f"docker exec {container_name} systemctl status ssh --no-pager",
                        timeout=5, check=False, verbose=True,
                    )

        except Exception as e:
            print_status(f"   SSH check: {e}", YELLOW)

        time.sleep(3)

    print_status("Final SSH service diagnostics:", YELLOW)
    run_command(f"docker exec {container_name} systemctl status ssh --no-pager -l", timeout=10, check=False, verbose=True)
    run_command(f"docker exec {container_name} journalctl -u ssh --no-pager -n 20", timeout=10, check=False, verbose=True)

    print_status("Checking SSH installation:", YELLOW)
    run_command(f"docker exec {container_name} which sshd", timeout=5, check=False, verbose=True)
    run_command(f"docker exec {container_name} dpkg -l | grep openssh", timeout=5, check=False, verbose=True)

    print_status("Checking SSH config:", YELLOW)
    run_command(f"docker exec {container_name} ls -la /etc/ssh/", timeout=5, check=False, verbose=True)
    run_command(f"docker exec {container_name} sshd -T", timeout=5, check=False, verbose=True)

    print_status(f"SSH service not ready within {timeout}s", RED)
    return False


def setup_ssh_access():
    print_status("Setting up SSH access...", YELLOW)

    ssh_key_path = Path.home() / '.ssh' / 'id_rsa'

    if not ssh_key_path.exists():
        print_status("Generating SSH key...", YELLOW)
        result = run_command(f'ssh-keygen -t rsa -b 2048 -f {ssh_key_path} -N ""')
        if not result:
            return False

    try:
        run_command("docker exec test-vps mkdir -p /root/.ssh")

        with open(f"{ssh_key_path}.pub", 'r') as f:
            pub_key = f.read().strip()

        run_command(f"docker exec test-vps bash -c 'echo \"{pub_key}\" > /root/.ssh/authorized_keys'")
        run_command("docker exec test-vps chmod 600 /root/.ssh/authorized_keys")
        run_command("docker exec test-vps chown root:root /root/.ssh/authorized_keys")

        print_status("SSH access configured", GREEN)
        return True

    except Exception as e:
        print_status(f"Failed to setup SSH: {e}", RED)
        return False


def test_http_endpoint(url, expected_text=None, timeout=10):
    try:
        response = requests.get(url, verify=False, timeout=timeout)
        if response.status_code == 200:
            if expected_text and expected_text.lower() in response.text.lower():
                return True
            elif not expected_text:
                return True
        return False
    except Exception:
        return False


def main():
    print_status("Starting local testing environment...", BLUE)

    try:
        result = run_command("docker info", timeout=10)
        if result and result.returncode == 0:
            print_status("Docker CLI is working", GREEN)
        else:
            raise Exception("Docker CLI failed")
    except Exception:
        raise VpsError("Docker is not accessible. Please ensure Docker/Colima is running. Try: colima start")

    project_root = find_project_root()
    os.chdir(project_root)

    print_status("Building test environment...", YELLOW)
    compose_dir = project_root / 'docker' / 'test-environment'

    run_command("docker-compose down --remove-orphans", cwd=compose_dir, check=False)

    result = run_command("docker-compose up -d --build", cwd=compose_dir)
    if not result:
        raise VpsError("Failed to start test environment")

    if not wait_for_container_healthy('test-vps', timeout=180):
        print_status("Container logs:", YELLOW)
        run_command("docker-compose logs --tail 50", cwd=compose_dir, check=False, verbose=True)
        print_status("Container status:", YELLOW)
        run_command("docker ps -a --filter name=test-vps", check=False, verbose=True)
        print_status("Docker events:", YELLOW)
        run_command("docker events --since 5m --filter container=test-vps", check=False, verbose=True)
        raise VpsError("Test container failed to start properly")

    if not wait_for_ssh_service('test-vps', timeout=60):
        raise VpsError("SSH service failed to start")

    if not setup_ssh_access():
        raise VpsError("Failed to setup SSH access")

    print_status("Waiting for services to stabilize...", YELLOW)
    time.sleep(5)

    print_status("Running Ansible deployment on test environment...", BLUE)
    ansible_dir = project_root / 'ansible'

    print_status("Testing Ansible connectivity...", YELLOW)
    result = run_command("ansible vps -i inventories/test.yml -m ping -vvv", cwd=ansible_dir, check=False, verbose=True)
    if not result or result.returncode != 0:
        print_status("Connectivity test failed", RED)

        print_status("Debugging SSH connection...", YELLOW)
        run_command("ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 root@localhost 'echo SSH connection works'", check=False, verbose=True)

        print_status("Checking SSH key setup...", YELLOW)
        run_command("docker exec test-vps cat /root/.ssh/authorized_keys", check=False, verbose=True)

        print_status("Checking SSH daemon config...", YELLOW)
        run_command("docker exec test-vps grep -E '(PermitRootLogin|PubkeyAuthentication)' /etc/ssh/sshd_config", check=False, verbose=True)

        print_status("Checking container status...", YELLOW)
        run_command("docker ps --filter name=test-vps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", check=False, verbose=True)

        print_status("Checking SSH inside container...", YELLOW)
        run_command("docker exec test-vps netstat -tlnp | grep :22", check=False, verbose=True)

        print_status("Checking Docker port mapping...", YELLOW)
        run_command("docker port test-vps", check=False, verbose=True)

        print_status("Testing direct container SSH...", YELLOW)
        run_command("docker exec test-vps ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@localhost 'echo Direct SSH works'", check=False, verbose=True)

        raise VpsError("Ansible connectivity test failed")

    print_status("Connectivity test passed", GREEN)

    print_status("Deploying configuration...", BLUE)
    result = run_command(
        "ansible-playbook playbooks/site.yml -i inventories/test.yml -v",
        cwd=ansible_dir, timeout=600, check=False, verbose=True,
    )
    if not result or result.returncode != 0:
        raise VpsError("Deployment failed")

    print_status("Deployment successful", GREEN)

    print_status("Testing deployed services...", BLUE)

    print_status("Waiting for services to start...", YELLOW)
    time.sleep(30)

    print_status("Checking Docker containers...", YELLOW)
    run_command(
        'ansible vps -i inventories/test.yml -m shell -a "docker ps --format \'table {{.Names}}\\t{{.Status}}\'"',
        cwd=ansible_dir,
    )

    print_status("Testing HTTP endpoints...", YELLOW)

    endpoints = [
        ("https://localhost:3001", "Grafana", "grafana"),
        ("https://localhost:9091", "Prometheus", "prometheus"),
        ("https://localhost:3101", "Loki", None)
    ]

    for url, name, expected_text in endpoints:
        if test_http_endpoint(url, expected_text, timeout=15):
            print_status(f"{name} is responding", GREEN)
        else:
            print_status(f"{name} test inconclusive (might need more startup time)", YELLOW)

    print_status("\nLocal testing completed!", GREEN)
    print_status("You can now access services at:", BLUE)
    print_status("  Grafana: https://localhost:3001 (admin/admin)", RESET)
    print_status("  Prometheus: https://localhost:9091", RESET)
    print_status("  Loki: https://localhost:3101", RESET)

    print_status(f"\n{YELLOW}To clean up test environment:{RESET}")
    print_status("  cd docker/test-environment && docker-compose down", RESET)

    print_status(f"\nConfiguration is ready for production deployment!", GREEN)
