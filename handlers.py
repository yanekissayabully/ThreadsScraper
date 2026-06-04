# """
# Обработчики команд для Telegram-бота
# Новые команды: /search "ключ1, ключ2" 7
# """

# from telegram import Update
# from telegram.ext import ContextTypes
# from telegram.constants import ParseMode
# import asyncio
# import json
# from datetime import datetime

# from threads_scraper import search_all
# from ai_filter import filter_leads


# async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     /search ключевые_слова дни
    
#     Примеры:
#     /search "амо срм, битрикс, интеграция" 7
#     /search "waba, телефония" 3
#     """
#     if not context.args:
#         await update.message.reply_text(
#             "❌ Укажи ключевые слова и период.\n\n"
#             "Пример:\n"
#             "/search \"амо срм, битрикс, интеграция\" 7\n\n"
#             "Слова через запятую в кавычках, затем число дней."
#         )
#         return

#     # Парсим аргументы
#     try:
#         # Первый аргумент — строка с ключевыми словами в кавычках
#         # Telegram сам разбивает, поэтому собираем до первого числа
#         args_list = ' '.join(context.args).split('"')
#         keywords_str = args_list[1] if len(args_list) > 1 else context.args[0]
        
#         # Ищем число дней
#         days = None
#         for part in context.args:
#             if part.isdigit():
#                 days = int(part)
#                 break
        
#         if days is None:
#             days = 7  # по умолчанию
        
#         # Разбираем ключевые слова
#         keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        
#     except Exception as e:
#         await update.message.reply_text(f"❌ Ошибка в формате: {e}\nИспользуй: /search \"слово1, слово2\" 7")
#         return

#     msg = await update.message.reply_text(
#         f"🔍 Ищу по ключевым словам:\n"
#         f"`{', '.join(keywords)}`\n"
#         f"📅 За последние {days} дней\n"
#         f"⏳ Это займёт 1-3 минуты...",
#         parse_mode=ParseMode.MARKDOWN
#     )

#     try:
#         # 1. Парсим Threads
#         posts = await search_all(keywords, days=days, max_results=100)
        
#         if not posts:
#             await msg.edit_text("😶 Ничего не найдено по твоим ключевым словам.")
#             return

#         # 2. AI-анализ
#         leads, non_leads = await filter_leads(posts, min_score=6)

#         # 3. Сохраняем результат в JSON (опционально — присылаем файлом)
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
#         # Весь результат
#         all_results_file = f"all_results_{timestamp}.json"
#         with open(all_results_file, "w", encoding="utf-8") as f:
#             json.dump(posts, f, ensure_ascii=False, indent=2)
        
#         # Только лиды
#         leads_file = f"leads_{timestamp}.json"
#         with open(leads_file, "w", encoding="utf-8") as f:
#             json.dump(leads, f, ensure_ascii=False, indent=2)

#         # 4. Отправляем отчёт
#         await msg.edit_text(
#             f"✅ Готово!\n\n"
#             f"📊 Всего постов: {len(posts)}\n"
#             f"🎯 Лидов найдено: {len(leads)}\n"
#             f"⏱️ Срок: {days} дней",
#             parse_mode=ParseMode.MARKDOWN
#         )

#         # 5. Отправляем JSON-файлы (чтобы можно было скачать)
#         await update.message.reply_document(
#             document=open(all_results_file, "rb"),
#             filename=all_results_file,
#             caption=f"📄 Все посты ({len(posts)} шт)"
#         )
        
#         if leads:
#             await update.message.reply_document(
#                 document=open(leads_file, "rb"),
#                 filename=leads_file,
#                 caption=f"🎯 Отфильтрованные лиды ({len(leads)} шт)"
#             )
#         else:
#             await update.message.reply_text("😶 Лидов не найдено после AI-анализа.")

#         # 6. Отправляем краткую сводку лидов в чат (первые 5)
#         if leads:
#             await update.message.reply_text("🎯 <b>ТОП-5 ЛИДОВ</b>", parse_mode=ParseMode.HTML)
#             for i, lead in enumerate(leads[:5], 1):
#                 score = lead.get("ai_score", 0)
#                 score_icon = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
#                 text = f"{score_icon} <b>Лид {i}</b> | Оценка: {score}/10\n"
#                 text += f"👤 @{lead['username']}\n"
#                 text += f"📝 {lead['text'][:150]}...\n"
#                 text += f"🔗 <a href='{lead['url']}'>Открыть пост</a>"
                
#                 await update.message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
#                 await asyncio.sleep(0.3)

#         # Очищаем временные файлы
#         import os
#         os.remove(all_results_file)
#         if leads:
#             os.remove(leads_file)

#     except Exception as e:
#         await msg.edit_text(f"❌ Ошибка: {e}")


# async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Помощь по командам"""
#     help_text = """
# 🤖 <b>Threads Lead Bot</b>

# <b>🔍 Основные команды:</b>
# /search "ключ1, ключ2" [дни]  — поиск и анализ
#    Пример: /search "амо срм, битрикс" 7

# /scan [дни]                    — сканирование по умолчанию (твои сохранённые ключи)
# /leads                         — показать последние лиды из кэша
# /status                        — статус последнего скана
# /schedule                      — расписание автоскана

# <b>📦 Результат:</b>
# Приходит 2 файла JSON:
# - <code>all_results_*.json</code> — все посты
# - <code>leads_*.json</code> — только лиды (оценка ≥6/10)

# <b>⚙️ Настройки:</b>
# Твои дефолтные ключи в <code>threads_scraper.py</code> (переменная KEYWORDS)
# """
#     await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)




"""
Обработчики команд для Telegram-бота
Новые команды: /search "ключ1, ключ2" 7
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import asyncio
import json
from datetime import datetime
import os

# Импортируем модули парсинга и AI
import sys
sys.path.append(os.path.dirname(__file__))
from threads_scraper import search_all
from ai_filter import filter_leads


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /search ключевые_слова дни
    
    Примеры:
    /search "амо срм, битрикс, интеграция" 7
    /search "waba, телефония" 3
    """
    # Проверяем аргументы
    if not context.args:
        await update.message.reply_text(
            "❌ Укажи ключевые слова и период.\n\n"
            "📝 <b>Как использовать:</b>\n"
            "/search \"ключевые слова через запятую\" [дни]\n\n"
            "📌 <b>Примеры:</b>\n"
            "/search \"амо срм, битрикс24\" 7\n"
            "/search \"интеграция whatsapp, телефония\" 3\n"
            "/search \"waba\" 14\n\n"
            "<i>По умолчанию период: 7 дней</i>",
            parse_mode=ParseMode.HTML
        )
        return

    # Парсим аргументы
    try:
        # Собираем все аргументы в строку
        full_args = ' '.join(context.args)
        
        # Ищем кавычки
        if '"' in full_args:
            # Разбираем по кавычкам
            parts = full_args.split('"')
            keywords_str = parts[1] if len(parts) > 1 else full_args
            # Остальное — дни
            rest = parts[2] if len(parts) > 2 else ""
        else:
            # Если без кавычек — первый аргумент это ключевые слова
            keywords_str = context.args[0]
            rest = ' '.join(context.args[1:])
        
        # Ищем число дней
        days = 7  # по умолчанию
        for word in rest.split():
            if word.isdigit():
                days = int(word)
                break
        
        # Если не нашли в rest, ищем в аргументах
        if days == 7:
            for arg in context.args:
                if arg.isdigit():
                    days = int(arg)
                    break
        
        # Разбираем ключевые слова (по запятой)
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        
        if not keywords:
            await update.message.reply_text("❌ Не указаны ключевые слова для поиска.")
            return
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка в формате: {str(e)}\n\n"
            "Используй: /search \"слово1, слово2, слово3\" 7"
        )
        return

    # Отправляем сообщение о начале поиска
    msg = await update.message.reply_text(
        f"🔍 <b>Запущен поиск лидов</b>\n\n"
        f"📝 <b>Ключевые слова:</b>\n"
        f"<code>{', '.join(keywords)}</code>\n\n"
        f"📅 <b>Период:</b> последние {days} дней\n\n"
        f"⏳ <i>Парсинг Threads и AI-анализ...\nЭто займёт 1-3 минуты</i>",
        parse_mode=ParseMode.HTML
    )

    try:
        # 1. Парсим Threads
        posts = await search_all(keywords, days=days, max_results=100)
        
        if not posts:
            await msg.edit_text(
                f"😶 <b>Ничего не найдено</b>\n\n"
                f"По ключевым словам:\n<code>{', '.join(keywords)}</code>\n\n"
                f"За {days} дней в Threads ничего не нашлось.\n"
                f"Попробуй другие ключевые слова или увеличь период.",
                parse_mode=ParseMode.HTML
            )
            return

        # 2. AI-анализ
        leads, non_leads = await filter_leads(posts, min_score=6)

        # 3. Сохраняем результат в JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Весь результат
        all_results_file = f"all_results_{timestamp}.json"
        with open(all_results_file, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        
        # Только лиды
        leads_file = f"leads_{timestamp}.json"
        with open(leads_file, "w", encoding="utf-8") as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)

        # 4. Отправляем отчёт
        await msg.edit_text(
            f"✅ <b>Поиск завершён!</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Всего постов: <code>{len(posts)}</code>\n"
            f"• Лидов найдено: <code>{len(leads)}</code>\n"
            f"• Не лидов: <code>{len(non_leads)}</code>\n\n"
            f"⏱️ Период: {days} дней\n"
            f"🔑 Ключевые слова: <code>{', '.join(keywords)}</code>",
            parse_mode=ParseMode.HTML
        )

        # 5. Отправляем JSON-файлы
        # Файл со всеми постами
        with open(all_results_file, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=all_results_file,
                caption=f"📄 <b>Все посты</b> ({len(posts)} шт)\n<code>сырые данные без фильтрации</code>",
                parse_mode=ParseMode.HTML
            )
        
        # Файл с лидами
        if leads:
            with open(leads_file, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=leads_file,
                    caption=f"🎯 <b>Отфильтрованные лиды</b> ({len(leads)} шт)\n<code>только качественные лиды (оценка ≥6/10)</code>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                "😶 <b>Лидов не найдено</b>\n\n"
                "AI-анализ не выявил релевантных лидов.\n"
                "Попробуй другие ключевые слова.",
                parse_mode=ParseMode.HTML
            )

        # 6. Отправляем топ-5 лидов в чат (если есть)
        if leads:
            await update.message.reply_text(
                f"🏆 <b>ТОП-{min(5, len(leads))} ЛИДОВ</b>\n"
                f"(отсортированы по релевантности)\n"
                f"{'─' * 20}",
                parse_mode=ParseMode.HTML
            )
            
            for i, lead in enumerate(leads[:5], 1):
                score = lead.get("ai_score", 0)
                score_icon = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
                lead_type = lead.get("ai_lead_type", "не_лид").replace("_", " ")
                text_preview = lead.get('text', '')[:200].replace('\n', ' ')
                
                lead_text = (
                    f"{score_icon} <b>Лид {i}</b> | Оценка: <b>{score}/10</b> | 🏷 {lead_type}\n"
                    f"👤 <b>@{lead.get('username')}</b>\n"
                    f"📅 {lead.get('published_on')}\n\n"
                    f"📝 {text_preview}...\n\n"
                    f"💡 <i>{lead.get('ai_reason', '')}</i>\n\n"
                    f"🔗 <a href='{lead['url']}'>Открыть пост в Threads</a>"
                )
                
                await update.message.reply_text(
                    lead_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(0.5)  # пауза между сообщениями

        # 7. Очищаем временные файлы
        os.remove(all_results_file)
        if leads:
            os.remove(leads_file)

    except Exception as e:
        await msg.edit_text(
            f"❌ <b>Ошибка при выполнении поиска</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Попробуй ещё раз или обратись к администратору.",
            parse_mode=ParseMode.HTML
        )
        print(f"Ошибка в cmd_search: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь по командам"""
    help_text = """
🤖 <b>Threads Lead Bot</b> — поиск лидов в Threads

<b>🔍 Основные команды:</b>

/search "ключ1, ключ2" [дни]  — поиск и AI-анализ
   Пример: /search "амо срм, битрикс24" 7

/scan [дни]                    — поиск по дефолтным ключам
/leads                         — показать последние лиды
/status                        — статус последнего скана
/schedule                      — расписание автоскана
/help                          — это сообщение

<b>📦 Что приходит:</b>
• 2 JSON-файла:
  - <code>all_results_*.json</code> — все найденные посты
  - <code>leads_*.json</code> — только лиды (оценка ≥6/10)
• Топ-5 лидов с краткой информацией

<b>💡 Советы:</b>
• Ключевые слова пиши через запятую
• Бери в кавычки: /search "слова, сюда"
• Дни можно не указывать (по умолчанию 7)
• Экспериментируй с ключевыми словами

<b>🎯 Примеры запросов:</b>
/search "амо срм внедрение" 14
/search "битрикс24 настройка, интеграция" 7
/search "waba, телефония, whatsapp api" 3
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)