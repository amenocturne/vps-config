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

from config import BOT_TOKEN, ADMIN_TELEGRAM_ID, CLIENT_TYPES
import remnawave

def _reply_keyboard(tg_id: int) -> ReplyKeyboardMarkup:
    rows = [["🔑 Получить конфиг"]]
    if tg_id == ADMIN_TELEGRAM_ID:
        rows.append(["👥 Пользователи", "🏓 Пинг"])
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
        await update.message.reply_text(
            "Выбери формат конфига:",
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
    await query.answer()
    await query.message.reply_text(
        "Выбери формат конфига:",
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
    await update.message.reply_text(status)


async def _fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = update.effective_user.id
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
    app.add_handler(CallbackQueryHandler(_pick_user_callback, pattern=r"^pick_user:"))
    app.add_handler(CallbackQueryHandler(_config_callback, pattern=r"^config:"))
    app.add_handler(CallbackQueryHandler(_user_detail_callback, pattern=r"^user:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _fallback))

    app.run_polling()


if __name__ == "__main__":
    main()
