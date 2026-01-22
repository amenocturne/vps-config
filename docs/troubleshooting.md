# Troubleshooting Guide

This guide covers common issues, diagnostic procedures, and solutions for the VPS configuration.

## Table of Contents
- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [Service-Specific Issues](#service-specific-issues)
- [Network and SSL Issues](#network-and-ssl-issues)
- [Authentication Problems](#authentication-problems)
- [Monitoring Issues](#monitoring-issues)
- [Performance Problems](#performance-problems)
- [Emergency Recovery](#emergency-recovery)

## Quick Diagnostics

### Health Check Commands
```bash
# Run comprehensive health check
just health-check

# Check VPS connectivity
just ping

# Verify all services are running
just ssh "docker ps"

# Check service logs
just logs <service-name>

# Check system resources
just ssh "free -h && df -h && uptime"
```

### Service Status Check
```bash
# Check all containers
just ssh "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# Check container resource usage
just ssh "docker stats --no-stream"

# View recent container events
just ssh "docker events --since '1h' --until '0s'"
```

## Common Issues

### 1. Deployment Fails

**Symptoms**: Ansible playbook fails during deployment

**Diagnostic Steps**:
```bash
# Check Ansible syntax
just check

# Run with verbose output
just deploy-verbose

# Test connectivity
just ping
```

**Common Causes & Solutions**:

#### SSH Connection Issues
```bash
# Error: "SSH timeout" or "Connection refused"
# Solution: Check SSH configuration and connectivity
ssh -v your-vps-ip

# Check SSH service
just ssh "sudo systemctl status ssh"

# Verify SSH port
just ssh "sudo ss -tlnp | grep :22"
```

#### Permission Errors
```bash
# Error: "sudo: a password is required"
# Solution: Verify sudo access
ssh your-vps-ip "sudo whoami"

# Check sudoers configuration
just ssh "sudo cat /etc/sudoers.d/90-cloud-init-users"
```

#### Python/Ansible Issues
```bash
# Error: "No module named 'apt_pkg'"
# Solution: Install Python dependencies
just ssh "sudo apt update && sudo apt install -y python3-apt"
```

### 2. Services Won't Start

**Symptoms**: Docker containers fail to start or immediately exit

**Diagnostic Steps**:
```bash
# Check container logs
just logs <service-name>

# Check Docker daemon status
just ssh "sudo systemctl status docker"

# Check available disk space
just ssh "df -h"

# Check available memory
just ssh "free -h"
```

**Common Solutions**:

#### Out of Disk Space
```bash
# Clean up Docker resources
just ssh "docker system prune -f"

# Remove unused images
just ssh "docker image prune -a -f"

# Check large log files
just ssh "sudo du -sh /var/log/*"
```

#### Port Conflicts
```bash
# Check what's using a port
just ssh "sudo ss -tlnp | grep :9090"

# Kill process using port
just ssh "sudo fuser -k 9090/tcp"
```

#### Memory Issues
```bash
# Check memory usage
just ssh "free -h"

# Check for OOMKilled containers
just ssh "dmesg | grep -i 'killed process'"

# Restart services with memory issues
just restart <service-name>
```

### 3. Can't Access Services

**Symptoms**: Services return 502/503 errors or timeouts

**Diagnostic Steps**:
```bash
# Check Caddy logs
just logs caddy

# Test service health directly
just ssh "curl -I http://localhost:3000"  # Grafana
just ssh "curl -I http://localhost:9090"  # Prometheus

# Check DNS resolution
nslookup grafana.yourdomain.com
```

**Solutions**:

#### DNS Issues
```bash
# Verify DNS records point to correct IP
dig A grafana.yourdomain.com

# Check DNS propagation
nslookup grafana.yourdomain.com 8.8.8.8
```

#### Caddy Configuration Issues
```bash
# Check Caddy configuration syntax
just ssh "docker exec caddy caddy validate --config /etc/caddy/Caddyfile"

# Reload Caddy configuration
just ssh "docker exec caddy caddy reload --config /etc/caddy/Caddyfile"

# Check Caddy health
just ssh "curl -s http://localhost:2019/config/ | jq '.'"
```

## Service-Specific Issues

### Remnawave VPN Connection Issues

#### VPN Client Timeouts (Reality Works, WebSocket Doesn't)

**Symptoms**: 
- Reality protocol connections work fine
- VLESS + WebSocket connections timeout
- Nodes show as "Online" in panel
- Panel can communicate with nodes

**Root Cause**: DNS/Cloudflare misconfiguration for VLESS + WebSocket protocol

**Quick Diagnostic**:
```bash
# Run automated diagnostic
just diagnose-vpn

# Manual check - should return Cloudflare IPs (104.x or 172.x), NOT node IPs
dig +short nl1.rutube.dad
dig +short us1.rutube.dad
```

**Solutions**:

1. **Fix DNS Records in Cloudflare**:
   - Go to Cloudflare DNS settings for your domain (`rutube.dad`)
   - For EACH node, add/update A record:
     - `nl1` → `64.111.92.2` (node-1 IP)
     - `us1` → `162.33.177.182` (node-2 IP)
   - **CRITICAL**: Enable Cloudflare Proxy (click cloud icon until it's ORANGE)
   
2. **Enable WebSocket in Cloudflare**:
   - Go to Cloudflare → Network settings
   - Enable **WebSocket** toggle
   - Save changes

3. **Verify SSL Settings**:
   - Go to Cloudflare → SSL/TLS
   - Set to **Full (strict)**
   - Enable "Always Use HTTPS"

4. **Verify Changes**:
   ```bash
   # DNS should now return Cloudflare IPs
   dig +short nl1.rutube.dad
   # Expected: 104.x.x.x or 172.x.x.x (Cloudflare)
   # NOT: 64.111.92.2 (your node IP)
   
   # Check Cloudflare is proxying
   curl -I https://nl1.rutube.dad | grep cf-ray
   # Should show: cf-ray header
   ```

5. **Test VPN Connection**:
   - Wait 2-5 minutes for DNS changes to propagate
   - Reconnect VPN client
   - VLESS + WebSocket should now work

**See detailed guide**: `docs/REMNAWAVE_DNS_SETUP.md`

#### Nodes Timing Out in Panel (Node Offline)

**Symptoms**: VPN nodes show as offline or timeout when clients try to connect through the panel

**Root Cause**: The panel cannot establish a secure TLS connection to nodes on port 2222

**Common Causes**:
1. Panel doesn't have node SSL certificates in its CA bundle
2. Nodes not running or not listening on port 2222
3. Firewall blocking port 2222
4. Network connectivity issues between panel and nodes

**Diagnostic Steps**:
```bash
# 1. Check if nodes are running
just ssh-nodes "docker ps | grep remnanode"

# 2. Check if port 2222 is listening on nodes
just ssh-nodes "ss -tlnp | grep :2222"

# 3. Test TLS connectivity from control machine
for node in 64.111.92.2 162.33.177.182; do
  echo "Testing $node..."
  echo "" | timeout 5 openssl s_client -connect $node:2222 2>/dev/null | grep -E "Verify return code|subject="
done

# 4. Check panel has node certificates
just ssh-remnawave "cat /opt/remnawave/certs/remnawave-nodes-ca.pem"

# 5. Check panel .env configuration
just ssh-remnawave "grep NODE_EXTRA_CA_CERTS /opt/remnawave/.env"

# 6. Check panel logs for TLS errors
just logs-remnawave | grep -i "tls\|certificate\|timeout\|node"

# 7. Check node logs
just logs-nodes
```

**Solutions**:

**IMPORTANT**: This setup uses SECURE TLS connections. We do NOT bypass certificate validation.

1. **Re-extract Node Certificates** (Recommended):
   ```bash
   # Deploy nodes first to ensure they're running
   just deploy-nodes
   
   # Redeploy panel - this will auto-extract node certificates
   just deploy-remnawave
   
   # Verify certificates were extracted
   just ssh-remnawave "wc -l /opt/remnawave/certs/remnawave-nodes-ca.pem"
   # Should show multiple lines (one cert per node)
   ```

2. **Manual Certificate Extraction** (if auto-extraction fails):
   ```bash
   # On your local machine, extract from each node
   echo "" | openssl s_client -connect 64.111.92.2:2222 -showcerts 2>/dev/null | \
     openssl x509 -outform PEM > node-1-cert.pem
   
   echo "" | openssl s_client -connect 162.33.177.182:2222 -showcerts 2>/dev/null | \
     openssl x509 -outform PEM > node-2-cert.pem
   
   # Combine into CA bundle
   cat node-*-cert.pem > remnawave-nodes-ca.pem
   
   # Copy to panel server
   scp remnawave-nodes-ca.pem root@YOUR_PANEL_IP:/opt/remnawave/certs/
   
   # Set permissions
   just ssh-remnawave "chown remnawave:remnawave /opt/remnawave/certs/remnawave-nodes-ca.pem"
   just ssh-remnawave "chmod 644 /opt/remnawave/certs/remnawave-nodes-ca.pem"
   
   # Restart panel
   just ssh-remnawave "cd /opt/remnawave && docker compose restart"
   ```

3. **Verify Certificates Are Working**:
   ```bash
   # Check panel logs for successful node connections
   just logs-remnawave | tail -50
   
   # Check node status in panel UI
   # Visit https://panel.yourdomain.com/nodes
   # Nodes should show as "Online" with green status
   ```

**Prevention**:
- Always deploy nodes BEFORE deploying the panel
- Ensure port 2222 is accessible from your control machine during deployment
- Keep firewall rules open for port 2222
- Re-run panel deployment after adding new nodes to update certificate bundle

#### Node Communication Port Blocked

**Symptoms**: Panel shows "Node offline" or "Connection refused"

**Diagnostic Steps**:
```bash
# Check firewall rules on node
just ssh-nodes "sudo ufw status | grep 2222"

# Test from panel server
just ssh-remnawave "nc -zv NODE_IP 2222"

# Check if node is listening
just ssh-nodes "ss -tlnp | grep :2222"
```

**Solutions**:
```bash
# Ensure firewall allows port 2222
just ssh-nodes "sudo ufw allow 2222/tcp comment 'Remnawave panel API'"

# Verify node container is running with host network
just ssh-nodes "docker inspect remnanode | grep NetworkMode"
# Should show: "NetworkMode": "host"

# Restart node if needed
just restart-nodes
```

#### Node SSL Certificate Issues

**Symptoms**: TLS handshake errors, certificate verification failures

**Diagnostic Steps**:
```bash
# Check if node has SSL certificates
just ssh-nodes "ls -la /opt/remnanode/certs/"

# View certificate details
just ssh-nodes "openssl x509 -in /opt/remnanode/certs/fullchain.pem -text -noout | grep -A 2 'Validity'"

# Test TLS connection
just ssh-remnawave "openssl s_client -connect NODE_IP:2222 -showcerts"
```

**Solutions**:
```bash
# Panel now automatically disables TLS verification when needed
# If issues persist, check panel .env file
just ssh-remnawave "grep TLS /opt/remnawave/.env"

# Should show either:
# NODE_EXTRA_CA_CERTS=/etc/ssl/certs/node-ca.pem
# OR
# NODE_TLS_REJECT_UNAUTHORIZED=0
```

### Authelia Problems

#### Can't Login / "Incorrect Password"
```bash
# Check username format (use 'admin', not email)
# Username: admin (not admin@yourdomain.com)

# Verify password hash generation
just authelia-hash 'your-password'

# Check user database
just ssh "cat /opt/authelia/config/users_database.yml"

# Check Authelia logs
just logs authelia

# Clear failed attempts (if account is banned)
just reset-authelia-bans
```

#### 2FA Setup Issues
```bash
# Check Authelia configuration
just ssh "cat /opt/authelia/config/configuration.yml | grep -A 10 totp"

# Verify time synchronization (critical for TOTP)
just ssh "timedatectl status"

# Reset 2FA for user (requires manual database edit)
just ssh "sqlite3 /opt/authelia/data/db.sqlite3 'DELETE FROM totp_configurations WHERE username=\"admin\";'"
```

#### Session Issues
```bash
# Check Redis connection
just ssh "docker exec authelia redis-cli -h redis ping"

# Clear all sessions
just ssh "docker exec redis redis-cli FLUSHALL"

# Check session domain configuration
just logs authelia | grep -i session
```

### Grafana Issues

#### Admin Password Problems
```bash
# Reset admin password
just ssh "docker exec grafana grafana-cli admin reset-admin-password newpassword"

# Check Grafana logs for authentication issues
just logs grafana | grep -i auth
```

#### Dashboard Loading Issues
```bash
# Check datasource connectivity
just ssh "curl -s http://localhost:3000/api/datasources | jq '.'"

# Test Prometheus connectivity from Grafana
just ssh "docker exec grafana wget -qO- http://prometheus:9090/api/v1/query?query=up"

# Verify dashboard provisioning
just ssh "ls -la /opt/grafana/dashboards/"
```

### Prometheus Issues

#### No Metrics Data
```bash
# Check Prometheus targets
just ssh "curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health, lastError}'"

# Verify Node Exporter
just ssh "curl -s http://localhost:9100/metrics | head -10"

# Check Prometheus configuration
just ssh "curl -s http://localhost:9090/api/v1/status/config | jq '.data.yaml' -r"
```

#### Storage Issues
```bash
# Check Prometheus storage usage
just ssh "du -sh /opt/prometheus/data/"

# Check retention settings
just logs prometheus | grep -i retention

# Verify write permissions
just ssh "ls -la /opt/prometheus/"
```

### Caddy Issues

#### SSL Certificate Problems
```bash
# Check certificate status
just ssh "docker exec caddy caddy list-certificates"

# Check certificate errors
just logs caddy | grep -i "certificate\|ssl\|tls"

# Manually trigger certificate renewal
just ssh "docker exec caddy caddy reload --config /etc/caddy/Caddyfile"
```

#### Reverse Proxy Issues
```bash
# Check upstream connectivity
just ssh "docker exec caddy wget -qO- http://grafana:3000/api/health"

# Verify Caddy can reach backend services
just ssh "docker network inspect vps-config_default"

# Test proxy configuration
just ssh "curl -H 'Host: grafana.yourdomain.com' http://localhost"
```

## Network and SSL Issues

### SSL Certificate Problems

#### Certificate Not Obtained
```bash
# Check Let's Encrypt rate limits
# Visit: https://crt.sh/?q=yourdomain.com

# Verify DNS points to correct IP
dig A yourdomain.com

# Check port 80 accessibility (required for challenge)
curl -I http://yourdomain.com

# Check Caddy logs for ACME errors
just logs caddy | grep -i "acme\|certificate\|challenge"
```

#### Certificate Expired
```bash
# Check certificate expiration
echo | openssl s_client -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates

# Force certificate renewal
just ssh "docker exec caddy caddy reload --config /etc/caddy/Caddyfile"
```

### DNS Resolution Issues

```bash
# Test DNS resolution from different servers
dig @8.8.8.8 grafana.yourdomain.com
dig @1.1.1.1 grafana.yourdomain.com

# Check DNS propagation globally
# Use online tools like whatsmydns.net

# Verify DNS records are correct
dig ANY yourdomain.com
```

### Firewall Issues

```bash
# Check UFW status and rules
just ssh "sudo ufw status verbose"

# Test port accessibility
just ssh "sudo ss -tlnp | grep :443"

# Temporarily disable firewall for testing (CAUTION!)
just ssh "sudo ufw disable"  # Remember to re-enable!

# Check for blocked connections
just ssh "sudo tail -f /var/log/ufw.log"
```

## Authentication Problems

### Authelia Authentication Flow Issues

#### Forward Auth Not Working
```bash
# Check Caddy forward auth configuration
just ssh "cat /opt/caddy/Caddyfile | grep -A 5 forward_auth"

# Test auth endpoint directly
curl -I https://auth.yourdomain.com/api/verify

# Check headers being passed
just logs caddy | grep -i "Remote-User\|Remote-Groups"
```

#### Redirect Loops
```bash
# Check default redirection URL
just ssh "cat /opt/authelia/config/configuration.yml | grep default_redirection_url"

# Verify access control rules
just ssh "cat /opt/authelia/config/configuration.yml | grep -A 20 access_control"

# Test with curl to see redirect headers
curl -v https://grafana.yourdomain.com
```

### Session Management Issues

```bash
# Check Redis connectivity
just ssh "docker exec authelia redis-cli -h redis ping"

# View active sessions
just ssh "docker exec redis redis-cli KEYS 'authelia:*'"

# Clear stuck sessions
just ssh "docker exec redis redis-cli FLUSHDB"

# Check session configuration
just logs authelia | grep -i session
```

## Monitoring Issues

### Metrics Not Appearing

#### Prometheus Scraping Issues
```bash
# Check target status
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'

# Verify scrape configs
curl -s http://localhost:9090/api/v1/status/config

# Test individual exporters
curl http://localhost:9100/metrics  # Node Exporter
curl http://localhost:8080/metrics  # cAdvisor
```

#### Grafana Dashboard Issues
```bash
# Check datasource health
curl -s http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up

# Verify dashboard JSON
just ssh "ls -la /opt/grafana/dashboards/*.json"

# Check dashboard provisioning logs
just logs grafana | grep -i dashboard
```

### Log Aggregation Issues

#### Promtail Not Collecting Logs
```bash
# Check Promtail configuration
just ssh "cat /opt/promtail/config.yml"

# Verify log file accessibility
just ssh "ls -la /var/log/containers/"

# Check Promtail status
just logs promtail

# Test Loki connectivity
just ssh "docker exec promtail wget -qO- http://loki:3100/ready"
```

#### Loki Query Issues
```bash
# Test Loki API directly
curl -s 'http://localhost:3100/loki/api/v1/labels'

# Check Loki storage
just ssh "du -sh /opt/loki/data/"

# Verify log ingestion
curl -s 'http://localhost:3100/loki/api/v1/query_range?query={job="docker"}&limit=10'
```

## Performance Problems

### High Resource Usage

#### Memory Issues
```bash
# Check memory usage by container
just ssh "docker stats --no-stream --format 'table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}'"

# Check for memory leaks
just ssh "free -h && sync && echo 3 > /proc/sys/vm/drop_caches && free -h"

# Adjust container memory limits
# Edit docker-compose files and set memory limits
```

#### Disk Space Issues
```bash
# Check disk usage
just ssh "df -h"

# Find large files
just ssh "sudo find /opt -type f -size +100M -exec ls -lh {} +"

# Clean up Docker resources
just ssh "docker system prune -a -f"

# Rotate and compress logs
just ssh "sudo logrotate -f /etc/logrotate.d/docker-container"
```

#### High CPU Usage
```bash
# Check CPU usage by container
just ssh "docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}'"

# Check system load
just ssh "uptime && top -bn1 | head -20"

# Analyze process activity
just ssh "sudo iotop -ao"
```

### Slow Response Times

#### Network Latency
```bash
# Test internal container connectivity
just ssh "docker exec caddy ping -c 3 grafana"
just ssh "docker exec grafana ping -c 3 prometheus"

# Check DNS resolution times
just ssh "time nslookup grafana.yourdomain.com"

# Test external connectivity
just ssh "ping -c 3 8.8.8.8"
```

#### Database Performance
```bash
# Check Prometheus query performance
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_samples_appended_total'

# Monitor SQLite performance (Authelia)
just ssh "sqlite3 /opt/authelia/data/db.sqlite3 'PRAGMA optimize;'"
```

## Emergency Recovery

### Complete System Recovery

#### If All Services Are Down
```bash
# 1. Check system basics
just ssh "systemctl status"
just ssh "docker ps -a"

# 2. Restart Docker daemon
just ssh "sudo systemctl restart docker"

# 3. Start services manually
just ssh "cd /opt && docker-compose up -d"

# 4. Full redeployment if needed
just deploy
```

#### If SSH Access Is Lost
1. **Use VPS provider console** (DigitalOcean, AWS, etc.)
2. **Check SSH service**: `systemctl status ssh`
3. **Reset SSH configuration**: 
   ```bash
   sudo cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
   sudo systemctl restart ssh
   ```
4. **Check firewall rules**: `ufw status`

#### If Domain/DNS Issues Prevent Access
```bash
# Access services directly via IP
http://YOUR_VPS_IP:3000  # Grafana
http://YOUR_VPS_IP:9090  # Prometheus

# Bypass Caddy entirely if needed
just ssh "docker stop caddy"
```

### Data Recovery

#### Backup and Restore
```bash
# Create emergency backup
just ssh "tar -czf /tmp/vps-backup-$(date +%Y%m%d).tar.gz /opt/"

# Restore from backup
just ssh "cd / && tar -xzf /tmp/vps-backup-YYYYMMDD.tar.gz"
```

### Logging and Debugging

#### Enable Debug Logging
```bash
# Authelia debug mode
just ssh "docker exec authelia sed -i 's/level: info/level: debug/' /config/configuration.yml"
just restart authelia

# Caddy debug mode
just ssh "docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile"

# Docker daemon debug
just ssh "sudo systemctl edit docker"
# Add: Environment="DOCKERD_OPTS=--debug"
```

#### Collect Debug Information
```bash
# System information
just ssh "uname -a && lsb_release -a && uptime"

# Service versions
just ssh "docker --version && docker-compose --version"

# Container information
just ssh "docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"

# Network information
just ssh "docker network ls && ip addr show"

# Resource usage
just ssh "free -h && df -h && docker system df"
```

### Getting Help

When reporting issues, include:

1. **Error messages** from logs
2. **System information** (OS version, Docker version)
3. **Configuration files** (sanitized, no secrets)
4. **Steps to reproduce** the issue
5. **Expected vs actual behavior**

**Log Collection Command**:
```bash
# Collect all relevant logs
just ssh "journalctl -u docker --since '1 hour ago' > /tmp/docker.log"
just logs caddy > /tmp/caddy.log
just logs authelia > /tmp/authelia.log
just logs grafana > /tmp/grafana.log
just logs prometheus > /tmp/prometheus.log
```