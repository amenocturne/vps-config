# CLAUDE.md

## Project Overview

Personal VPS + VPN infrastructure management. Ansible deploys servers, Python CLI (`vps`) manages day-to-day operations, and the `remnawave` subpackage handles declarative VPN panel configuration.

## Architecture

### Servers

| Name | IP | Inventory | Purpose |
|------|----|-----------|---------|
| vps (main) | 168.100.11.130 | production.yml | Caddy, Authelia, monitoring, personal sites, xray tunnel |
| remnawave (panel) | 64.111.92.2 | remnawave-test.yml | Remnawave panel + subscription page + PostgreSQL |
| node-1 | 64.111.92.2 | nodes.yml | VPN node (Netherlands), default ports |
| node-2 | 193.149.129.84 | nodes.yml | VPN node (Netherlands 2), custom ports (2083/9443) |

Domain: `amenocturne.space` (panel at `panel.amenocturne.space`, nodes at `*.rutube.dad`)

### Deploy Targets

- `vps` -- site.yml: common, security, docker, authelia, projects, personal-website, wishlist, coturn, briefing, xray-portal, caddy, monitoring
- `home` -- home_server.yml: common, security, lan-access, xray-bridge, radicale, dwayne, jellyfin, navidrome, webdav, send, minecraft
- `remnawave` -- remnawave.yml: common, security, docker, remnawave, remnawave-subscription-page, remnawave-telegram-bot
- `nodes` -- node.yml: common, security, docker, remnawave-node
- Deploy single component: `vps deploy vps caddy`, `vps deploy home jellyfin`
- Single node: `vps deploy node-2` (limits to one node)

## CLI Commands

Entry point: `vps` (installed via `uv tool install -e .` or run with `just vps <args>`)

```bash
vps                              # show help (available commands)
vps status                       # status dashboard (secrets + connectivity)
vps setup                        # first-time setup (inventory + secrets)

# Deploy — explicit target + component required
vps deploy                       # show available targets
vps deploy remnawave             # show components (panel, subscription, telegram-bot)
vps deploy remnawave all         # deploy everything on remnawave
vps deploy remnawave telegram-bot # deploy just the telegram bot
vps deploy vps caddy             # deploy just caddy on main server
vps deploy vps all               # deploy everything on main server
vps deploy home all              # deploy everything on home server
vps deploy home jellyfin         # deploy just jellyfin on home server
vps deploy nodes                 # deploy all VPN nodes
vps deploy node-2                # deploy specific node
vps deploy <target> <comp> --dry-run  # check mode

vps local setup                  # install LAN toggle daemon + trust CA (macOS)
vps local status                 # check daemon, hosts entries, reachability
vps local remove                 # uninstall daemon and clean up

vps doctor                       # all checks (--secrets, --syntax, --connectivity, --services)
vps server logs <service>        # docker logs (--on remnawave for other targets)
vps server restart <service>     # docker restart
vps server ssh ["command"]       # run shell command (--on to pick target)
vps server test [--clean]        # local Docker testing
vps secrets check                # verify secrets.yml
vps secrets init                 # interactive setup

# Remnawave panel config
vps remnawave export             # export panel state to state.yml
vps remnawave sync --plan        # show diff between state.yml and panel
vps remnawave sync --apply       # apply state.yml to panel
vps remnawave snapshot [--user]  # save Clash configs locally for offline use
vps remnawave add-node           # guided node provisioning (--ip, --name, --country, --domain)
vps remnawave gen-keys           # generate Reality keypair (--prefix, --node)
vps remnawave template push      # upload Mihomo template to panel (--file, --name)
```

### Deploy Targets & Components

| Target | Components | Notes |
|--------|-----------|-------|
| `vps` | caddy, authelia, monitoring, personal-website, wishlist, coturn, briefing, tunnel, projects | Main server roles |
| `home` | lan, tunnel, radicale, dwayne, jellyfin, navidrome, webdav, send, minecraft | Home server (MacBook) roles |
| `remnawave` | panel, subscription, telegram-bot | Panel server roles |
| `nodes` | — | Use `node-N` to limit to one node |

### Adding a New Node

1. `vps remnawave add-node --ip IP --name "Name" --country CC --domain xx.rutube.dad`
   - Registers node in panel, creates subscription hosts, adds to `ansible/inventories/nodes.yml`, saves connection key to `secrets.yml`
2. `vps deploy node-N` to provision the server
3. For shared servers (ports already taken): use `--vless-port` and `--reality-port` flags, then `--tags node` when deploying to skip security role

## Key Files

```
src/vps_cli/                     # all Python code
remnawave-config/state.yml       # exported panel state (gitignored)
remnawave-config/snapshots/      # Clash config snapshots (gitignored)
remnawave-config/templates/      # Mihomo subscription templates (version-controlled)
ansible/playbooks/site.yml       # main server playbook
ansible/playbooks/remnawave.yml  # panel server playbook
ansible/playbooks/node.yml       # VPN node playbook
ansible/inventories/nodes.yml    # node inventory (IPs, domains, port overrides)
ansible/inventories/production.yml  # main server inventory
ansible/roles/                   # all Ansible roles
secrets.yml                      # all secrets (gitignored)
justfile                         # just install / just vps <args>
scripts/                         # shell scripts (certs, diagnostics, maintenance)
```

## Secrets

All in `secrets.yml` (gitignored). Schema defined in `src/vps_cli/secrets.py`. Sections:

- **Remnawave Panel**: `remnawave_panel_url`, `remnawave_api_token`, `jwt_auth_secret`, `jwt_api_tokens_secret`, `metrics_pass`, `webhook_secret`, `postgres_password`
- **VPN Nodes**: `node_secret_keys` (dict: node-1, node-2, ...), `reality_private_key`, `reality_public_key`, `reality_short_id`
- **Cloudflare**: `cloudflare_api_token`
- **Xray Tunnel**: `xray_tunnel_uuid`, `xray_tunnel_private_key`, `xray_tunnel_public_key`, `xray_tunnel_short_id`
- **Seafile**: `seafile_db_password`, `seafile_admin_email`, `seafile_admin_password`
- **Radicale**: `radicale_user`, `radicale_password_hash`
- **TURN/STUN**: `coturn_user`, `coturn_password`
- **Authelia**: `authelia_jwt_secret`, `authelia_session_secret`, `authelia_storage_encryption_key`, `authelia_admin_user`, `authelia_admin_displayname`, `authelia_admin_email`, `authelia_admin_password_hash`, `authelia_oidc_hmac_secret`, `authelia_oidc_jwks_rsa_private_key`

## Tech Stack

- Python 3.11+, uv, hatchling
- Ansible for server provisioning
- httpx + Pydantic for panel API interaction
- just as task runner
