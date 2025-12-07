# Remnawave VPN Setup Guide

Complete step-by-step guide to deploy Remnawave VPN using this Ansible configuration.

## What You're Building

A VPN system with:
- **Panel/Backend**: Management interface for users and nodes
- **Subscription Page**: User subscription links
- **VPN Nodes**: Servers that route VPN traffic with two connection methods:
  - **VLESS + WebSocket + TLS**: Routes through Cloudflare CDN (bypasses IP whitelists)
  - **VLESS + Reality**: Direct connection masquerading as legitimate traffic (bypasses DPI/SNI filtering)

## Prerequisites

- VPS with Ubuntu 22.04+ or Debian 11+ (minimum 1GB RAM, 10GB disk)
- Root SSH access
- Domain name (e.g., `amenocturne.space`)
- Cloudflare account (free tier is sufficient)
- Just task runner: `brew install just`
- uv package manager: `brew install uv`

## Part 1: Generate Secrets (5 minutes)

Run these commands to generate all required secrets:

```bash
# 1. Generate Reality keys (CRITICAL - write these down!)
docker run --rm teddysun/xray:latest xray x25519
# Output:
# PrivateKey: xxx  ← Copy this for reality_private_key (server uses this)
# Password: yyy    ← Copy this for reality_public_key (clients use this)
# Hash32: zzz      ← Ignore this

# 2. Generate Reality short ID
openssl rand -hex 8
# Copy this for reality_short_id

# 3. Generate JWT secrets (run twice for two different secrets)
openssl rand -hex 32
# First output → jwt_auth_secret
openssl rand -hex 32
# Second output → jwt_api_tokens_secret

# 4. Generate passwords (run three times)
openssl rand -hex 16  # → metrics_pass
openssl rand -hex 16  # → webhook_secret  
openssl rand -hex 16  # → postgres_password
```

## Part 2: Configure Secrets (5 minutes)

### 2.1 Create Secrets File

```bash
cd /Users/skril/Vault/Projects/my-projects/vps-config

# Copy the secrets template
cp ansible/inventories/remnawave-test/.secrets.yml.example \
   ansible/inventories/remnawave-test/.secrets.yml

# Edit the file
nano ansible/inventories/remnawave-test/.secrets.yml
```

### 2.2 Fill in Values

Paste the values you generated in Part 1:

```yaml
# JWT Secrets
jwt_auth_secret: "PASTE_64_CHAR_HEX_FROM_STEP_3_FIRST"
jwt_api_tokens_secret: "PASTE_64_CHAR_HEX_FROM_STEP_3_SECOND"

# Metrics and database
metrics_pass: "PASTE_32_CHAR_HEX_FROM_STEP_4_FIRST"
webhook_secret: "PASTE_32_CHAR_HEX_FROM_STEP_4_SECOND"
postgres_password: "PASTE_32_CHAR_HEX_FROM_STEP_4_THIRD"

# Reality Configuration (SAME for ALL nodes)
reality_private_key: "PASTE_PRIVATE_KEY_FROM_STEP_1"  # Server uses this
reality_public_key: "PASTE_PASSWORD_FROM_STEP_1"      # Clients use this
reality_short_id: "PASTE_SHORT_ID_FROM_STEP_2"

# Node Secret Keys (leave empty for now - we'll get these from the panel)
node_secret_keys:
  node-1: ""  # We'll fill this after creating the node in the panel
```

**IMPORTANT**: 
- The `reality_private_key` is the "PrivateKey" output from xray x25519
- The `reality_public_key` is the "Password" output from xray x25519 (yes, it's confusing naming!)
- These Reality keys must be IDENTICAL across all nodes

## Part 3: Configure Inventory (3 minutes)

Edit `ansible/inventories/remnawave-test.yml` and update these values:

```yaml
all:
  hosts:
    remnawave:
      ansible_host: 64.111.92.2  # ← YOUR VPS IP HERE
      ansible_ssh_private_key_file: ~/.ssh/bitlaunch  # ← YOUR SSH KEY PATH

  vars:
    domain_name: "amenocturne.space"  # ← YOUR DOMAIN
    remnawave_panel_subdomain: "panel.amenocturne.space"  # ← YOUR PANEL SUBDOMAIN
    remnawave_frontend_domain: "panel.amenocturne.space"
    remnawave_sub_domain: "sub.amenocturne.space"  # ← YOUR SUBSCRIPTION SUBDOMAIN
    vpn_subdomain: "static.amenocturne.space"  # ← YOUR VPN CLOUDFLARE SUBDOMAIN
```

## Part 4: Deploy Panel and Backend (10 minutes)

### 4.1 Validate Configuration

```bash
# Quick validation
just validate

# Check Remnawave playbook syntax
just check-remnawave
```

### 4.2 Deploy

```bash
# Deploy everything (panel, backend, subscription page, node)
just deploy-remnawave

# Or deploy with verbose output if you want to see details
just deploy-remnawave-verbose
```

This deploys:
- PostgreSQL database
- Redis for sessions
- Remnawave backend API
- Remnawave subscription page
- Caddy reverse proxy
- VPN node software

### 4.3 Verify Deployment

```bash
# Check containers are running
just ssh-remnawave "docker ps"

# You should see: remnawave, postgres, redis, caddy, remnanode
```

## Part 5: Set Up DNS (5 minutes + waiting time)

### 5.1 Add Domain to Cloudflare

1. Go to https://dash.cloudflare.com
2. Click **Add a site**
3. Enter your domain: `amenocturne.space`
4. Choose **Free** plan
5. Update nameservers at your domain registrar (shown in Cloudflare)
6. **Wait for DNS propagation** (can take up to 24 hours, usually 10-30 minutes)

### 5.2 Create DNS Records

Once nameservers are active, add these DNS records:

| Type | Name   | Content       | Proxy Status |
|------|--------|---------------|--------------|
| A    | panel  | 64.111.92.2   | Proxied ☁️   |
| A    | sub    | 64.111.92.2   | Proxied ☁️   |
| A    | static | 64.111.92.2   | Proxied ☁️   |

**CRITICAL**: The orange cloud (Proxied) must be enabled for all records!

### 5.3 Configure Cloudflare Settings

**SSL/TLS Settings:**
1. Go to **SSL/TLS** → **Overview**
2. Set mode to: **Full (strict)**
3. Go to **SSL/TLS** → **Edge Certificates**
4. Enable:
   - ✅ Always Use HTTPS
   - ✅ Minimum TLS Version: TLS 1.2

**Network Settings:**
1. Go to **Network**
2. Enable:
   - ✅ **WebSocket**: ON (CRITICAL for VPN!)
   - ✅ HTTP/2: ON
   - ✅ gRPC: ON (optional)

### 5.4 Verify DNS

```bash
# Should return Cloudflare IPs (104.x.x.x, 172.x.x.x), NOT your VPS IP
dig panel.amenocturne.space
dig sub.amenocturne.space
dig static.amenocturne.space
```

## Part 6: Access Panel and Register Node (10 minutes)

### 6.1 Access the Panel

Open in your browser: `https://panel.amenocturne.space`

**First-time setup:**
1. You'll see the registration page
2. Create your admin account (save these credentials!)

### 6.2 Register Your Node in the Panel

This is crucial - you need to register the node to get its SECRET_KEY:

1. Login to the panel
2. Go to **Nodes** section (in left sidebar)
3. Click **Add Node** or **Create Node**
4. Fill in:
   - **Name**: `Netherlands` (or your node location)
   - **Address**: `64.111.92.2` (your VPS IP)
   - **Port**: `2222`
5. Click **Create**
6. **COPY THE SECRET_KEY** - it looks like: `sk_abc123...`

### 6.3 Add Secret Key to Configuration

```bash
# Edit your secrets file
nano ansible/inventories/remnawave-test/.secrets.yml

# Find the node_secret_keys section and paste the key:
node_secret_keys:
  node-1: "sk_abc123...YOUR_SECRET_KEY_FROM_PANEL"
```

### 6.4 Redeploy to Apply Secret Key

```bash
# Redeploy just the node with the new secret key
just deploy-remnawave
```

### 6.5 Verify Node is Online

1. Go back to the panel
2. Go to **Nodes** section
3. Your node should now show as **Online** (green indicator)

If it's not online after 30 seconds, check logs:
```bash
just logs-remnawave remnanode
```

## Part 7: Configure Inbounds (10 minutes)

Now configure the VPN protocols in the panel.

### 7.1 Create VLESS + WebSocket Inbound (Primary Method)

This routes through Cloudflare for IP whitelist bypass.

1. In the panel, go to **Inbounds**
2. Click **Create Inbound**
3. Fill in:

```
Tag: vless-ws-cloudflare
Protocol: VLESS
Port: 443
Network: WebSocket (or ws)
Path: /api/v2/ws
Host / Server Name: static.amenocturne.space
TLS / Security: Enabled
SNI: static.amenocturne.space
ALPN: h2,http/1.1 (if available)
Node: Select your node
```

4. Click **Save**

### 7.2 Create VLESS + Reality Inbound (Backup Method)

This is for direct connections bypassing DPI/SNI filtering.

1. Click **Create Inbound** again
2. Fill in:

```
Tag: vless-reality-backup
Protocol: VLESS
Port: 8443
Network: TCP
Security: Reality
Flow: xtls-rprx-vision (REQUIRED!)
Destination: www.speedtest.net:443
Server Names: www.speedtest.net, speedtest.net
Private Key: (paste reality_private_key from .secrets.yml)
Short IDs: ["", "your_short_id_here"]
Node: Select your node
```

**IMPORTANT**: 
- Use the **private key** (reality_private_key) on the server
- DO NOT use the public key/password in the panel - the panel generates client configs automatically
- The empty string `""` in short IDs allows connections without a short ID

3. Click **Save**

### 7.3 Verify Inbounds

Both inbounds should show as **Active** or **Running** in the Inbounds page.

## Part 8: Create User and Test (10 minutes)

### 8.1 Create a Test User

1. Go to **Users** → **Create User**
2. Fill in:
   - **Username**: `test-user` (or your name)
   - **Email**: (optional)
   - **Traffic Limit**: `50` GB
   - **Expiry Date**: (leave empty or set future date)
3. **IMPORTANT**: Check BOTH inbounds:
   - ☑ vless-ws-cloudflare
   - ☑ vless-reality-backup
4. Click **Create**

### 8.2 Get Subscription Link

1. Click on the user you just created
2. Find **Subscription URL** or **Sub Link**
3. Copy it (looks like: `https://sub.amenocturne.space/api/sub/uuid-here`)

### 8.3 Import to VPN Client

Choose your VPN client:
- **Windows**: v2rayN
- **Android**: v2rayNG
- **iOS**: Shadowrocket
- **Linux**: Nekoray

**For v2rayNG (Android):**
1. Open v2rayNG
2. Tap **+** (top right)
3. Select **Import config from clipboard** or **Subscription**
4. Paste the subscription URL
5. Tap **Update subscription**
6. You should see 2 servers appear

**For v2rayN (Windows):**
1. Open v2rayN
2. **Subscription** → **Subscription settings**
3. Click **Add**
4. Paste URL in **URL** field
5. Click **OK**
6. **Subscription** → **Update subscription**

### 8.4 Test Connections

**Test Primary (Cloudflare):**
1. Select `vless-ws-cloudflare` profile
2. Connect
3. Visit https://ipinfo.io
4. Verify your IP has changed (should NOT be your real IP)

**Test Backup (Reality):**
1. Disconnect from primary
2. Select `vless-reality-backup` profile
3. Connect
4. Visit https://ipinfo.io
5. Verify your IP has changed

## Part 9: Add More Users (2 minutes per user)

To add family members or friends:

1. Go to **Users** → **Create User**
2. Fill in details
3. Assign both inbounds
4. Send them the subscription link
5. They import and connect!

Each user can have their own:
- Traffic limits
- Expiry dates
- Access to specific inbounds

## Troubleshooting

### Panel Not Accessible

**Check containers:**
```bash
just ssh-remnawave "docker ps"
```

Should show: remnawave, postgres, redis, caddy

**Check logs:**
```bash
just logs-remnawave remnawave
just logs-remnawave caddy
```

**Verify DNS:**
```bash
dig panel.amenocturne.space
# Should show Cloudflare IP, not your VPS IP
```

### Node Shows Offline

**Check logs:**
```bash
just logs-remnawave remnanode
```

**Common issues:**
- Wrong SECRET_KEY in `.secrets.yml`
- Firewall blocking port 2222
- Node container not running

**Restart node:**
```bash
just ssh-remnawave "docker restart remnanode"
```

Wait 30 seconds and check panel again.

### Primary Connection (Cloudflare) Fails

**Check Cloudflare settings:**
- ✅ DNS record has orange cloud (Proxied) enabled
- ✅ WebSocket is ON in Network settings
- ✅ SSL/TLS mode is "Full (strict)"

**Check inbound configuration:**
- Path is `/api/v2/ws` (with leading slash)
- TLS is enabled
- Port is 443

**Check logs:**
```bash
just logs-remnawave remnanode
```

### Reality Connection Fails

**Verify Reality keys:**
```bash
# Check your secrets file
cat ansible/inventories/remnawave-test/.secrets.yml | grep reality
```

**Make sure:**
- You used the **private key** in the panel (not the password/public key)
- Destination is `www.speedtest.net:443` (with :443)
- Flow is set to `xtls-rprx-vision`

**Test destination is accessible:**
```bash
curl -I https://www.speedtest.net
# Should return HTTP/2 200
```

### Connection Drops After ~100 Seconds

This is Cloudflare's WebSocket idle timeout.

**Fix in VPN client:**
- **v2rayN**: Settings → Core Settings → Mux → Concurrency: 8
- **v2rayNG**: Settings → Enable "Mux"
- **Nekoray**: Preferences → Connection Settings → TCP Keep Alive: ON

### Both Connections Fail

**Check ports are listening:**
```bash
just ssh-remnawave "ss -tlnp | grep -E '443|8443'"
```

Should show both ports listening.

**Restart all services:**
```bash
just restart-remnawave
```

Wait 10 seconds, try connecting again.

## Quick Command Reference

```bash
# Deployment
just deploy-remnawave              # Deploy all Remnawave components
just deploy-remnawave-verbose      # Deploy with verbose output

# Validation
just check-remnawave               # Check syntax
just dry-run-remnawave             # Preview changes

# Monitoring
just ping-remnawave                # Test connectivity
just logs-remnawave remnawave      # View panel logs
just logs-remnawave remnanode      # View node logs
just ssh-remnawave "command"       # Run custom command

# Maintenance
just restart-remnawave             # Restart all services
just ssh-remnawave "docker ps"     # Check containers
```

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                      YOUR VPS (64.111.92.2)                 │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐     │
│  │   Panel     │  │ Subscription │  │   VPN Node    │     │
│  │  (port 3000)│  │    Page      │  │               │     │
│  └──────┬──────┘  └──────┬───────┘  │ VLESS+WS: 443 │     │
│         │                │           │ Reality: 8443 │     │
│         │                │           │ Node API: 2222│     │
│  ┌──────┴────────────────┴──────┐   └───────────────┘     │
│  │     Caddy Reverse Proxy      │                          │
│  │         (port 80/443)         │                          │
│  └──────────┬───────────────────┘                          │
└─────────────┼──────────────────────────────────────────────┘
              │
              ▼
     Cloudflare CDN Proxy
     (panel.*, sub.*, static.*)
              │
              ▼
┌─────────────┴──────────────┐
│     VPN Clients            │
│  (v2rayN, v2rayNG, etc.)   │
└────────────────────────────┘
```

## What You've Accomplished

✅ Deployed Remnawave panel for VPN management
✅ Configured VPN node with two connection methods
✅ Set up Cloudflare CDN routing (IP whitelist bypass)
✅ Configured Reality protocol (DPI/SNI bypass)
✅ Created users and tested connections
✅ Ready to add unlimited users and manage traffic

## Next Steps

### Add More Nodes (Optional)

See `docs/deploying-multiple-nodes.md` for:
- Deploying nodes in different geographic locations
- Load balancing across multiple nodes
- High availability setup

### Monitor Usage

In the panel dashboard:
- View total traffic
- Monitor per-user usage
- Check node status and performance

### Manage Users

- Set individual traffic limits
- Configure expiry dates
- Enable/disable users
- View connection logs

---

**Your Remnawave VPN is now fully operational!**

For additional help:
- Check container logs: `just logs-remnawave <service>`
- Restart services: `just restart-remnawave`
- Test connectivity: `just ping-remnawave`
