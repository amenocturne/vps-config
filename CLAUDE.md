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
- `remnawave` -- remnawave.yml: common, security, docker, remnawave, remnawave-subscription-page
- `nodes` -- node.yml: common, security, docker, remnawave-node
- Role-only targets: `caddy`, `authelia`, `grafana` (deploy single role on vps)
- Single node: `vps deploy node-2` (limits to one node)

## Python Package Structure

Single `vps_cli` package under `src/` layout:

```
src/vps_cli/
  __init__.py              # find_project_root(), CONFIG_PATH
  __main__.py              # python -m vps_cli
  errors.py                # VpsError, SecretsError, ConfigError, AnsibleError, ApiError
  util.py                  # ANSI colors, confirm(), prompt()
  ansible.py               # TARGETS, ROLE_TARGETS, run_ansible(), ping_target()
  secrets.py               # SCHEMA, init/check/distribute/setup_secrets()
  certs.py                 # renew_certs() — Cloudflare Origin CA
  validate.py              # run_validation() — pre-deploy checks
  health_check.py          # run_health_checks() — infrastructure health
  test_local.py            # Docker test environment
  cli/
    __init__.py            # _build_parser(), main(), dispatch
    status.py              # cmd_status() — dashboard
    setup.py               # cmd_setup() — first-time setup
    deploy.py              # cmd_deploy() — Ansible deploy
    doctor.py              # cmd_doctor() — all checks
    server.py              # cmd_server_logs/restart/ssh/test()
    secrets.py             # cmd_secrets() — check/init
    certs.py               # cmd_certs_renew()
    remnawave.py           # cmd_remnawave_export/sync/snapshot/add_node/gen_keys()
  remnawave/
    __init__.py
    client.py              # httpx async client, API wrappers
    models.py              # Pydantic models (PanelState, etc.)
    export.py              # export_state() — panel -> state.yml
    snapshot.py            # Clash config download
    add_node.py            # guided node provisioning workflow
    gen_keys.py            # Reality x25519 keypair generation
    sync/
      __init__.py          # run_sync(mode, state_path, delete_missing)
      diff.py              # compute_sync_plan() — pure diff
      render.py            # render_plan() — terminal output
      apply.py             # apply_plan() — mutations
```

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
vps remnawave gen-keys           # generate Reality keypair (--prefix, --node)
```

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
- **Radicale**: `radicale_user`, `radicale_password_hash`
- **TURN/STUN**: `coturn_user`, `coturn_password`
- **Authelia**: `authelia_jwt_secret`, `authelia_session_secret`, `authelia_storage_encryption_key`, `authelia_admin_user`, `authelia_admin_displayname`, `authelia_admin_email`, `authelia_admin_password_hash`, `authelia_oidc_hmac_secret`, `authelia_oidc_jwks_rsa_private_key`

## Tech Stack

- Python 3.11+, uv, hatchling
- Ansible for server provisioning
- httpx + Pydantic for panel API interaction
- just as task runner
