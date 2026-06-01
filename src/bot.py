from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import database as db
from downloader import normalize_url
from worker import archive_account, pause_account, resume_account

logger = logging.getLogger(__name__)

HELP_TEXT = """
📋 *Comandos disponibles*

/add <@canal|URL> [--comments [-N]] — archivar canal o playlist
  Ejemplos:
  /add @MrBeast
  /add https://youtube.com/@MrBeast
  /add @MrBeast --comments
  /add @MrBeast --comments -500

/remove <@canal|URL> — dejar de monitorear
/stop <@canal|URL> — pausar envío
/resume <@canal|URL> — reanudar desde donde quedó
/restart <@canal|URL> — reenviar todo desde el principio
/list — ver canales monitoreados
/status — estado del bot
/help — mostrar esta ayuda
""".strip()


def _parse_add_args(args: list[str]) -> tuple[str, bool, Optional[int]]:
    """Returns (identifier, comments_enabled, comments_limit)."""
    identifier = args[0]
    comments_enabled = "--comments" in args
    comments_limit: Optional[int] = None

    if comments_enabled:
        idx = args.index("--comments")
        if idx + 1 < len(args):
            nxt = args[idx + 1]
            if nxt.startswith("-") and nxt[1:].isdigit():
                comments_limit = int(nxt[1:])

    return identifier, comments_enabled, comments_limit


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /add <@canal|URL> [--comments [-N]]\nEjemplo: /add @MrBeast --comments -500"
        )
        return

    identifier, comments_enabled, comments_limit = _parse_add_args(context.args)
    url = normalize_url(identifier)
    chat_id = update.effective_chat.id

    existing = await db.get_account_by_url_and_chat(url, chat_id)
    if existing and existing["is_active"]:
        await update.message.reply_text(f"Ya está siendo monitoreado en este chat.")
        return

    account = await db.add_account(
        identifier=identifier,
        url=url,
        chat_id=chat_id,
        comments_enabled=comments_enabled,
        comments_limit=comments_limit,
    )
    context.application.create_task(archive_account(context.bot, account))


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /remove <@canal|URL>")
        return

    url = normalize_url(context.args[0])
    chat_id = update.effective_chat.id
    removed = await db.remove_account(url, chat_id)

    if removed:
        await update.message.reply_text("✅ Canal eliminado del monitoreo.")
    else:
        await update.message.reply_text("No se encontró ese canal en este chat.")


async def _get_account_from_args(args: list[str], chat_id: int) -> Optional[dict]:
    if not args:
        return None
    url = normalize_url(args[0])
    return await db.get_account_by_url_and_chat(url, chat_id)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /stop <@canal|URL>")
        return

    account = await _get_account_from_args(context.args, update.effective_chat.id)
    if not account or not account["is_active"]:
        await update.message.reply_text("Canal no encontrado en este chat.")
        return

    await pause_account(account)
    label = account.get("display_name") or account["identifier"]
    await update.message.reply_text(f"⏸️ {label} pausado.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /resume <@canal|URL>")
        return

    account = await _get_account_from_args(context.args, update.effective_chat.id)
    if not account or not account["is_active"]:
        await update.message.reply_text("Canal no encontrado en este chat.")
        return

    await resume_account(account)
    label = account.get("display_name") or account["identifier"]
    await update.message.reply_text(f"▶️ {label} reanudado.")
    context.application.create_task(archive_account(context.bot, account, resuming=True))


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /restart <@canal|URL>")
        return

    account = await _get_account_from_args(context.args, update.effective_chat.id)
    if not account or not account["is_active"]:
        await update.message.reply_text("Canal no encontrado en este chat.")
        return

    label = account.get("display_name") or account["identifier"]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"restart:confirm:{account['id']}"),
        InlineKeyboardButton("❌ Cancelar",  callback_data="restart:cancel"),
    ]])
    await update.message.reply_text(
        f"⚠️ ¿Reiniciar el envío de *{label}*?\nSe reenviarán todos los videos desde el principio.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def callback_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()

        if query.data == "restart:cancel":
            await query.edit_message_text("❌ Reinicio cancelado.")
            return

        account_id = int(query.data.split(":")[-1])
        account = await db.get_account_by_id(account_id)
        if not account:
            await query.edit_message_text("❌ Canal no encontrado.")
            return

        label = account.get("display_name") or account["identifier"]
        await db.reset_account_sent(account["id"])
        await resume_account(account)
        await query.edit_message_text(f"🔄 {label} — reiniciando desde el principio…")
        context.application.create_task(archive_account(context.bot, account))

    except Exception as exc:
        logger.error("callback_restart error: %s", exc)
        try:
            await query.edit_message_text("❌ Error al procesar. Intentá de nuevo.")
        except Exception:
            pass


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await db.get_active_accounts()
    if not accounts:
        await update.message.reply_text("No hay canales monitoreados.")
        return

    lines = ["📋 Canales monitoreados:\n"]
    for acc in accounts:
        label = acc.get("display_name") or acc["identifier"]
        count = await db.get_account_video_count(acc["id"])
        last = acc["last_checked"]
        last_str = last.strftime("%Y-%m-%d %H:%M UTC") if last else "nunca"
        comments_str = f" · 💬 {'todos' if not acc['comments_limit'] else acc['comments_limit']}" if acc["comments_enabled"] else ""
        lines.append(f"• {label}{comments_str} — {count} videos — revisado: {last_str}")

    await update.message.reply_text("\n".join(lines))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await db.get_active_accounts()
    await update.message.reply_text(
        f"🤖 Bot activo\n📊 {len(accounts)} canal(es) monitoreado(s)"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


def build_app() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("add",     cmd_add))
    app.add_handler(CommandHandler("remove",  cmd_remove))
    app.add_handler(CommandHandler("stop",    cmd_stop))
    app.add_handler(CommandHandler("resume",  cmd_resume))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("list",    cmd_list))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(callback_restart, pattern="^restart:"))
    return app
