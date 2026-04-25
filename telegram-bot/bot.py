import io
import logging
from datetime import time as dt_time, timezone, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import httpx

from config import BOT_TOKEN, ADMIN_TELEGRAM_ID, CLIENT_TYPES, SUBSCRIPTION_BASE_URL
import remnawave
import monitoring
import minecraft

logger = logging.getLogger(__name__)

def _reply_keyboard(tg_id: int) -> ReplyKeyboardMarkup:
    rows = [["🔑 Получить конфиг"]]
    if tg_id == ADMIN_TELEGRAM_ID:
        rows.append(["👥 Пользователи", "🏓 Пинг"])
        rows.append(["📊 Статус серверов", "🔔 Проверить алерты"])
        rows.append(["⛏ Minecraft"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def _is_admin(tg_id: int) -> bool:
    return tg_id == ADMIN_TELEGRAM_ID


async def _authorize(tg_id: int) -> list[dict] | None:
    return await remnawave.get_users_by_telegram_id(tg_id)


async def _is_authorized(tg_id: int) -> bool:
    return _is_admin(tg_id) or bool(await _authorize(tg_id))


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not await _is_authorized(tg_id):
        await update.message.reply_text(
            f"Твой Telegram ID: <code>{tg_id}</code>\n\n"
            "Отправь его администратору для получения доступа.",
            parse_mode="HTML",
        )
        return
    await update.message.reply_text(
        "Привет! Нажми кнопку ниже для получения конфига.",
        reply_markup=_reply_keyboard(tg_id),
    )


def _client_type_keyboard(short_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"config:{short_uuid}:{cb}") for label, cb in row]
        for row in CLIENT_TYPES
    ])


async def _get_config_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not await _is_authorized(tg_id):
        return

    users = await _authorize(tg_id)
    if not users:
        if _is_admin(tg_id):
            await update.message.reply_text("Нет привязанного пользователя в панели.")
        return

    if len(users) == 1:
        sub_link = f"{SUBSCRIPTION_BASE_URL}/{users[0]['shortUuid']}"
        await update.message.reply_text(
            f"🔗 <a href=\"{sub_link}\">Ссылка подписки</a>\n\n"
            "Или выбери формат конфига:",
            parse_mode="HTML",
            reply_markup=_client_type_keyboard(users[0]["shortUuid"]),
        )
    else:
        keyboard = [
            [InlineKeyboardButton(
                u.get("username", u["shortUuid"]),
                callback_data=f"pick_user:{u['shortUuid']}",
            )]
            for u in users
        ]
        await update.message.reply_text(
            "Выбери пользователя:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def _pick_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    if not await _is_authorized(tg_id):
        await query.answer()
        return

    short_uuid = query.data.removeprefix("pick_user:")
    sub_link = f"{SUBSCRIPTION_BASE_URL}/{short_uuid}"
    await query.answer()
    await query.message.reply_text(
        f"🔗 Ссылка подписки:\n<code>{sub_link}</code>\n\n"
        "Или выбери формат конфига:",
        parse_mode="HTML",
        reply_markup=_client_type_keyboard(short_uuid),
    )


async def _config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    if not await _is_authorized(tg_id):
        await query.answer()
        return

    # callback data: config:{short_uuid}:{client_type}
    parts = query.data.removeprefix("config:").split(":", 1)
    short_uuid, client_type = parts[0], parts[1]

    try:
        config = await remnawave.get_subscription(short_uuid, client_type)
    except Exception:
        await query.answer("Ошибка при получении конфига", show_alert=True)
        return

    await query.answer()

    wrapped = f"<pre>{config}</pre>"
    if len(wrapped) <= 4096:
        await query.message.reply_text(wrapped, parse_mode="HTML")
    else:
        buf = io.BytesIO(config.encode())
        buf.name = f"{client_type}.txt"
        await query.message.reply_document(buf, filename=f"{client_type}.txt")


async def _users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    try:
        users = await remnawave.get_all_users()
    except Exception:
        await update.message.reply_text("Ошибка при получении списка пользователей.")
        return

    if not users:
        await update.message.reply_text("Пользователей нет.")
        return

    keyboard = [
        [InlineKeyboardButton(
            f"{u.get('username', '?')} ({u.get('status', '?')})",
            callback_data=f"user:{u['username']}",
        )]
        for u in users
    ]
    await update.message.reply_text(
        f"Пользователи ({len(users)}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _user_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id != ADMIN_TELEGRAM_ID:
        await query.answer()
        return

    username = query.data.removeprefix("user:")

    try:
        user = await remnawave.get_user_by_username(username)
    except Exception:
        await query.answer("Ошибка", show_alert=True)
        return

    await query.answer()

    if not user:
        await query.message.reply_text(f"Пользователь {username} не найден.")
        return

    lines = [
        f"👤 {user.get('username', '?')}",
        f"Статус: {user.get('status', '?')}",
        f"Telegram ID: {user.get('telegramId', '—')}",
        f"Создан: {user.get('createdAt', '—')}",
    ]
    await query.message.reply_text("\n".join(lines))


async def _ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    ok = await remnawave.ping()
    status = "✅ API доступен" if ok else "❌ API недоступен"
    await update.message.reply_text(status, reply_markup=_reply_keyboard(tg_id))


async def _server_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    health = await monitoring.get_all_servers_health()
    text = monitoring.format_server_health(health)
    await update.message.reply_text(text)


async def _check_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    alerts = await monitoring.check_alerts()
    text = monitoring.format_alerts(alerts)
    await update.message.reply_text(text)


async def _daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    health = await monitoring.get_all_servers_health()
    alerts = await monitoring.check_alerts()
    text = monitoring.format_daily_digest(health, alerts)
    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=text)


async def _periodic_alert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    alerts = await monitoring.check_alerts()
    alert_set = frozenset(alerts)
    prev = context.bot_data.get("_last_alerts", frozenset())
    if alert_set == prev:
        return
    context.bot_data["_last_alerts"] = alert_set
    if alerts:
        text = monitoring.format_alerts(alerts)
        await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=text)
    elif prev:
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text="\u2705 All alerts resolved",
        )


async def _mc_rejection_alert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    rejected = await minecraft.check_rejected_logins()
    rejected_set = frozenset(rejected)
    prev = context.bot_data.get("_last_mc_rejections", frozenset())
    new_rejections = rejected_set - prev
    context.bot_data["_last_mc_rejections"] = rejected_set
    if new_rejections:
        players = ", ".join(sorted(new_rejections))
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=f"\u26a0\ufe0f Minecraft: unauthorized login attempt\n\nRejected players: {players}",
        )


def _mc_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Whitelist", callback_data="mc:whitelist"),
         InlineKeyboardButton("👥 Online", callback_data="mc:online")],
        [InlineKeyboardButton("➕ Add Player", callback_data="mc:add_prompt"),
         InlineKeyboardButton("➖ Remove Player", callback_data="mc:remove_prompt")],
        [InlineKeyboardButton("📊 Status", callback_data="mc:status"),
         InlineKeyboardButton("🌍 Worlds", callback_data="mc:worlds")],
    ])


async def _minecraft_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    online = await minecraft.is_online()
    status = "🟢 Online" if online else "🔴 Offline"
    await update.message.reply_text(
        f"⛏ Minecraft Server ({status})",
        reply_markup=_mc_menu_keyboard(),
    )


async def _mc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id != ADMIN_TELEGRAM_ID:
        await query.answer()
        return

    action = query.data.removeprefix("mc:")

    if action == "whitelist":
        await query.answer()
        try:
            players = await minecraft.whitelist_list()
            if players:
                text = "📋 Whitelisted players:\n" + "\n".join(f"  • {p}" for p in sorted(players))
            else:
                text = "📋 Whitelist is empty"
        except ConnectionError:
            text = "❌ Cannot reach Minecraft server"
        await query.message.reply_text(text, reply_markup=_mc_menu_keyboard())

    elif action == "online":
        await query.answer()
        try:
            count, players = await minecraft.list_online()
            if players:
                text = f"👥 Online ({count}):\n" + "\n".join(f"  • {p}" for p in players)
            else:
                text = "👥 No players online"
        except ConnectionError:
            text = "❌ Cannot reach Minecraft server"
        await query.message.reply_text(text, reply_markup=_mc_menu_keyboard())

    elif action == "status":
        await query.answer()
        try:
            s = await minecraft.server_status()
            tps_1m, tps_5m, tps_15m = s["tps"]
            mspt_5s, mspt_10s, mspt_60s = s["mspt"]
            players = ", ".join(s["players"]) if s["players"] else "—"

            text = (
                f"📊 <b>Server Status</b>\n\n"
                f"<pre>"
                f"Players   {s['players_online']}\n"
                f"Online    {players}\n"
                f"─────────────────────\n"
                f"TPS       1m     5m    15m\n"
                f"          {tps_1m:<6.1f} {tps_5m:<5.1f} {tps_15m:.1f}\n"
                f"─────────────────────\n"
                f"MSPT      5s     10s   60s\n"
                f"          {mspt_5s:<6.1f} {mspt_10s:<5.1f} {mspt_60s:.1f}"
                f"</pre>"
            )
        except ConnectionError:
            text = "❌ Cannot reach Minecraft server"
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=_mc_menu_keyboard())

    elif action == "add_prompt":
        await query.answer()
        context.user_data["mc_action"] = "add"
        await query.message.reply_text(
            "Enter the player name to add to whitelist:",
        )

    elif action == "remove_prompt":
        await query.answer()
        try:
            players = await minecraft.whitelist_list()
        except ConnectionError:
            await query.message.reply_text("❌ Cannot reach Minecraft server")
            return
        if not players:
            await query.message.reply_text("Whitelist is empty", reply_markup=_mc_menu_keyboard())
            return
        keyboard = [
            [InlineKeyboardButton(f"❌ {p}", callback_data=f"mc:remove:{p}")]
            for p in sorted(players)
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="mc:back")])
        await query.message.reply_text(
            "Select player to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action.startswith("remove:"):
        player = action.removeprefix("remove:")
        await query.answer()
        try:
            result = await minecraft.whitelist_remove(player)
            text = f"✅ {result}" if result else f"✅ Removed {player}"
        except ConnectionError:
            text = "❌ Cannot reach Minecraft server"
        await query.message.reply_text(text, reply_markup=_mc_menu_keyboard())

    elif action == "back":
        await query.answer()
        online = await minecraft.is_online()
        status = "🟢 Online" if online else "🔴 Offline"
        await query.message.reply_text(
            f"⛏ Minecraft Server ({status})",
            reply_markup=_mc_menu_keyboard(),
        )

    elif action == "worlds":
        await query.answer()
        try:
            data = await minecraft.get_worlds()
            seed = await minecraft.get_seed()
            active = data.get("active", "—")
            worlds = data.get("worlds", [])
            text = f"🌍 World Management\n\nActive: <b>{active or 'new world'}</b>\nSeed: <code>{seed}</code>\nArchived: {len(worlds)}"
        except Exception:
            text = "🌍 World Management\n\n❌ Cannot reach world manager"
        keyboard = [
            [InlineKeyboardButton("🆕 New World", callback_data="mc:world_new_prompt"),
             InlineKeyboardButton("🔄 Switch World", callback_data="mc:world_switch_list")],
            [InlineKeyboardButton("🗑 Delete World", callback_data="mc:world_delete_list")],
            [InlineKeyboardButton("⬅️ Back", callback_data="mc:back")],
        ]
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "world_new_prompt":
        await query.answer()
        context.user_data["mc_action"] = "new_world"
        await query.message.reply_text(
            "Enter a name to archive the current world as\n(e.g. <code>survival-1</code>, <code>parkour</code>):",
            parse_mode="HTML",
        )

    elif action == "world_switch_list":
        await query.answer()
        try:
            data = await minecraft.get_worlds()
            worlds = data.get("worlds", [])
        except Exception:
            await query.message.reply_text("❌ Cannot reach world manager")
            return
        if not worlds:
            await query.message.reply_text("No archived worlds yet.", reply_markup=_mc_menu_keyboard())
            return
        keyboard = [
            [InlineKeyboardButton(f"🔄 {w}", callback_data=f"mc:world_switch:{w}")]
            for w in worlds
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="mc:worlds")])
        await query.message.reply_text("Select world to switch to:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action.startswith("world_switch:"):
        name = action.removeprefix("world_switch:")
        await query.answer()
        try:
            data = await minecraft.get_worlds()
            active = data.get("active", "")
        except Exception:
            active = ""
        if not active:
            context.user_data["mc_action"] = "save_then_switch"
            context.user_data["mc_switch_to"] = name
            await query.message.reply_text(
                f"Current world has no name. Enter a name to save it as before switching to <b>{name}</b>:",
                parse_mode="HTML",
            )
        else:
            await query.message.reply_text(f"🔄 Switching to <b>{name}</b>...\nServer will restart.", parse_mode="HTML")
            try:
                result = await minecraft.switch_world(name)
                await query.message.reply_text(f"✅ Switched to <b>{name}</b>", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
            except Exception as e:
                await query.message.reply_text(f"❌ Failed to switch: {e}", reply_markup=_mc_menu_keyboard())

    elif action == "world_delete_list":
        await query.answer()
        try:
            data = await minecraft.get_worlds()
            worlds = data.get("worlds", [])
            active = data.get("active", "")
        except Exception:
            await query.message.reply_text("❌ Cannot reach world manager")
            return
        if not worlds:
            await query.message.reply_text("No archived worlds to delete.", reply_markup=_mc_menu_keyboard())
            return
        keyboard = [
            [InlineKeyboardButton(f"🗑 {w}", callback_data=f"mc:world_delete:{w}")]
            for w in worlds if w != active
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="mc:worlds")])
        await query.message.reply_text("Select world to delete:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action.startswith("world_delete:"):
        name = action.removeprefix("world_delete:")
        await query.answer()
        try:
            await minecraft.delete_world(name)
            await query.message.reply_text(f"✅ Deleted world <b>{name}</b>", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
        except Exception as e:
            await query.message.reply_text(f"❌ Failed to delete: {e}", reply_markup=_mc_menu_keyboard())


async def _mc_player_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input when waiting for a player name to add to whitelist."""
    tg_id = update.effective_user.id
    if not _is_admin(tg_id):
        return

    mc_action = context.user_data.pop("mc_action", None)
    if mc_action == "save_then_switch":
        switch_to = context.user_data.pop("mc_switch_to", "")
        name = update.message.text.strip()
        if not name or "/" in name or len(name) > 30:
            await update.message.reply_text("Invalid name. Use 1-30 characters, no slashes.", reply_markup=_mc_menu_keyboard())
            return
        try:
            await minecraft.new_world(name)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                await update.message.reply_text(f"❌ World <b>{name}</b> already exists. Choose a different name.", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
            else:
                await update.message.reply_text(f"❌ Failed: {e}", reply_markup=_mc_menu_keyboard())
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to save: {e}", reply_markup=_mc_menu_keyboard())
            return
        await update.message.reply_text(f"✅ Saved as <b>{name}</b>. Now switching to <b>{switch_to}</b>...", parse_mode="HTML")
        try:
            await minecraft.switch_world(switch_to)
            await update.message.reply_text(f"✅ Switched to <b>{switch_to}</b>", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to switch: {e}", reply_markup=_mc_menu_keyboard())
        return
    if mc_action == "new_world":
        name = update.message.text.strip()
        if not name or "/" in name or len(name) > 30:
            await update.message.reply_text("Invalid name. Use 1-30 characters, no slashes.", reply_markup=_mc_menu_keyboard())
            return
        await update.message.reply_text(f"🆕 Archiving current world as <b>{name}</b> and generating new world...\nServer will restart.", parse_mode="HTML")
        try:
            result = await minecraft.new_world(name)
            await update.message.reply_text(f"✅ New world created! Previous archived as <b>{name}</b>", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                await update.message.reply_text(f"❌ World <b>{name}</b> already exists. Choose a different name.", parse_mode="HTML", reply_markup=_mc_menu_keyboard())
            else:
                await update.message.reply_text(f"❌ Failed: {e}", reply_markup=_mc_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}", reply_markup=_mc_menu_keyboard())
        return
    if mc_action != "add":
        return  # Not waiting for MC input, let fallback handle it

    player = update.message.text.strip()
    if not player or " " in player or len(player) > 16:
        await update.message.reply_text(
            "Invalid player name. Must be 1-16 characters with no spaces.",
            reply_markup=_mc_menu_keyboard(),
        )
        return

    try:
        result = await minecraft.whitelist_add(player)
        text = f"✅ {result}" if result else f"✅ Added {player}"
    except ConnectionError:
        text = "❌ Cannot reach Minecraft server"
    await update.message.reply_text(text, reply_markup=_mc_menu_keyboard())


async def _fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id

    # Check if we're waiting for MC player name input
    if context.user_data.get("mc_action") and _is_admin(tg_id):
        await _mc_player_name_handler(update, context)
        return

    if not await _is_authorized(tg_id):
        await update.message.reply_text(
            f"Твой Telegram ID: <code>{tg_id}</code>\n\n"
            "Отправь его администратору для получения доступа.",
            parse_mode="HTML",
        )
        return
    await update.message.reply_text(
        "Нажми кнопку ниже для получения конфига.",
        reply_markup=_reply_keyboard(tg_id),
    )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(MessageHandler(filters.Text(["🔑 Получить конфиг"]), _get_config_menu))
    app.add_handler(MessageHandler(filters.Text(["👥 Пользователи"]), _users_list))
    app.add_handler(MessageHandler(filters.Text(["🏓 Пинг"]), _ping))
    app.add_handler(MessageHandler(filters.Text(["📊 Статус серверов"]), _server_status))
    app.add_handler(MessageHandler(filters.Text(["🔔 Проверить алерты"]), _check_alerts))
    app.add_handler(MessageHandler(filters.Text(["⛏ Minecraft"]), _minecraft_menu))
    app.add_handler(CallbackQueryHandler(_pick_user_callback, pattern=r"^pick_user:"))
    app.add_handler(CallbackQueryHandler(_config_callback, pattern=r"^config:"))
    app.add_handler(CallbackQueryHandler(_user_detail_callback, pattern=r"^user:"))
    app.add_handler(CallbackQueryHandler(_mc_callback, pattern=r"^mc:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _fallback))

    # Daily digest at 09:00 Moscow time (UTC+3 = 06:00 UTC)
    moscow_tz = timezone(timedelta(hours=3))
    app.job_queue.run_daily(
        _daily_digest_job,
        time=dt_time(hour=9, minute=0, tzinfo=moscow_tz),
        name="daily_digest",
    )

    # Periodic alert check every 5 minutes
    app.job_queue.run_repeating(
        _periodic_alert_job,
        interval=300,
        first=10,
        name="periodic_alerts",
    )

    # Minecraft whitelist rejection check every minute
    app.job_queue.run_repeating(
        _mc_rejection_alert_job,
        interval=60,
        first=30,
        name="mc_rejection_alerts",
    )

    app.run_polling()


if __name__ == "__main__":
    main()
