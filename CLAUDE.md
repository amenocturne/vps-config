# CLAUDE.md

## Project Overview

Personal VPS + VPN infrastructure management. Ansible deploys servers, Python CLI (`vps`) manages day-to-day operations, and the `remnawave-config` module handles declarative VPN panel configuration.

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
- `remnawave` -- remnawave.yml: common, security, docker, remnawave, remnawave-subscription-page
- `nodes` -- node.yml: common, security, docker, remnawave-node
- Role-only targets: `caddy`, `authelia`, `grafana` (deploy single role on vps)
- Single node: `vps deploy node-2` (limits to one node)

## CLI Commands

Entry point: `vps` (installed via `uv tool install -e .` or run with `just vps <args>`)

```bash
vps                              # status dashboard (secrets + connectivity)
vps setup                        # first-time setup (inventory + secrets)
vps deploy [TARGET]              # deploy (interactive picker if no target)
vps deploy --dry-run             # check mode
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
```

## Remnawave Config Module (`remnawave-config/`)

Python package for managing the Remnawave VPN panel declaratively via its API.

- **client.py** -- httpx-based API client, reads credentials from `secrets.yml`
- **models.py** -- Pydantic models for panel state (config profiles, nodes, hosts, users)
- **export.py** -- fetches panel state, writes `state.yml` (git-diffable snapshot)
- **sync.py** -- computes diff between `state.yml` and live panel, applies changes
- **snapshot.py** -- downloads Clash subscription configs for users tagged "MY"
- **add_node.py** -- guided workflow: creates config profile, registers node, creates hosts, updates inventory + secrets

### Adding a New Node

1. `vps remnawave add-node --ip IP --name "Name" --country CC --domain xx.rutube.dad`
   - Registers node in panel, creates subscription hosts, adds to `ansible/inventories/nodes.yml`, saves connection key to `secrets.yml`
2. `vps deploy node-N` to provision the server
3. For shared servers (ports already taken): use `--vless-port` and `--reality-port` flags, then `--tags node` when deploying to skip security role

## Key Files

```
scripts/cli.py                   # CLI entry point
scripts/secrets.py               # secrets schema + management
remnawave-config/                # panel config module (export, sync, snapshot, add-node)
remnawave-config/state.yml       # exported panel state (gitignored)
ansible/playbooks/site.yml       # main server playbook
ansible/playbooks/remnawave.yml  # panel server playbook
ansible/playbooks/node.yml       # VPN node playbook
ansible/inventories/nodes.yml    # node inventory (IPs, domains, port overrides)
ansible/inventories/production.yml  # main server inventory
ansible/roles/                   # all Ansible roles
secrets.yml                      # all secrets (gitignored)
justfile                         # just install / just vps <args>
```

## Secrets

All in `secrets.yml` (gitignored). Schema defined in `scripts/secrets.py`. Sections:

- **Remnawave Panel**: `remnawave_panel_url`, `remnawave_api_token`, `jwt_auth_secret`, `jwt_api_tokens_secret`, `metrics_pass`, `webhook_secret`, `postgres_password`
- **VPN Nodes**: `node_secret_keys` (dict: node-1, node-2, ...), `reality_private_key`, `reality_public_key`, `reality_short_id`
- **Cloudflare**: `cloudflare_api_token`
- **Xray Tunnel**: `xray_tunnel_uuid`, `xray_tunnel_private_key`, `xray_tunnel_public_key`, `xray_tunnel_short_id`
- **Radicale**: `radicale_user`, `radicale_password_hash`
- **TURN/STUN**: `coturn_user`, `coturn_password`
- **Authelia**: `authelia_jwt_secret`, `authelia_session_secret`, `authelia_storage_encryption_key`, `authelia_admin_user`, `authelia_admin_displayname`, `authelia_admin_email`, `authelia_admin_password_hash`, `authelia_oidc_hmac_secret`, `authelia_oidc_jwks_rsa_private_key`

## Tech Stack

- Python 3.11+, uv, hatchling
- Ansible for server provisioning
- httpx + Pydantic for panel API interaction
- just as task runner
