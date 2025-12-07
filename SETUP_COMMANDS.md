# Remnawave VPN Setup - Command Checklist

Quick reference for setting up your VPN. Run these commands in order.

## Step 1: Move Certificates (2 minutes)

```bash
cd /Users/skril/Vault/Projects/my-projects/vps-config

# Move certificates to correct location
mv certificates/fullchain.pem ansible/inventories/remnawave-test/certs/
mv certificates/key.pem ansible/inventories/remnawave-test/certs/

# Set secure permissions
chmod 644 ansible/inventories/remnawave-test/certs/fullchain.pem
chmod 600 ansible/inventories/remnawave-test/certs/key.pem

# Verify
ls -lh ansible/inventories/remnawave-test/certs/
# Should show: fullchain.pem, key.pem, README.md
```

## Step 2: Generate Reality Keys (1 minute)

```bash
# Generate Reality keys
docker run --rm teddysun/xray:latest xray x25519

# Example output:
# PrivateKey: KOUIR-WsM_PPY0edEuzm6LsWIrRbj4lswecll91WGWg  ← Save for SERVER
# Password: -iPbJXrK7XygDR4SSH-jgRxb62WNZITowRUgwixwXQA    ← Save for CLIENT
# Hash32: 9DOaPfPgj-i-gDKpKkeJJ9pFUQM10Jw5N6eeaeHSgO0      ← (not needed)

# Generate short ID
openssl rand -hex 8
# Example output: a1b2c3d4e5f6g7h8  ← Save this
```

## Step 3: Update Secrets File (3 minutes)

```bash
# Edit secrets file
nano ansible/inventories/remnawave-test/.secrets.yml
```

Add these values (using your generated keys from Step 2):

```yaml
# Use PrivateKey output for server
reality_private_key: "PASTE_PRIVATEKEY_FROM_STEP2"

# Use Password output for client  
reality_public_key: "PASTE_PASSWORD_FROM_STEP2"

# Use generated short ID
reality_short_id: "PASTE_SHORT_ID_FROM_STEP2"
```

**Important:** Also add `remnawave_node_secret_key`

How to get it:
1. Login to https://panel.amenocturne.space
2. Go to **Nodes** section
3. Click **"Create Node"** (if first time) or edit existing node
4. Fill in: Name, Address (64.111.92.2), Port (2222)
5. Save and **copy the SECRET_KEY** that appears
6. Paste into `.secrets.yml`

**See detailed guide:** `docs/getting-node-secret-key.md`

Save and exit (Ctrl+X, Y, Enter)

## Step 4: Deploy to VPS (2 minutes)

```bash
# Deploy configuration
just deploy

# Or manually:
ansible-playbook -i ansible/inventories/remnawave-test.yml \
  ansible/playbooks/remnawave.yml \
  --tags "remnawave-node"
```

**Watch for:**
- ✅ Certificates copied to VPS
- ✅ Docker container restarted
- ✅ Firewall rules updated (ports 443, 8443)

## Step 5: Verify Deployment (1 minute)

```bash
# SSH to VPS and check
ssh root@64.111.92.2 -i ~/.ssh/bitlaunch

# Check container is running
docker ps | grep remnanode

# Check certificates are present
ls -lh /opt/remnanode/certs/

# Check ports are listening
ss -tlnp | grep -E '443|8443'

# View logs
docker logs remnanode -f
# Press Ctrl+C to exit logs

# Exit VPS
exit
```

## Step 6: Configure Inbounds in Panel (10 minutes)

Open https://panel.amenocturne.space and follow `docs/remnawave-panel-configuration.md`

**Quick summary:**

### Inbound 1: VLESS + WebSocket
- Tag: `vless-ws-cloudflare`
- Protocol: VLESS
- Port: `443`
- Network: WebSocket
- Path: `/api/v2/ws`
- Host: `static.amenocturne.space`
- TLS: Enabled
- Cert: `/etc/xray/certs/fullchain.pem`
- Key: `/etc/xray/certs/key.pem`

### Inbound 2: VLESS + Reality
- Tag: `vless-reality-backup`
- Protocol: VLESS
- Port: `8443`
- Network: TCP
- Security: Reality
- Flow: `xtls-rprx-vision`
- Destination: `www.speedtest.net:443`
- Server Names: `www.speedtest.net`, `speedtest.net`
- Private Key: (from .secrets.yml)
- Short IDs: (from .secrets.yml)

## Step 7: Create Test User (2 minutes)

In panel:
1. Users → Create User
2. Username: your-name
3. Traffic: 50GB
4. Assign both inbounds ✅✅
5. Copy subscription link

## Step 8: Test Connection (5 minutes)

### Import to Client

**v2rayNG (Android):**
```
+ → Import config from clipboard → Paste subscription URL → Update
```

**v2rayN (Windows):**
```
Subscription → Subscription settings → Add → Paste URL → OK → Update
```

### Test

1. Select `vless-ws-cloudflare`
2. Connect
3. Visit https://ipinfo.io
4. Verify IP changed ✅

## Troubleshooting Quick Fixes

### Certificates not found
```bash
ls ansible/inventories/remnawave-test/certs/
# If empty, go back to Step 1
```

### Container not running
```bash
ssh root@64.111.92.2 "docker restart remnanode && docker logs remnanode -f"
```

### Can't connect via Cloudflare
```bash
# Check WebSocket is ON in Cloudflare Network settings
# Check orange cloud is enabled on DNS record
# Check logs: ssh root@64.111.92.2 "docker logs remnanode -f"
```

### Reality connection fails
```bash
# Verify keys match (from same x25519 generation)
# Check destination: curl -I https://www.speedtest.net
```

## Summary Checklist

- [ ] Certificates moved to `ansible/inventories/remnawave-test/certs/`
- [ ] Reality keys generated and added to `.secrets.yml`
- [ ] `remnawave_node_secret_key` added to `.secrets.yml`
- [ ] Deployed with `just deploy`
- [ ] Container running on VPS
- [ ] Certificates present in `/opt/remnanode/certs/`
- [ ] Ports 443 and 8443 listening
- [ ] VLESS + WebSocket inbound created in panel
- [ ] VLESS + Reality inbound created in panel
- [ ] Test user created and assigned to both inbounds
- [ ] Subscription link obtained
- [ ] VPN client connects successfully
- [ ] IP changes when connected

## Files Reference

- **Certificates**: `ansible/inventories/remnawave-test/certs/`
- **Secrets**: `ansible/inventories/remnawave-test/.secrets.yml`
- **Inventory**: `ansible/inventories/remnawave-test.yml`
- **Full guide**: `docs/remnawave-panel-configuration.md`
- **Certificate help**: `docs/certificate-setup.md`
- **Quick start**: `QUICK_START_VPN.md`

## Done!

Your VPN is now ready to bypass IP whitelists via Cloudflare CDN! 🎉
