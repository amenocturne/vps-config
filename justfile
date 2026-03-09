# VPS Configuration Management

# List all available commands
default:
    @just --list

# Run all validation tests (fast mode - skips Docker pulls)
validate:
    @echo "🔍 Running validation tests..."
    SKIP_DOCKER_PULL=true uv run validate

# Run full validation including Docker image pulls
validate-full:
    @echo "🔍 Running full validation tests..."
    uv run validate

# Test configuration locally with Docker
test-local:
    @echo "🧪 Testing configuration locally..."
    uv run test-local

# Clean up local test environment
test-clean:
    @echo "🧹 Cleaning up test environment..."
    cd docker/test-environment && docker-compose down --remove-orphans -v

# Setup inventory file (copy and customize)
setup:
    @echo "⚙️ Setting up inventory file..."
    @if [ ! -f ansible/inventories/production.yml ]; then \
        cp ansible/inventories/hosts.yml ansible/inventories/production.yml; \
        echo "✅ Created production.yml - please customize with your VPS IP and domain"; \
    else \
        echo "⚠️  production.yml already exists"; \
    fi

# Deploy all services to VPS
deploy:
    @echo "🚀 Deploying to VPS..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml

# Deploy all services to VPS with verbose output
deploy-verbose:
    @echo "🚀 Deploying to VPS (verbose)..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml -v

# Check Ansible syntax
check:
    @echo "🔍 Checking Ansible syntax..."
    cd ansible && ansible-playbook playbooks/site.yml --syntax-check -i inventories/production.yml

# Run Ansible in dry-run mode
dry-run:
    @echo "🧪 Running Ansible dry-run..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml --check

# Test VPS connectivity
ping:
    @echo "📡 Testing VPS connectivity..."
    cd ansible && ansible vps -i inventories/production.yml -m ping

# Run health checks
health-check:
    @echo "🔍 Running health checks..."
    uv run health-check production

# Restart specific service
restart service:
    @echo "🔄 Restarting {{service}}..."
    cd ansible && ansible vps -i inventories/production.yml -m shell -a "docker restart {{service}}"

# View service logs
logs service:
    @echo "📋 Viewing {{service}} logs..."
    cd ansible && ansible vps -i inventories/production.yml -m shell -a "docker logs --tail 50 {{service}}"

# Clean temporary files
clean:
    @echo "🧹 Cleaning temporary files..."
    find . -name "*.retry" -delete

# Update Caddyfile only
update-caddy:
    @echo "🔄 Updating Caddyfile..."
    @echo "📄 Generating and copying Caddyfile..."
    cd ansible && ansible vps -i inventories/production.yml -m template -a "src=roles/caddy/templates/Caddyfile.j2 dest=/opt/caddy/Caddyfile mode=0644" --become
    @echo "🔄 Restarting Caddy container..."
    cd ansible && ansible vps -i inventories/production.yml -m docker_container -a "name=caddy restart=yes" --become

# Deploy Authelia only
deploy-authelia:
    @echo "🔒 Deploying Authelia..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml --tags authelia

# Deploy Caddy only
deploy-caddy:
    @echo "🌐 Deploying Caddy..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml --tags caddy

# Deploy Grafana only
deploy-grafana:
    @echo "📊 Deploying Grafana..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml --tags grafana

# Reset Authelia user bans and regulation
reset-authelia-bans:
    @echo "🔓 Resetting Authelia bans..."
    cd ansible && ansible vps -i inventories/production.yml -m shell -a "docker exec authelia rm -f /data/db.sqlite3"
    @echo "🔄 Restarting Authelia..."
    cd ansible && ansible vps -i inventories/production.yml -m shell -a "docker restart authelia"
    @echo "✅ Authelia bans cleared and service restarted"

# SSH to VPS
ssh command="uptime":
    @echo "🔐 Running command on VPS: {{command}}"
    cd ansible && ansible vps -i inventories/production.yml -m shell -a "{{command}}"

@authelia-hash password:
  docker run --rm authelia/authelia:latest authelia crypto hash generate --password '{{password}}'

# Remnawave VPN Server Commands

# Deploy Remnawave to VPN server
deploy-remnawave:
    @echo "🚀 Deploying Remnawave to VPN server..."
    cd ansible && ansible-playbook playbooks/remnawave.yml -i inventories/remnawave-test.yml

# Deploy Remnawave with verbose output
deploy-remnawave-verbose:
    @echo "🚀 Deploying Remnawave (verbose)..."
    cd ansible && ansible-playbook playbooks/remnawave.yml -i inventories/remnawave-test.yml -v

# Check Remnawave playbook syntax
check-remnawave:
    @echo "🔍 Checking Remnawave playbook syntax..."
    cd ansible && ansible-playbook playbooks/remnawave.yml --syntax-check -i inventories/remnawave-test.yml

# Run Remnawave deployment in dry-run mode
dry-run-remnawave:
    @echo "🧪 Running Remnawave dry-run..."
    cd ansible && ansible-playbook playbooks/remnawave.yml -i inventories/remnawave-test.yml --check

# Test Remnawave VPN server connectivity
ping-remnawave:
    @echo "📡 Testing Remnawave VPN server connectivity..."
    cd ansible && ansible remnawave -i inventories/remnawave-test.yml -m ping

# Update main server's Caddy configuration (for reverse proxy)
update-main-caddy:
    @echo "🔄 Updating main server's Caddy configuration..."
    cd ansible && ansible-playbook playbooks/site.yml -i inventories/production.yml --tags caddy

# Restart Remnawave services
restart-remnawave:
    @echo "🔄 Restarting Remnawave services..."
    cd ansible && ansible remnawave -i inventories/remnawave-test.yml -m shell -a "cd /opt/remnawave && docker compose restart"

# View Remnawave logs
logs-remnawave service="remnawave":
    @echo "📋 Viewing Remnawave {{service}} logs..."
    cd ansible && ansible remnawave -i inventories/remnawave-test.yml -m shell -a "docker logs --tail 50 {{service}}"

# SSH to Remnawave VPN server
ssh-remnawave command="uptime":
    @echo "🔐 Running command on Remnawave VPN server: {{command}}"
    cd ansible && ansible remnawave -i inventories/remnawave-test.yml -m shell -a "{{command}}"

# VPN Nodes Deployment Commands

# Deploy all VPN nodes
deploy-nodes:
    @echo "🚀 Deploying all VPN nodes..."
    cd ansible && ansible-playbook playbooks/node.yml -i inventories/nodes.yml

# Deploy all VPN nodes with verbose output
deploy-nodes-verbose:
    @echo "🚀 Deploying all VPN nodes (verbose)..."
    cd ansible && ansible-playbook playbooks/node.yml -i inventories/nodes.yml -v

# Check nodes playbook syntax
check-nodes:
    @echo "🔍 Checking nodes playbook syntax..."
    cd ansible && ansible-playbook playbooks/node.yml --syntax-check -i inventories/nodes.yml

# Run nodes deployment in dry-run mode
dry-run-nodes:
    @echo "🧪 Running nodes deployment dry-run..."
    cd ansible && ansible-playbook playbooks/node.yml -i inventories/nodes.yml --check

# Test all nodes connectivity
ping-nodes:
    @echo "📡 Testing all nodes connectivity..."
    cd ansible && ansible remnawave_nodes -i inventories/nodes.yml -m ping

# View logs from all nodes
logs-nodes service="remnanode":
    @echo "📋 Viewing {{service}} logs from all nodes..."
    cd ansible && ansible remnawave_nodes -i inventories/nodes.yml -m shell -a "docker logs --tail 50 {{service}}"

# Restart all node services
restart-nodes:
    @echo "🔄 Restarting all node services..."
    cd ansible && ansible remnawave_nodes -i inventories/nodes.yml -m shell -a "docker restart remnanode"

# SSH to all nodes
ssh-nodes command="uptime":
    @echo "🔐 Running command on all nodes: {{command}}"
    cd ansible && ansible remnawave_nodes -i inventories/nodes.yml -m shell -a "{{command}}"

# Deploy specific node by name (e.g., node-1, node-2)
deploy-node-single node:
    @echo "🚀 Deploying {{node}}..."
    cd ansible && ansible-playbook playbooks/node.yml -i inventories/nodes.yml --limit {{node}}

# View logs from specific node
logs-node-single node service="remnanode":
    @echo "📋 Viewing {{service}} logs from {{node}}..."
    cd ansible && ansible {{node}} -i inventories/nodes.yml -m shell -a "docker logs --tail 50 {{service}}"

# Extract SSL certificates from nodes for panel trust
extract-node-certs:
    @echo "🔐 Extracting node SSL certificates..."
    ./scripts/extract-node-certificates.sh

# Diagnose VPN connectivity issues
diagnose-vpn:
    @echo "🔍 Diagnosing VPN connectivity..."
    ./scripts/diagnose-vpn-connectivity.sh

# Remnawave Config Management

# Export current Remnawave panel state to state.yml
export-remnawave-config:
    uv run export-config

# Sync Remnawave panel state to match state.yml (pass --apply to execute, default is --plan)
sync-remnawave-config *ARGS:
    uv run sync-config {{ARGS}}
