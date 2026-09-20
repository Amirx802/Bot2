import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from . import db
from .config import settings

log = logging.getLogger(__name__)


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user and update.effective_user.id in settings.admin_ids:
            return await func(update, context)
        await update.effective_message.reply_text("⛔ این دستور فقط برای ادمین است.")

    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.add_user(u.id, u.username, u.first_name)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 راهنما", callback_data="help")],
            [InlineKeyboardButton("ℹ️ درباره", callback_data="about")],
        ]
    )
    await update.message.reply_text(
        f"سلام {u.first_name} 👋\nبه ربات خوش اومدی!", reply_markup=kb
    )


HELP_TEXT = (
    "دستورات:\n"
    "/start - شروع\n"
    "/help - راهنما\n"
    "/ping - تست سرعت پاسخ\n"
    "/id - نمایش آیدی شما"
)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 pong")


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"آیدی شما: <code>{update.effective_user.id}</code>", parse_mode=ParseMode.HTML)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "help":
        await q.edit_message_text(HELP_TEXT)
    elif q.data == "about":
        await q.edit_message_text("این ربات با python-telegram-bot ساخته شده است.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.is_banned(update.effective_user.id):
        return
    await update.message.reply_text(update.message.text)


@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"👥 تعداد کاربران: {db.count_users()}")


@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("استفاده: /broadcast متن پیام")
        return
    ok = fail = 0
    for uid in db.all_user_ids():
        try:
            await context.bot.send_message(uid, text)
            ok += 1
        except (Forbidden, TelegramError):
            fail += 1
        await asyncio.sleep(0.05)  # رعایت محدودیت نرخ تلگرام
    await update.message.reply_text(f"✅ ارسال شد: {ok}\n❌ ناموفق: {fail}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("خطا در پردازش آپدیت", exc_info=context.error)
