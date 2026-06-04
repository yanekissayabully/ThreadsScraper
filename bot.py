# """
# Telegram-бот для получения лидов из Threads.
# Команды:
#   /scan       — запустить парсинг прямо сейчас
#   /leads      — показать последние лиды из кэша
#   /status     — статус последнего скана
#   /schedule   — показать расписание автосканирования
# """

# import asyncio
# import json
# import os
# from datetime import datetime
# from dotenv import load_dotenv

# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
# from telegram.constants import ParseMode
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

# from threads_scraper import search_all, KEYWORDS
# from ai_filter import filter_leads

# from handlers import cmd_search, cmd_help

# load_dotenv()

# TOKEN   = os.getenv("TELEGRAM_TOKEN")
# CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# # Кэш последних лидов
# _last_leads: list = []
# _last_scan_time: str = "не запускался"
# _scan_lock = asyncio.Lock()  # чтобы не запускать два скана одновременно


# # ─────────────────────────────────────────────
# #  ФОРМАТИРОВАНИЕ СООБЩЕНИЯ О ЛИДЕ
# # ─────────────────────────────────────────────

# def format_lead_message(lead: dict, index: int, total: int) -> str:
#     score      = lead.get("ai_score", 0)
#     score_bar  = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
#     lead_type  = lead.get("ai_lead_type", "").replace("_", " ")
#     text       = lead.get("text", "")[:300].replace("<", "&lt;").replace(">", "&gt;")

#     return (
#         f"{score_bar} <b>Лид {index}/{total}</b> | Оценка: <b>{score}/10</b>\n"
#         f"👤 <b>@{lead.get('username')}</b>  •  {lead.get('published_on')}\n"
#         f"🏷 {lead_type}\n\n"
#         f"{text}{'...' if len(lead.get('text','')) > 300 else ''}\n\n"
#         f"💡 <i>{lead.get('ai_reason', '')}</i>"
#     )


# def lead_keyboard(lead: dict) -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup([[
#         InlineKeyboardButton("🔗 Открыть пост", url=lead["url"])
#     ]])


# # ─────────────────────────────────────────────
# #  ОСНОВНАЯ ЛОГИКА СКАНА
# # ─────────────────────────────────────────────

# async def run_scan(days: int = 7) -> list:
#     """Запускает полный цикл: парсинг → AI-фильтрация → возвращает лиды."""
#     global _last_leads, _last_scan_time

#     async with _scan_lock:
#         print("🔄 Запуск скана...")
#         posts = await search_all(KEYWORDS, days=days, max_results=100)
#         leads, _ = await filter_leads(posts, min_score=6)

#         _last_leads = leads
#         _last_scan_time = datetime.now().strftime("%d.%m.%Y %H:%M")

#         # Сохраняем на диск
#         with open("leads.json", "w", encoding="utf-8") as f:
#             json.dump(leads, f, ensure_ascii=False, indent=2)

#         return leads


# # ─────────────────────────────────────────────
# #  КОМАНДЫ БОТА
# # ─────────────────────────────────────────────

# async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Запускает парсинг по команде /scan."""
#     if update.effective_chat.id != CHAT_ID:
#         return  # только для авторизованного чата

#     days = 7
#     if context.args:
#         try:
#             days = int(context.args[0])
#         except ValueError:
#             pass

#     msg = await update.message.reply_text(
#         f"🔄 Запускаю сканирование за последние {days} дн...\n"
#         "Это займёт несколько минут ⏳"
#     )

#     try:
#         leads = await run_scan(days=days)

#         if not leads:
#             await msg.edit_text("😶 Лидов не найдено за этот период.")
#             return

#         await msg.edit_text(f"✅ Готово! Найдено лидов: <b>{len(leads)}</b>", parse_mode=ParseMode.HTML)

#         # Отправляем каждый лид отдельным сообщением
#         for i, lead in enumerate(leads, 1):
#             text = format_lead_message(lead, i, len(leads))
#             await context.bot.send_message(
#                 chat_id=CHAT_ID,
#                 text=text,
#                 parse_mode=ParseMode.HTML,
#                 reply_markup=lead_keyboard(lead),
#             )
#             await asyncio.sleep(0.3)  # не спамим Telegram API

#     except Exception as e:
#         await msg.edit_text(f"❌ Ошибка: {e}")


# async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """/leads — показывает последние лиды из кэша."""
#     if update.effective_chat.id != CHAT_ID:
#         return

#     if not _last_leads:
#         await update.message.reply_text("📭 Кэш пуст. Запусти /scan")
#         return

#     await update.message.reply_text(f"📋 Последние лиды ({len(_last_leads)} шт), скан: {_last_scan_time}")
#     for i, lead in enumerate(_last_leads, 1):
#         text = format_lead_message(lead, i, len(_last_leads))
#         await context.bot.send_message(
#             chat_id=CHAT_ID,
#             text=text,
#             parse_mode=ParseMode.HTML,
#             reply_markup=lead_keyboard(lead),
#         )
#         await asyncio.sleep(0.3)


# async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """/status — текущий статус."""
#     if update.effective_chat.id != CHAT_ID:
#         return

#     scanning = _scan_lock.locked()
#     await update.message.reply_text(
#         f"📊 <b>Статус</b>\n\n"
#         f"{'⏳ Сканирование идёт прямо сейчас...' if scanning else '✅ Простаивает'}\n"
#         f"🕐 Последний скан: {_last_scan_time}\n"
#         f"📌 Лидов в кэше: {len(_last_leads)}",
#         parse_mode=ParseMode.HTML
#     )


# async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """/schedule — расписание автосканирования."""
#     if update.effective_chat.id != CHAT_ID:
#         return
#     await update.message.reply_text(
#         "🕒 <b>Расписание</b>\n\n"
#         "Автоскан запускается каждые <b>6 часов</b>.\n"
#         "Запустить вручную: /scan\n"
#         "Указать период: /scan 3 (за 3 дня)",
#         parse_mode=ParseMode.HTML
#     )


# # ─────────────────────────────────────────────
# #  АВТОМАТИЧЕСКОЕ СКАНИРОВАНИЕ ПО РАСПИСАНИЮ
# # ─────────────────────────────────────────────

# async def scheduled_scan(app: Application):
#     """Запускается по расписанию, отправляет лиды в чат."""
#     print(f"⏰ Автоскан: {datetime.now().strftime('%H:%M')}")
#     try:
#         leads = await run_scan(days=7)
#         if not leads:
#             await app.bot.send_message(chat_id=CHAT_ID, text="⏰ Автоскан: лидов не найдено.")
#             return

#         await app.bot.send_message(
#             chat_id=CHAT_ID,
#             text=f"⏰ <b>Автоскан завершён</b>\nНайдено лидов: <b>{len(leads)}</b>",
#             parse_mode=ParseMode.HTML
#         )
#         for i, lead in enumerate(leads, 1):
#             text = format_lead_message(lead, i, len(leads))
#             await app.bot.send_message(
#                 chat_id=CHAT_ID,
#                 text=text,
#                 parse_mode=ParseMode.HTML,
#                 reply_markup=lead_keyboard(lead),
#             )
#             await asyncio.sleep(0.3)
#     except Exception as e:
#         await app.bot.send_message(chat_id=CHAT_ID, text=f"❌ Ошибка автоскана: {e}")


# # ─────────────────────────────────────────────
# #  ЗАПУСК БОТА
# # ─────────────────────────────────────────────

# async def post_init(app: Application):
#     """Запускается после старта event loop — здесь безопасно стартовать планировщик."""
#     scheduler = AsyncIOScheduler()
#     scheduler.add_job(
#         scheduled_scan,
#         trigger="interval",
#         hours=6,
#         args=[app],
#         id="auto_scan"
#     )
#     scheduler.start()
#     print("⏰ Планировщик запущен (каждые 6 часов)")


# def main():
#     app = (
#         Application.builder()
#         .token(TOKEN)
#         .post_init(post_init)   # ← планировщик стартует здесь
#         .build()
#     )

#     app.add_handler(CommandHandler("search",   cmd_search))
#     app.add_handler(CommandHandler("scan",     cmd_scan))
#     app.add_handler(CommandHandler("leads",    cmd_leads))
#     app.add_handler(CommandHandler("status",   cmd_status))
#     app.add_handler(CommandHandler("schedule", cmd_schedule))
#     app.add_handler(CommandHandler("help",     cmd_help))

#     print("🤖 Бот запущен. Ctrl+C для остановки.")
#     app.run_polling(allowed_updates=Update.ALL_TYPES)


# if __name__ == "__main__":
#     main()



"""
Telegram-бот для получения лидов из Threads.
Работает в группе и в личке.
"""

"""
Telegram-бот для получения лидов из Threads.
Работает в группе и в личке — доступен всем участникам.
"""

import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from threads_scraper import search_all, KEYWORDS
from ai_filter import filter_leads
from handlers import cmd_search, cmd_help

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Кэш последних лидов
_last_leads: list = []
_last_scan_time: str = "не запускался"
_scan_lock = asyncio.Lock()


# ─────────────────────────────────────────────
#  ФОРМАТИРОВАНИЕ СООБЩЕНИЯ О ЛИДЕ
# ─────────────────────────────────────────────

def format_lead_message(lead: dict, index: int, total: int) -> str:
    score = lead.get("ai_score", 0)
    score_bar = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
    lead_type = lead.get("ai_lead_type", "").replace("_", " ")
    text = lead.get("text", "")[:300].replace("<", "&lt;").replace(">", "&gt;")

    return (
        f"{score_bar} <b>Лид {index}/{total}</b> | Оценка: <b>{score}/10</b>\n"
        f"👤 <b>@{lead.get('username')}</b>  •  {lead.get('published_on')}\n"
        f"🏷 {lead_type}\n\n"
        f"{text}{'...' if len(lead.get('text','')) > 300 else ''}\n\n"
        f"💡 <i>{lead.get('ai_reason', '')}</i>"
    )


def lead_keyboard(lead: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔗 Открыть пост", url=lead["url"])
    ]])


# ─────────────────────────────────────────────
#  ОСНОВНАЯ ЛОГИКА СКАНА
# ─────────────────────────────────────────────

async def run_scan(days: int = 7) -> list:
    """Запускает полный цикл: парсинг → AI-фильтрация → возвращает лиды."""
    global _last_leads, _last_scan_time

    async with _scan_lock:
        print("🔄 Запуск скана...")
        posts = await search_all(KEYWORDS, days=days, max_results=100)
        leads, _ = await filter_leads(posts, min_score=6)

        _last_leads = leads
        _last_scan_time = datetime.now().strftime("%d.%m.%Y %H:%M")

        with open("leads.json", "w", encoding="utf-8") as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)

        return leads


# ─────────────────────────────────────────────
#  КОМАНДЫ БОТА (ДОСТУПНЫ ВСЕМ)
# ─────────────────────────────────────────────

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает парсинг по команде /scan."""
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
        except ValueError:
            pass

    msg = await update.message.reply_text(
        f"🔄 Запускаю сканирование за последние {days} дн...\n"
        "Это займёт несколько минут ⏳"
    )

    try:
        leads = await run_scan(days=days)

        if not leads:
            await msg.edit_text("😶 Лидов не найдено за этот период.")
            return

        await msg.edit_text(f"✅ Готово! Найдено лидов: <b>{len(leads)}</b>", parse_mode=ParseMode.HTML)

        for i, lead in enumerate(leads, 1):
            text = format_lead_message(lead, i, len(leads))
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=lead_keyboard(lead),
            )
            await asyncio.sleep(0.3)

    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние лиды из кэша."""
    if not _last_leads:
        await update.message.reply_text("📭 Кэш пуст. Запусти /scan")
        return

    await update.message.reply_text(f"📋 Последние лиды ({len(_last_leads)} шт), скан: {_last_scan_time}")
    for i, lead in enumerate(_last_leads, 1):
        text = format_lead_message(lead, i, len(_last_leads))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=lead_keyboard(lead),
        )
        await asyncio.sleep(0.3)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус последнего скана."""
    scanning = _scan_lock.locked()
    await update.message.reply_text(
        f"📊 <b>Статус</b>\n\n"
        f"{'⏳ Сканирование идёт...' if scanning else '✅ Простаивает'}\n"
        f"🕐 Последний скан: {_last_scan_time}\n"
        f"📌 Лидов в кэше: {len(_last_leads)}",
        parse_mode=ParseMode.HTML
    )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание автосканирования."""
    await update.message.reply_text(
        "🕒 <b>Расписание</b>\n\n"
        "Автоскан запускается каждые <b>6 часов</b>.\n"
        "Запустить вручную: /scan\n"
        "Кастомный поиск: /search \"слова\" 7",
        parse_mode=ParseMode.HTML
    )


# ─────────────────────────────────────────────
#  АВТОМАТИЧЕСКОЕ СКАНИРОВАНИЕ
# ─────────────────────────────────────────────

async def scheduled_scan(app: Application):
    """Автоскан по расписанию."""
    print(f"⏰ Автоскан: {datetime.now().strftime('%H:%M')}")
    try:
        leads = await run_scan(days=7)
        # В автоскане не отправляем в чат, только сохраняем
        print(f"  ✅ Автоскан завершён, найдено лидов: {len(leads)}")
    except Exception as e:
        print(f"  ❌ Ошибка автоскана: {e}")


# ─────────────────────────────────────────────
#  ЗАПУСК БОТА
# ─────────────────────────────────────────────

async def post_init(app: Application):
    """Запуск планировщика после старта."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_scan,
        trigger="interval",
        hours=6,
        args=[app],
        id="auto_scan"
    )
    scheduler.start()
    print("⏰ Планировщик запущен (каждые 6 часов)")


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Регистрируем команды (доступны всем)
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("help", cmd_help))

    print("🤖 Бот запущен. Ctrl+C для остановки.")
    print("👥 Доступ открыт для всех участников групп и личных чатов")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()