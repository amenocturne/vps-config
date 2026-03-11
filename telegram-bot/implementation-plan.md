# Implementation Plan

## MVP Scope

**In**: Auth by Telegram ID, config delivery with client type selection (inline buttons), subscription status, admin commands, Docker + Ansible deployment

**Out**: Inline mode, subscription purchase/renewal, auto-notifications (expiry warnings), localization

## File Structure

```
telegram-bot/
├── bot.py              # Entry point, handlers, message formatting
├── remnawave.py        # Remnawave API client
├── config.py           # Env loading + validation
├── Dockerfile
└── requirements.txt
ansible/roles/remnawave-telegram-bot/
├── defaults/main.yml
├── tasks/main.yml
└── templates/
    └── docker-compose-telegram-bot.yml.j2
```

## Task Breakdown

### Phase 1: Bot core

1. `config.py` — load and validate env vars (BOT_TOKEN, REMNAWAVE_API_URL, REMNAWAVE_API_TOKEN, ADMIN_TELEGRAM_ID)
2. `remnawave.py` — async httpx client with methods:
   - `get_users_by_telegram_id(tg_id) -> list[User] | None`
   - `get_subscription(short_uuid, client_type=None) -> str`
   - `get_all_users() -> list[User]` (admin)
   - `get_user_by_username(username) -> User` (admin)
3. `bot.py` — telegram handlers:
   - Auth middleware: check telegram_id against API on every message/callback, ignore unknowns
   - `/start` + any text → show welcome + persistent reply keyboard (main menu)
   - Reply keyboard buttons: `🔑 Получить конфиг` (+ `👥 Пользователи`, `🏓 Пинг` for admin)
   - "Получить конфиг" → send inline keyboard with client type buttons
   - Client type callback → fetch config, send as monospace message (or file if >4096 chars)
   - "Пользователи" (admin) → list users with inline buttons to drill into each
   - "Пинг" (admin) → health check
   - User detail callback (admin) → show user info

### Phase 2: Docker + Ansible

1. `Dockerfile` — Python slim, install deps, run bot.py
2. `requirements.txt` — python-telegram-bot, httpx
3. Ansible role:
   - `defaults/main.yml` — port (not needed, bot uses polling), container name
   - `templates/docker-compose-telegram-bot.yml.j2` — container on remnawave-network
   - `tasks/main.yml` — deploy compose file, start container
4. Add role to `ansible/playbooks/remnawave.yml`
5. Add `telegram_bot_token` to secrets.yml schema
6. Add `ADMIN_TELEGRAM_ID` to inventory vars

## Testing Strategy

Manual testing only — this is a ~150-line bot for family use. Test:
- Unauthorized user sends message → no response
- Authorized user `/config` → buttons appear → tap → config received
- Config >4096 chars → sent as file
- Admin `/users` → user list
- `/status` → traffic + expiry info
- Bot restart → works immediately (stateless)

## Definition of Done

- Bot responds to authorized users with VPN configs
- Client type selection via inline keyboard
- Admin commands work
- Deployed on remnawave server via `vps deploy remnawave`
- Bot token in secrets.yml
