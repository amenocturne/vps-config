# Remnawave Configuration

This directory contains **ALL** Remnawave configuration including panel and nodes.

## Files

```
remnawave-test/
├── .secrets.yml         # ALL secrets (panel + all nodes)
└── certs/               # Certificates for panel server
    ├── fullchain.pem
    └── key.pem
```

## Single Secrets File

The `.secrets.yml` file contains secrets for:
- ✅ Panel/backend (JWT, database, metrics)
- ✅ All VPN nodes (SECRET_KEY per node)
- ✅ Reality configuration (shared across all)

## Structure

```yaml
# Panel secrets
jwt_auth_secret: "..."
postgres_password: "..."

# Node secrets (one per node)
node_secret_keys:
  node-1: "sk_xxx..."
  node-2: "sk_yyy..."

# Reality keys (shared)
reality_private_key: "..."
reality_public_key: "..."
reality_short_id: "..."
```

## Adding New Node

1. Register node in panel → get SECRET_KEY
2. Add to `.secrets.yml`:
   ```yaml
   node_secret_keys:
     node-3: "sk_zzz_FROM_PANEL"
   ```
3. Deploy: `just deploy-nodes`

That's it!
