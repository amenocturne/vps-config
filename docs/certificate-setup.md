# Certificate Setup for Remnawave VPN

## Quick Start: Move Your Existing Certificates

You already have Cloudflare Origin CA certificates. Let's move them to the correct location:

```bash
# From project root
cd /Users/skril/Vault/Projects/my-projects/vps-config

# Move certificates to inventory-specific location
mv certificates/fullchain.pem ansible/inventories/remnawave-test/certs/
mv certificates/key.pem ansible/inventories/remnawave-test/certs/

# Set secure permissions
chmod 644 ansible/inventories/remnawave-test/certs/fullchain.pem
chmod 600 ansible/inventories/remnawave-test/certs/key.pem

# Verify files are in place
ls -lh ansible/inventories/remnawave-test/certs/
```

**Expected output:**
```
-rw-r--r--  fullchain.pem
-rw-------  key.pem
-rw-r--r--  README.md
```

## Certificate File Structure

### Per-Environment Certificates

Certificates are stored **per-inventory** to support multiple environments:

```
ansible/inventories/
├── remnawave-test/
│   ├── certs/
│   │   ├── fullchain.pem  ← Your certificate chain
│   │   ├── key.pem        ← Your private key (SECRET!)
│   │   └── README.md
│   ├── .secrets.yml
│   └── remnawave-test.yml
│
├── production/  (if you have production env)
│   ├── certs/
│   │   ├── fullchain.pem
│   │   └── key.pem
│   └── ...
```

**Why per-inventory?**
- Different environments may use different certificates
- Keeps secrets organized and environment-specific
- Easy to manage renewals per environment

## Certificate Types

### Option 1: Cloudflare Origin CA (What You Have)

**Pros:**
- ✅ Valid for 15 years (no frequent renewal)
- ✅ Free and easy to generate
- ✅ Perfect for Cloudflare-proxied domains
- ✅ Works even if VPS IP changes

**Cons:**
- ❌ Only trusted when accessed through Cloudflare
- ❌ Direct IP access shows "untrusted certificate" (but that's fine for VPN)

**Where to get:**
1. Cloudflare Dashboard → SSL/TLS → Origin Server
2. Create Certificate
3. Save certificate as `fullchain.pem`
4. Save private key as `key.pem`

### Option 2: Let's Encrypt

**Pros:**
- ✅ Publicly trusted certificate
- ✅ Works with or without Cloudflare
- ✅ Free and automated

**Cons:**
- ❌ Valid for only 90 days (needs renewal)
- ❌ Requires port 80 open for validation
- ❌ More complex renewal automation

**How to get:**
```bash
# On the VPS
certbot certonly --standalone \
  -d static.amenocturne.space \
  --email your-email@example.com \
  --agree-tos

# Copy to your local machine
scp root@64.111.92.2:/etc/letsencrypt/live/static.amenocturne.space/fullchain.pem \
    ansible/inventories/remnawave-test/certs/
scp root@64.111.92.2:/etc/letsencrypt/live/static.amenocturne.space/privkey.pem \
    ansible/inventories/remnawave-test/certs/key.pem
```

## How Ansible Handles Certificates

### During Deployment

When you run `just deploy`, Ansible will:

1. **Check for certificates** in `ansible/inventories/remnawave-test/certs/`
2. **Create certs directory** on VPS: `/opt/remnanode/certs/`
3. **Copy fullchain.pem** with permissions `644` (readable)
4. **Copy key.pem** with permissions `600` (secure, owner-only)
5. **Mount into container** as `/etc/xray/certs/` (read-only)

### In Docker Container

The certificates are mounted to the Xray container:

```yaml
volumes:
  - '/opt/remnanode/certs:/etc/xray/certs:ro'
```

**Container paths:**
- Certificate: `/etc/xray/certs/fullchain.pem`
- Private key: `/etc/xray/certs/key.pem`

### In Remnawave Panel Configuration

When configuring VLESS + WebSocket inbound, you'll reference:

```
TLS Certificate: /etc/xray/certs/fullchain.pem
TLS Key: /etc/xray/certs/key.pem
```

**Note:** Remnawave panel may handle this automatically. If it asks for cert paths, use the above.

## Security & Git

### What's Protected

The `.gitignore` automatically excludes:

```gitignore
# All certificate files
*.pem
*.crt
*.key
certificates/
ansible/inventories/**/certs/
```

**Files that ARE committed:**
- ✅ `certs/README.md` (documentation)
- ✅ `certs/.gitkeep` (if you create one)

**Files that are NOT committed:**
- ❌ `certs/fullchain.pem` (public cert - not secret but excluded anyway)
- ❌ `certs/key.pem` (SECRET private key - NEVER commit!)

### Verify Certificates Are Ignored

```bash
# Check if files are ignored
git check-ignore -v ansible/inventories/remnawave-test/certs/fullchain.pem
git check-ignore -v ansible/inventories/remnawave-test/certs/key.pem

# Should output:
# .gitignore:XX:*.pem    ansible/inventories/remnawave-test/certs/fullchain.pem
# .gitignore:XX:*.pem    ansible/inventories/remnawave-test/certs/key.pem
```

### Check Nothing Is Staged

```bash
# Make sure no certificate files are staged for commit
git status ansible/inventories/remnawave-test/certs/

# Should output:
# nothing to commit (or only README.md)
```

## Certificate Verification

### Verify Certificate Details

```bash
# View certificate information
openssl x509 -in ansible/inventories/remnawave-test/certs/fullchain.pem -text -noout

# Check subject and issuer
openssl x509 -in ansible/inventories/remnawave-test/certs/fullchain.pem -noout -subject -issuer

# Check validity dates
openssl x509 -in ansible/inventories/remnawave-test/certs/fullchain.pem -noout -dates
```

### Verify Key Matches Certificate

```bash
# Get certificate modulus hash
openssl x509 -noout -modulus -in ansible/inventories/remnawave-test/certs/fullchain.pem | openssl md5

# Get private key modulus hash
openssl rsa -noout -modulus -in ansible/inventories/remnawave-test/certs/key.pem | openssl md5

# Both should output the SAME hash
```

**Example:**
```
(stdin)= a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6  ← Certificate hash
(stdin)= a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6  ← Key hash (MUST MATCH!)
```

### Verify Certificate Covers Your Domain

```bash
# Check Subject Alternative Names (SAN)
openssl x509 -in ansible/inventories/remnawave-test/certs/fullchain.pem -noout -text | grep -A1 "Subject Alternative Name"

# Should show:
# Subject Alternative Name:
#   DNS:*.amenocturne.space, DNS:amenocturne.space
```

## Certificate Deployment Workflow

### Initial Setup

```bash
# 1. Generate/obtain certificate (Cloudflare Origin CA)
# 2. Save files to inventory certs directory
mv /path/to/cert.pem ansible/inventories/remnawave-test/certs/fullchain.pem
mv /path/to/key.pem ansible/inventories/remnawave-test/certs/key.pem

# 3. Set permissions
chmod 644 ansible/inventories/remnawave-test/certs/fullchain.pem
chmod 600 ansible/inventories/remnawave-test/certs/key.pem

# 4. Deploy
just deploy
```

### Certificate Renewal (When Needed)

For **Cloudflare Origin CA** (15-year validity):
```bash
# Only needed every 15 years or if compromised
# 1. Generate new certificate in Cloudflare Dashboard
# 2. Replace existing files
mv new-fullchain.pem ansible/inventories/remnawave-test/certs/fullchain.pem
mv new-key.pem ansible/inventories/remnawave-test/certs/key.pem

# 3. Redeploy
just deploy

# 4. Restart node
ssh root@64.111.92.2 "docker restart remnanode"
```

For **Let's Encrypt** (90-day validity):
```bash
# Set up auto-renewal on VPS
ssh root@64.111.92.2

# Install certbot renewal timer
systemctl enable certbot.timer
systemctl start certbot.timer

# Add post-renewal hook to restart node
echo "#!/bin/bash
docker restart remnanode
" > /etc/letsencrypt/renewal-hooks/deploy/restart-remnanode.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/restart-remnanode.sh
```

## Troubleshooting

### Certificates Not Found During Deployment

**Error:**
```
⚠️ WARNING: SSL certificates not found!
```

**Fix:**
```bash
# Verify files exist
ls -lh ansible/inventories/remnawave-test/certs/

# Should show:
# fullchain.pem
# key.pem

# If missing, add them:
cp /path/to/fullchain.pem ansible/inventories/remnawave-test/certs/
cp /path/to/key.pem ansible/inventories/remnawave-test/certs/
```

### Permission Denied Errors

**Error:**
```
Permission denied reading key.pem
```

**Fix:**
```bash
# Make key readable by you
chmod 600 ansible/inventories/remnawave-test/certs/key.pem

# Ensure you own the file
sudo chown $USER:$USER ansible/inventories/remnawave-test/certs/key.pem
```

### Certificate/Key Mismatch

**Error:**
```
SSL: error:0B080074:x509 certificate routines
```

**Fix:**
```bash
# Verify certificate and key match (see "Verify Key Matches Certificate" above)
# If they don't match, regenerate/re-download both as a pair
```

### Container Can't Read Certificates

**Error in docker logs:**
```
failed to load certificate: open /etc/xray/certs/fullchain.pem: no such file or directory
```

**Fix:**
```bash
# Check certificates exist on VPS
ssh root@64.111.92.2 "ls -lh /opt/remnanode/certs/"

# If missing, redeploy
just deploy

# Restart container
ssh root@64.111.92.2 "docker restart remnanode"
```

### Certificate Shows as Untrusted

**Scenario:** Direct access to `https://64.111.92.2:443` shows untrusted certificate

**This is NORMAL for Cloudflare Origin CA:**
- Origin CA certs are only trusted when accessed through Cloudflare
- VPN clients connect through Cloudflare proxy, so they see Cloudflare's trusted cert
- Direct IP access shows "untrusted" but this doesn't affect VPN functionality

**Not a problem for:**
- ✅ VPN connections (go through Cloudflare)
- ✅ Remnawave panel access (separate cert)

**Only an issue if:**
- ❌ You want direct IP access to work with trusted cert
- **Solution:** Use Let's Encrypt instead

## File Locations Reference

### Local (Development Machine)

```
/Users/skril/Vault/Projects/my-projects/vps-config/
└── ansible/inventories/remnawave-test/certs/
    ├── fullchain.pem  ← Source certificate
    ├── key.pem        ← Source private key
    └── README.md
```

### Remote (VPS)

```
/opt/remnanode/
├── certs/
│   ├── fullchain.pem  ← Copied by Ansible
│   └── key.pem        ← Copied by Ansible (mode 600)
└── docker-compose.yml
```

### Docker Container

```
/etc/xray/certs/  ← Mounted read-only from /opt/remnanode/certs/
├── fullchain.pem
└── key.pem
```

## Summary

**Quick checklist for certificate setup:**

1. ✅ Move certificates to `ansible/inventories/remnawave-test/certs/`
2. ✅ Verify files: `fullchain.pem` and `key.pem`
3. ✅ Set permissions: `chmod 644 fullchain.pem && chmod 600 key.pem`
4. ✅ Verify ignored by git: `git status certs/`
5. ✅ Verify certificate matches key (see verification section)
6. ✅ Deploy: `just deploy`
7. ✅ Verify copied to VPS: `ssh root@64.111.92.2 "ls -lh /opt/remnanode/certs/"`

**Done!** Certificates are now deployed and mounted in the container.
