# Remnawave VPN DNS Setup Guide

## Why DNS Configuration is Critical

Remnawave nodes use **two VPN protocols**:

1. **VLESS + Reality** (Port 8443) - Direct connection to node IP
   - ✅ Works: Connects directly to node's IP address
   - No DNS or Cloudflare required
   
2. **VLESS + WebSocket + TLS** (Port 443) - Through Cloudflare CDN
   - ❌ Timeouts if DNS not configured correctly
   - **REQUIRES**: DNS records proxied through Cloudflare
   - **WHY**: Routes traffic through Cloudflare IPs to bypass IP-based blocking

## Current Configuration Issue

Based on your `nodes.yml`:
- **node-1** (Netherlands): Uses domain `nl1.rutube.dad` → IP `64.111.92.2`
- **node-2** (US): Uses domain `us1.rutube.dad` → IP `162.33.177.182`

### Problem Identified

```bash
# Check current DNS resolution
$ dig +short nl1.rutube.dad
64.111.92.2  # ❌ WRONG - Returns actual node IP (Cloudflare proxy OFF)

$ dig +short us1.rutube.dad
# ❌ WRONG - No DNS record exists
```

**Expected behavior (when Cloudflare proxy is ON):**
```bash
$ dig +short nl1.rutube.dad
104.21.x.x   # ✅ CORRECT - Returns Cloudflare IP
172.67.x.x   # ✅ CORRECT - Returns Cloudflare IP
```

## Required DNS Setup

### Step 1: Add DNS Records in Cloudflare

Go to your Cloudflare dashboard for domain `rutube.dad`:

**DNS Records to Create:**

| Type | Name | Target/Content    | Proxy Status        | Notes |
|------|------|-------------------|---------------------|-------|
| A    | nl1  | 64.111.92.2       | ☁️ Proxied (ORANGE) | Node 1 (Netherlands) |
| A    | us1  | 162.33.177.182    | ☁️ Proxied (ORANGE) | Node 2 (US) |

**CRITICAL**: The cloud icon MUST be **ORANGE** (Proxied), NOT gray (DNS only)

### Step 2: Verify Cloudflare Settings

In Cloudflare dashboard for `rutube.dad`:

1. **SSL/TLS Settings** → Overview
   - Encryption mode: **Full (strict)** ✅
   
2. **SSL/TLS** → Edge Certificates
   - Always Use HTTPS: **ON** ✅
   - Minimum TLS Version: **TLS 1.2** ✅

3. **Network Settings**
   - **WebSocket: ON** ✅ (CRITICAL!)
   - HTTP/2: ON ✅
   - gRPC: ON ✅ (optional)

4. **Speed** → Optimization
   - Auto Minify: Can be enabled
   - Brotli: ON ✅

### Step 3: Verify DNS Propagation

```bash
# Should return Cloudflare IPs (104.x.x.x or 172.x.x.x), NOT your node IPs
dig nl1.rutube.dad
dig us1.rutube.dad

# Test from multiple DNS servers
dig @8.8.8.8 nl1.rutube.dad    # Google DNS
dig @1.1.1.1 nl1.rutube.dad    # Cloudflare DNS

# Check globally (use online tool)
# https://www.whatsmydns.net/#A/nl1.rutube.dad
```

### Step 4: Test WebSocket Connection

```bash
# Test if Cloudflare is proxying WebSocket correctly
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Host: nl1.rutube.dad" \
     -H "Origin: https://nl1.rutube.dad" \
     https://nl1.rutube.dad/api/v2/ws

# Expected: 101 Switching Protocols (or 426 Upgrade Required)
# Bad: Connection timeout or refused
```

## Troubleshooting

### Issue: DNS Returns Node IP Instead of Cloudflare IP

**Cause**: Cloudflare proxy (orange cloud) is disabled

**Fix**:
1. Go to Cloudflare DNS settings
2. Click on the cloud icon next to the DNS record
3. Change from gray (DNS only) to orange (Proxied)
4. Wait 1-2 minutes for changes to propagate

### Issue: DNS Record Doesn't Exist

**Cause**: DNS record not created yet

**Fix**:
1. Add A record in Cloudflare
2. Set target to node IP
3. Enable proxy (orange cloud)

### Issue: WebSocket Connection Fails

**Cause**: WebSocket not enabled in Cloudflare

**Fix**:
1. Go to Cloudflare → Network
2. Enable WebSocket
3. Wait a few minutes for settings to propagate

### Issue: SSL/TLS Errors

**Cause**: Incorrect SSL mode or certificate issues

**Fix**:
1. Ensure SSL mode is "Full (strict)" in Cloudflare
2. Verify node has valid SSL certificates in `/opt/remnanode/certs/`
3. Check firewall allows port 443:
   ```bash
   just ssh-nodes "sudo ufw status | grep 443"
   ```

## Verification Commands

### On Nodes (Run on each VPN node)

```bash
# Check if node is listening on port 443
ss -tlnp | grep :443

# Check Docker container
docker ps | grep remnanode

# View node logs
docker logs remnanode -f

# Test local WebSocket
curl -k -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     https://127.0.0.1:443/api/v2/ws
```

### From Panel/Client

```bash
# Test DNS resolution
nslookup nl1.rutube.dad
nslookup us1.rutube.dad

# Test HTTPS connectivity
curl -I https://nl1.rutube.dad
curl -I https://us1.rutube.dad

# Check if Cloudflare is in the path
curl -I https://nl1.rutube.dad | grep -i cf-ray
# Should show: cf-ray header (confirms Cloudflare proxy)
```

## Quick Fix Checklist

Run through this checklist to fix timeout issues:

- [ ] DNS A record exists for each node domain
- [ ] Cloudflare proxy is ENABLED (orange cloud) for each record
- [ ] WebSocket is enabled in Cloudflare Network settings
- [ ] SSL mode is "Full (strict)" in Cloudflare
- [ ] DNS resolves to Cloudflare IPs (104.x.x.x or 172.x.x.x), NOT node IPs
- [ ] Nodes are listening on port 443 (`ss -tlnp | grep :443`)
- [ ] Firewall allows port 443 TCP and UDP
- [ ] Node certificates exist in `/opt/remnanode/certs/`
- [ ] Panel shows nodes as "Online"

## Understanding the Two Protocols

### Why Two Different Protocols?

1. **VLESS + WebSocket + TLS (through Cloudflare)**
   - **Purpose**: Bypass IP-based blocking
   - **How**: Routes through Cloudflare's IPs which are globally whitelisted
   - **Port**: 443 (HTTPS standard port)
   - **Requires**: Cloudflare DNS proxy enabled
   - **Best for**: Countries with IP-based censorship

2. **VLESS + Reality (direct connection)**
   - **Purpose**: Bypass DPI/SNI inspection
   - **How**: Masquerades as legitimate HTTPS traffic to speedtest.net
   - **Port**: 8443 (custom port)
   - **Requires**: Only direct IP connectivity
   - **Best for**: Countries with deep packet inspection

### When to Use Each

- Use **WebSocket variant** when Cloudflare is properly configured
- Use **Reality variant** as fallback or when Cloudflare is blocked
- Clients should auto-fail-over between protocols

## After DNS Changes

After making DNS changes in Cloudflare:

1. **Wait 1-5 minutes** for changes to propagate
2. **Clear VPN client cache** (if applicable)
3. **Reconnect** VPN connections
4. **Test both protocols** in your VPN client

## Additional Resources

- Cloudflare DNS Documentation: https://developers.cloudflare.com/dns/
- Cloudflare WebSocket Support: https://developers.cloudflare.com/support/websockets/
- VLESS Protocol: https://xtls.github.io/config/outbound/vless.html
