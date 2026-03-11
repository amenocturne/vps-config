import io
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

from config import BOT_TOKEN, ADMIN_TELEGRAM_ID
import remnawave

_auth_cache: dict[int, list[dict]] = {}

CLIENT_TYPES = [
    [("V2Ray/Streisand", "v2ray-json"), ("Clash", "clash")],
    [("Sing-Box", "singbox"), ("Mihomo", "mihomo")],
    [("Stash", "stash"), ("JSON", "json")],
]


def _reply_keyboard(tg_id: int) -> ReplyKeyboardMarkup:
    rows = [["🔑 Получить конфиг"]]
    if tg_id == ADMIN_TELEGRAM_ID:
        rows.append(["👥 Пользователи", "🏓 Пинг"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def _authorize(tg_id: int) -> list[dict] | None:
    if tg_id in _auth_cache:
        return _auth_cache[tg_id]
    users = await remnawave.get_users_by_telegram_id(tg_id)
    if users:
        _auth_cache[tg_id] = users
    return users


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    users = await _authorize(tg_id)
    if not users:
        return
    await update.message.reply_text(
        "Привет! Используй кнопку ниже для получения конфига.",
        reply_markup=_reply_keyboard(tg_id),
    )


async def _get_config_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if not await _authorize(tg_id):
        return
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"config:{cb}") for label, cb in row]
        for row in CLIENT_TYPES
    ]
    await update.message.reply_text(
        "Выбери формат конфига:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    tg_id = query.from_user.id
    users = await _authorize(tg_id)
    if not users:
        await query.answer()
        return

    client_type = query.data.removeprefix("config:")
    short_uuid = users[0]["shortUuid"]

    try:
        config = await remnawave.get_subscription(short_uuid, client_type)
    except Exception:
        await query.answer("Ошибка при получении конфига", show_alert=True)
        return

    await query.answer()

    if len(config) <= 4096:
        await query.message.reply_text(f"```\n{config}\n```", parse_mode="Markdown")
    else:
        buf = io.BytesIO(config.encode())
        buf.name = f"{client_type}.txt"
        await query.message.reply_document(buf, filename=f"{client_type}.txt")


async def _users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    if tg_id != ADMIN_TELEGRAM_ID or not await _authorize(tg_id):
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
    if tg_id != ADMIN_TELEGRAM_ID or not await _authorize(tg_id):
        return

    ok = await remnawave.ping()
    status = "✅ API доступен" if ok else "❌ API недоступен"
    await update.message.reply_text(status)


async def _fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
    users = await _authorize(tg_id)
    if not users:
        return
    await update.message.reply_text(
        "Используй кнопку ниже для получения конфига.",
        reply_markup=_reply_keyboard(tg_id),
    )


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(MessageHandler(filters.Text(["🔑 Получить конфиг"]), _get_config_menu))
    app.add_handler(MessageHandler(filters.Text(["👥 Пользователи"]), _users_list))
    app.add_handler(MessageHandler(filters.Text(["🏓 Пинг"]), _ping))
    app.add_handler(CallbackQueryHandler(_config_callback, pattern=r"^config:"))
    app.add_handler(CallbackQueryHandler(_user_detail_callback, pattern=r"^user:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _fallback))

    app.run_polling()


if __name__ == "__main__":
    main()
