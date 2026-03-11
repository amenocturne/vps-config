# Remnawave Telegram Bot

Minimal Telegram bot that delivers VPN subscription configs to authorized users, bypassing SNI-blocked web endpoints.

## Problem

`sub.amenocturne.space` is blocked by Roskomnadzor (SNI filtering). Users in Russia can't fetch their VPN configs without already having a VPN — chicken-and-egg problem. Telegram is accessible in Russia and provides an alternative delivery channel.

## Features

- Authenticate users by matching their Telegram ID against Remnawave's user database
- Send subscription config (vless:// links) as clipboard-ready message
- Client type selection via inline buttons (V2Ray, Clash, Sing-Box, Mihomo, Stash, JSON)
- Admin commands for debugging (list users, check specific user, ping)
- Silently ignore unauthorized Telegram IDs

## User Flow

### Regular user
1. User opens bot, sends `/start` (or any message)
2. Bot looks up their Telegram ID via Remnawave API
3. If not found → silent ignore (no response, don't leak that the bot exists)
4. If found → welcome message + persistent main menu keyboard:
   - `🔑 Получить конфиг`
5. **Получить конфиг** → inline keyboard with client type buttons:
   - Row 1: `V2Ray/Streisand` | `Clash`
   - Row 2: `Sing-Box` | `Mihomo`
   - Row 3: `Stash` | `JSON`
   (client names stay English — they're app names)
6. User taps a client button → bot fetches config, sends as clipboard-ready monospace message (wrapped in ``` for easy copy)
7. If config is too long for a single message (>4096 chars), send as a `.txt` file instead

### Admin
Main menu has an extra row when `ADMIN_TELEGRAM_ID` matches:
   - `🔑 Получить конфиг`
   - `👥 Пользователи` | `🏓 Пинг`
- **Пользователи** → list all users with status summary (inline buttons to drill into each)
- **Пинг** → bot health check + API connectivity status
- Tapping a user in the list → detailed info for that user

### Interaction model
- **Reply keyboard** (persistent bottom buttons) for main actions — always visible
- **Inline keyboard** (in-message buttons) for selections (client type, user list)
- No slash commands except `/start` (Telegram requires it for bot activation)
- Any unrecognized text from an authorized user → show main menu again

## Tech Stack

- Python 3.12+
- `python-telegram-bot` (async, v21+) — lightweight, well-maintained
- `httpx` — async HTTP client for Remnawave API (already used in vps-config)
- Docker — single container deployment

## Architecture

### Components

```
Telegram API ←→ Bot (Python) ←→ Remnawave API (panel)
```

Three modules:
- **bot.py** — Telegram handlers, command routing, message formatting
- **remnawave.py** — Remnawave API client (thin httpx wrapper)
- **config.py** — Environment variable loading, validation

### Data Flow

```
User message → Telegram API → Bot
                                ├─ config.py (ADMIN_TELEGRAM_ID check)
                                ├─ remnawave.py (GET /api/users/by-telegram-id/{id})
                                │   ├─ Not found → ignore
                                │   └─ Found → get short_uuid
                                │       └─ GET /api/sub/{short_uuid} → config payload
                                └─ Format + send response via Telegram API
```

### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/users/by-telegram-id/{id}` | Auth: match Telegram ID to Remnawave user |
| `GET /api/sub/{short_uuid}` | Fetch default subscription config (base64 vless:// links) |
| `GET /api/sub/{short_uuid}/{client_type}` | Fetch config for specific client (v2ray-json, clash, singbox, mihomo, stash, json) |
| `GET /api/sub/{short_uuid}/info` | Subscription metadata (traffic, expiry, links) |
| `GET /api/users` | Admin: list all users |
| `GET /api/users/by-username/{username}` | Admin: lookup specific user |

### Security

- **No response to unknown Telegram IDs** — bot appears non-functional to strangers
- **Admin commands gated by `ADMIN_TELEGRAM_ID`** env var
- **API token never exposed** — bot talks to panel API server-side only
- **No state stored** — bot is stateless, all data from Remnawave API on each request

### Constraints

- Bot must run on the remnawave server (same Docker network as panel) to avoid exposing the API externally
- No database — Remnawave is the single source of truth
- No user registration flow — users must already have `telegram_id` set in Remnawave panel

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | yes | Telegram bot token from BotFather |
| `REMNAWAVE_API_URL` | yes | Panel API URL (e.g., `http://remnawave:3000/api`) |
| `REMNAWAVE_API_TOKEN` | yes | Panel API bearer token |
| `ADMIN_TELEGRAM_ID` | yes | Your Telegram user ID for admin commands |

## Deployment

- New Ansible role: `remnawave-telegram-bot`
- Docker container on `remnawave-network` (same as panel + subscription page)
- Secrets (`BOT_TOKEN`) added to `secrets.yml`
- Deployed via `vps deploy remnawave` (added to `remnawave.yml` playbook)
