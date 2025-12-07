# Deploying Multiple VPN Nodes

Add additional VPN nodes in different geographic locations. All nodes connect to your single Remnawave panel.

## Prerequisites

- Main Remnawave panel already deployed (see `REMNAWAVE_SETUP.md`)
- Additional VPS(es) with Ubuntu 22.04+ or Debian 11+
- Root SSH access to new VPS(es)
- Same `.secrets.yml` from main deployment (Reality keys must be identical across all nodes!)

## Quick Start

### 1. Edit Node Inventory

Edit `ansible/inventories/nodes.yml`:

```yaml
all:
  children:
    remnawave_nodes:
      hosts:
        node-1:
          ansible_host: 64.111.92.2              # ← Node 1 IP
          node_name: "Netherlands"               # ← Display name in panel
          vless_ws_domain: "static.amenocturne.space"

        node-2:
          ansible_host: 162.33.177.182           # ← Node 2 IP  
          node_name: "Germany"                   # ← Display name
          vless_ws_domain: "static-de.amenocturne.space"  # ← Can use different subdomain

        # Add more nodes as needed
```

**Note**: You can use the same `vless_ws_domain` for all nodes, or create different subdomains.

### 2. Register Nodes in Panel

**IMPORTANT**: Do this BEFORE deployment to get SECRET_KEYs!

For each node:

1. Login to https://panel.amenocturne.space
2. Go to **Nodes** section
3. Click **Add Node**
4. Fill in:
   - **Name**: `Germany` (matches `node_name` in inventory)
   - **Address**: `162.33.177.182` (node's IP)
   - **Port**: `2222`
5. Click **Create**
6. **COPY THE SECRET_KEY** (looks like: `sk_abc123...`)

Repeat for all nodes.

### 3. Add Secret Keys

Edit `ansible/inventories/remnawave-test/.secrets.yml`:

```yaml
# Add all node secret keys here
node_secret_keys:
  node-1: "sk_existing_key_for_node_1"
  node-2: "sk_abc123_NEW_KEY_FROM_PANEL"  # ← Add new node keys

# CRITICAL: Keep the SAME Reality keys for ALL nodes
reality_private_key: "SAME_AS_EXISTING"  # ← DO NOT CHANGE
reality_public_key: "SAME_AS_EXISTING"   # ← DO NOT CHANGE
reality_short_id: "SAME_AS_EXISTING"     # ← DO NOT CHANGE
```

**CRITICAL**: All nodes MUST use identical Reality keys!

### 4. Setup SSL Certificates (One Time)

Create certificate directory (if not exists):

```bash
mkdir -p ansible/inventories/nodes/certs
```

Get Cloudflare Origin CA certificate:
1. Cloudflare Dashboard → SSL/TLS → Origin Server
2. Create Certificate:
   - Hostnames: `*.amenocturne.space`, `amenocturne.space`
   - Validity: 15 years
3. Save files:
   - Certificate → `ansible/inventories/nodes/certs/fullchain.pem`
   - Private Key → `ansible/inventories/nodes/certs/key.pem`

**These same certificates work for ALL nodes!**

### 5. Add DNS Records (If Using Different Subdomains)

If you're using different subdomains like `static-de.amenocturne.space`:

In Cloudflare Dashboard → DNS:
- **Type**: A
- **Name**: `static-de`
- **IPv4**: Node's IP (e.g., 162.33.177.182)
- **Proxy**: ☁️ **ENABLED** (orange cloud)

### 6. Deploy Nodes

```bash
# Deploy all nodes
just deploy-nodes

# Or deploy with verbose output
just deploy-nodes-verbose

# Or deploy single node
just deploy-node-single node-2
```

### 7. Verify Deployment

```bash
# Check all nodes connectivity
just ping-nodes

# View logs from all nodes
just logs-nodes remnanode

# Check specific node
just ssh-nodes "docker ps" --limit node-2
```

Check panel - all nodes should show as **Online**.

### 8. Configure Inbounds for Each Node

In the panel at https://panel.amenocturne.space, create inbounds for each node:

**For Node 2 (Germany):**

**VLESS + WebSocket Inbound:**
1. **Inbounds** → **Create Inbound**
2. Fill in:
   - Tag: `vless-ws-germany`
   - Protocol: VLESS
   - Port: 443
   - Network: WebSocket
   - Path: `/api/v2/ws`
   - Host: `static-de.amenocturne.space` (or same as node-1)
   - TLS: Enabled
   - **Node**: Select "Germany" ← CRITICAL!
3. Save

**Reality Inbound:**
1. **Inbounds** → **Create Inbound**
2. Fill in:
   - Tag: `vless-reality-germany`
   - Protocol: VLESS
   - Port: 8443
   - Network: TCP
   - Security: Reality
   - Flow: `xtls-rprx-vision`
   - Destination: `www.speedtest.net:443`
   - Server Names: `www.speedtest.net, speedtest.net`
   - Private Key: (same as node-1 from `.secrets.yml`)
   - Short IDs: `["", "your_short_id"]` (same as node-1)
   - **Node**: Select "Germany" ← CRITICAL!
3. Save

Repeat for all nodes.

### 9. Assign Users to Nodes

**Option A: Add to existing user** (for failover/load balancing)
1. **Users** → Click user → Edit
2. Check new inbounds:
   - ☑ vless-ws-germany
   - ☑ vless-reality-germany
3. Save

**Option B: Create node-specific user**
1. **Users** → **Create User**
2. Assign only Germany inbounds
3. User only connects through Germany node

## Managing Multiple Nodes

```bash
# View all nodes status
just ping-nodes
just logs-nodes remnanode
just ssh-nodes "docker ps"

# Restart specific node
just ssh-nodes "docker restart remnanode" --limit node-2

# Restart all nodes
just restart-nodes

# View logs from specific node
just logs-node-single node-2 remnanode
```

## Configuration Structure

```
ansible/inventories/
├── nodes.yml                    # All node IPs and configuration
├── remnawave-test/
│   └── .secrets.yml            # ALL secrets (panel + all nodes)
└── nodes/
    └── certs/
        ├── fullchain.pem       # Shared for all nodes
        └── key.pem             # Shared for all nodes
```

## Adding More Nodes Later

1. Edit `nodes.yml` - add new node IP
2. Register in panel → Get SECRET_KEY
3. Add SECRET_KEY to `remnawave-test/.secrets.yml` (keep same Reality keys!)
4. Add DNS record (if using different subdomain)
5. Deploy: `just deploy-nodes` (only updates new node)
6. Configure inbounds in panel
7. Assign users

## Troubleshooting

### Node Shows Offline

```bash
# Check connectivity
just ping-nodes --limit node-2

# Check container running
just ssh-nodes "docker ps | grep remnanode" --limit node-2

# Check logs
just logs-node-single node-2 remnanode
```

**Common issues:**
- Wrong SECRET_KEY in `.secrets.yml`
- Firewall blocking port 2222
- Node container not running

### Different Reality Keys Error

All nodes MUST use identical Reality keys. Check:

```bash
cat ansible/inventories/remnawave-test/.secrets.yml | grep reality
```

If different, update with correct keys and redeploy.

### Connection Works on Node-1 but Not Node-2

**Check DNS:**
```bash
dig static-de.amenocturne.space  # Should show Cloudflare IP
```

**Check inbound:**
- Host matches subdomain
- Correct node selected in inbound settings

**Check ports:**
```bash
just ssh-nodes "ss -tlnp | grep -E '443|8443'" --limit node-2
```

## Quick Command Reference

```bash
# Deploy
just deploy-nodes                      # All nodes
just deploy-node-single node-2         # Single node
just check-nodes                       # Check syntax
just dry-run-nodes                     # Preview changes

# Monitor
just ping-nodes                        # Test connectivity
just logs-nodes remnanode              # All node logs
just logs-node-single node-2 remnanode # Single node logs

# Manage
just restart-nodes                     # Restart all
just ssh-nodes "docker ps"             # Run command on all
```

## Summary

Per node setup (~10 minutes):
1. ✅ Add to `nodes.yml`
2. ✅ Register in panel → Get SECRET_KEY
3. ✅ Add SECRET_KEY to `.secrets.yml` (same Reality keys!)
4. ✅ Add DNS (if different subdomain)
5. ✅ Deploy: `just deploy-nodes`
6. ✅ Verify online in panel
7. ✅ Configure inbounds (select correct node!)
8. ✅ Assign users

Each node provides:
- Geographic diversity
- Load distribution
- Redundancy/failover
- Better regional latency
