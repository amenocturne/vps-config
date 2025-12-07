# VPN Nodes Configuration

This directory contains certificates for all VPN nodes.

## Directory Structure

```
nodes/
├── .secrets.yml          # All node SECRET_KEYs (gitignored)
└── certs/
    ├── node-1/
    │   ├── fullchain.pem # SSL certificate
    │   └── key.pem       # Private key
    └── node-2/
        ├── fullchain.pem
        └── key.pem
```

## Setup

1. Create certificate directory for each node:
   ```bash
   mkdir -p certs/node-1
   mkdir -p certs/node-2
   ```

2. Add Cloudflare Origin CA certificates:
   - Go to Cloudflare → SSL/TLS → Origin Server
   - Create Certificate for `*.amenocturne.space`
   - Save certificate as `fullchain.pem`
   - Save private key as `key.pem`
   - Copy to each node's directory

3. Configure secrets:
   ```bash
   cp .secrets.yml.example .secrets.yml
   # Edit .secrets.yml with SECRET_KEYs from panel
   ```

## Deployment

Deploy all nodes:
```bash
just deploy-nodes
```

Deploy specific node:
```bash
just deploy-node-single node-2
```

## Security

- `.secrets.yml` is gitignored - never commit
- `key.pem` files are private - keep secure
- `fullchain.pem` files are public certificates
