# VPS Config

Personal VPS and VPN infrastructure management. Uses Ansible for server provisioning and a Python CLI for day-to-day operations.

## What It Manages

- **Main server** (168.100.11.130) -- Caddy reverse proxy, Authelia 2FA, monitoring (Prometheus/Grafana/Loki), personal sites, xray tunnel
- **Remnawave panel** (64.111.92.2) -- VPN management panel + subscription page
- **VPN nodes** -- VLESS+WebSocket (via Cloudflare CDN) and VLESS+Reality (direct) on multiple servers

## Prerequisites

- [just](https://github.com/casey/just) -- `brew install just`
- [uv](https://docs.astral.sh/uv/) -- `brew install uv`
- SSH access to target servers

## Setup

```bash
# Install the CLI globally
just install

# First-time setup (creates inventory + secrets)
vps setup

# Fill in secrets interactively
vps secrets init

# Verify everything
vps doctor
```

## Usage

```bash
# Status dashboard
vps

# Deploy
vps deploy              # interactive target picker
vps deploy vps          # main server
vps deploy remnawave    # panel server
vps deploy nodes        # all VPN nodes
vps deploy node-2       # single node
vps deploy caddy        # single role on main server
vps deploy --dry-run    # check mode

# Server operations
vps server logs grafana
vps server restart prometheus
vps server ssh "uptime"
vps server ssh --on remnawave "docker ps"

# LAN access (macOS)
vps local setup              # configure split DNS + trust CA
vps local status             # check configuration
vps local remove             # remove configuration

# Diagnostics
vps doctor
vps doctor --secrets
vps doctor --connectivity
```

## Remnawave VPN Management

The `vps remnawave` subcommands manage the VPN panel declaratively.

```bash
# Export current panel state to state.yml
vps remnawave export

# Compare state.yml with live panel
vps remnawave sync --plan

# Apply state.yml changes to panel
vps remnawave sync --apply

# Save Clash proxy configs for offline use
vps remnawave snapshot
vps remnawave snapshot --user alice

# Add a new VPN node (guided workflow)
vps remnawave add-node --ip 1.2.3.4 --name "Germany" --country DE --domain de1.rutube.dad
```

### Adding a New Node

1. Run `vps remnawave add-node` with the node's IP, name, country, and domain
   - Registers the node in the panel
   - Creates subscription hosts (WS + Reality)
   - Adds the node to `ansible/inventories/nodes.yml`
   - Saves the connection key to `secrets.yml`
2. Deploy with `vps deploy node-N`
3. For shared servers where default ports are taken, use `--vless-port` and `--reality-port`

## Home Server LAN Access

By default, all home server services (WebDAV, Jellyfin, Navidrome, etc.) are accessed through the VPS tunnel — traffic goes Mac → VPS → XRay tunnel → home server, even when you're sitting on the same network. This is slow for large file transfers.

The **LAN access** feature enables split DNS so the same URLs (`files.home.amenocturne.space`, etc.) resolve to the home server's local IP when you're at home, giving you direct gigabit LAN speed. When you leave home, DNS automatically falls back to the VPS tunnel.

### How it works

```
At home:
  DNS query → home server dnsmasq → 192.168.0.104 (local)
  HTTPS → home Caddy (port 443, internal CA) → service
  Speed: LAN

Away:
  DNS query → home server → timeout (2s) → fallback to 1.1.1.1
  DNS resolves to VPS → HTTPS → XRay tunnel → home server → service
  Speed: internet
```

### Server setup

The `lan-access` Ansible role installs:
- **avahi-daemon** — advertises `home-server.local` via mDNS
- **dnsmasq** — resolves `*.home.amenocturne.space` to the local IP for LAN clients
- **UFW rules** — opens DNS (53) and service ports from the LAN subnet

The `xray-bridge` Caddyfile serves HTTPS on port 443 with Caddy's internal CA (`tls internal`) for all home domains.

Deploy with:

```bash
vps deploy home lan tunnel
```

### Client setup (required)

Each macOS client needs a one-time local configuration:

```bash
vps local setup
```

This does two things:

1. **Creates `/etc/resolver/home.amenocturne.space`** — tells macOS to query the home server for DNS first (with 2s timeout), falling back to `1.1.1.1` when not on the home network
2. **Trusts Caddy's internal CA** — adds the home server's Caddy root certificate to the macOS Keychain so HTTPS works without warnings

Both steps require `sudo` (you'll be prompted).

### Managing local access

```bash
vps local status    # check if resolver + CA are configured, test DNS resolution
vps local remove    # remove the resolver file
```

### Troubleshooting

- **DNS not resolving locally**: flush cache with `sudo dscacheutil -flushcache` and try again
- **Certificate warnings**: re-run `vps local setup` — the CA may have been regenerated after a redeploy
- **Slow first connection when away**: expected — 2s DNS timeout while macOS tries the home server before falling back. Subsequent connections use cached DNS

## Project Structure

```
scripts/cli.py                      CLI entry point
scripts/secrets.py                  Secrets schema and management
remnawave-config/                   Panel config module
  export.py                         Export panel state to state.yml
  sync.py                           Declarative sync (plan/apply)
  snapshot.py                       Download Clash configs
  add_node.py                       Guided node provisioning
  client.py                         API client (httpx)
  models.py                         Pydantic state models
ansible/
  playbooks/site.yml                Main server
  playbooks/remnawave.yml           Panel server
  playbooks/node.yml                VPN nodes
  inventories/nodes.yml             Node inventory
  inventories/production.yml        Main server inventory
  roles/                            Ansible roles
secrets.yml                         All secrets (gitignored)
justfile                            Task runner aliases
```

## Secrets

All secrets live in `secrets.yml` (gitignored). Manage with:

```bash
vps secrets init    # interactive setup
vps secrets check   # verify all keys present
```

Key sections: Remnawave Panel (API token, JWT secrets, DB password), VPN Nodes (per-node connection keys, Reality keys), Cloudflare (API token), Xray Tunnel, Radicale, TURN/STUN, Authelia (JWT, session, OIDC secrets).
