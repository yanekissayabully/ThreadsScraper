"""
Threads Scraper
---------------
Поиск постов по нескольким ключевым словам с фильтрацией по дате.

1. Установить зависимости
pip install -r requirements.txt
playwright install chromium

2. Сохранить куки (один раз — вручную логинишься в браузере)
python threads_scraper.py --save-cookies


Использование:
  python threads_scraper.py                  # поиск по умолчанию (последние 7 дней)
  python threads_scraper.py --days 3         # последние 3 дня
  python threads_scraper.py --save-cookies   # сохранить куки (нужно сделать один раз)
"""

import json
import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from playwright.async_api import async_playwright
from nested_lookup import nested_lookup
import jmespath
from parsel import Selector


# ─────────────────────────────────────────────
#  НАСТРОЙКИ — измени под себя
# ─────────────────────────────────────────────

KEYWORDS = [
    "амо срм внедрение",
]

DAYS_BACK = 15           # максимальный возраст поста в днях (можно менять через --days)
MAX_RESULTS = 100       # максимум постов на один запрос
SCROLL_COUNT = 8        # сколько раз скроллить страницу вниз (больше = медленнее, но полнее)
COOKIES_FILE = "threads_cookies.json"
OUTPUT_FILE  = "results.json"


# ─────────────────────────────────────────────
#  ФОРМАТИРОВАНИЕ ДАТЫ
# ─────────────────────────────────────────────

def format_date(unix_ts: Optional[int]) -> str:
    """Конвертирует Unix timestamp в читаемый формат с учётом часового пояса Алматы (UTC+5)."""
    if not unix_ts:
        return "—"
    almaty_tz = timezone(timedelta(hours=5))
    dt = datetime.fromtimestamp(unix_ts, tz=almaty_tz)
    return dt.strftime("%d.%m.%Y %H:%M")  # например: 27.05.2025 14:33


def is_within_days(unix_ts: Optional[int], days: int) -> bool:
    """Возвращает True если пост не старше `days` дней."""
    if not unix_ts:
        return False
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    post_dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return post_dt >= cutoff


# ─────────────────────────────────────────────
#  ПАРСИНГ ОДНОГО ПОСТА
# ─────────────────────────────────────────────

def parse_thread(data: Dict) -> Optional[Dict]:
    """Извлекает только нужные поля из сырых данных поста."""
    raw = jmespath.search(
        """{
            text:         post.caption.text,
            published_on: post.taken_at,
            username:     post.user.username,
            reply_count:  post.text_post_app_info.direct_reply_count,
            code:         post.code
        }""",
        data,
    )
    if not raw or not raw.get("text") or not raw.get("username"):
        return None

    return {
        "text":         raw["text"],
        "published_on": format_date(raw.get("published_on")),
        "username":     raw["username"],
        "reply_count":  raw.get("reply_count") or 0,
        "url":          f"https://www.threads.net/@{raw['username']}/post/{raw['code']}",
        "_ts":          raw.get("published_on"),  # служебное поле для фильтрации по дате
    }


# ─────────────────────────────────────────────
#  ИЗВЛЕЧЕНИЕ ПОСТОВ ИЗ HTML/JSON СТРАНИЦЫ
# ─────────────────────────────────────────────

def extract_from_page(html: str) -> List[Dict]:
    """Парсит hidden JSON из <script data-sjs> тегов на странице."""
    posts = []
    selector = Selector(html)
    datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()

    for dataset in datasets:
        if '"ScheduledServerJS"' not in dataset or "thread_items" not in dataset:
            continue
        try:
            data = json.loads(dataset)
        except json.JSONDecodeError:
            continue

        thread_items = nested_lookup("thread_items", data)
        for thread_list in thread_items:
            for item in thread_list:
                post = parse_thread(item)
                if post:
                    posts.append(post)

    return posts


# ─────────────────────────────────────────────
#  ПОИСК ПО ОДНОМУ КЛЮЧЕВОМУ СЛОВУ
# ─────────────────────────────────────────────

async def search_keyword(keyword: str, days: int, max_results: int) -> List[Dict]:
    """Открывает браузер, ищет посты по ключевому слову, фильтрует по дате."""

    # Загружаем куки
    try:
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"  ❌ Файл {COOKIES_FILE} не найден. Запустите: python threads_scraper.py --save-cookies")
        return []

    posts_found: List[Dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-KZ",
            timezone_id="Asia/Almaty",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Перехватываем XHR-ответы от GraphQL
        async def handle_response(response):
            if "api/graphql" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    thread_items = nested_lookup("thread_items", data)
                    for thread_list in thread_items:
                        for item in thread_list:
                            post = parse_thread(item)
                            if post:
                                posts_found.append(post)
                except Exception:
                    pass

        page.on("response", handle_response)

        # Открываем страницу поиска
        url = f"https://www.threads.net/search?q={keyword}&serp_type=default"
        print(f"  🌐 Открываем: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Также парсим hidden JSON с первой загрузки
        initial_posts = extract_from_page(await page.content())
        posts_found.extend(initial_posts)

        # Скроллим вниз для подгрузки новых постов
        for i in range(SCROLL_COUNT):
            await page.keyboard.press("End")
            await page.wait_for_timeout(2000)
            # Если уже набрали достаточно — останавливаемся
            if len(posts_found) >= max_results * 2:
                break
            print(f"  ↓ Скролл {i+1}/{SCROLL_COUNT}, собрано постов: {len(posts_found)}")

        await browser.close()

    # Дедупликация по URL
    seen_urls = set()
    unique = []
    for post in posts_found:
        if post["url"] not in seen_urls:
            seen_urls.add(post["url"])
            unique.append(post)

    # Фильтрация по дате
    filtered = [p for p in unique if is_within_days(p.get("_ts"), days)]

    # Удаляем служебное поле _ts из финального результата
    for post in filtered:
        post.pop("_ts", None)

    # Сортируем по дате (свежие первыми)
    filtered.sort(key=lambda p: p.get("published_on", ""), reverse=True)

    return filtered[:max_results]


# ─────────────────────────────────────────────
#  ПОИСК ПО НЕСКОЛЬКИМ КЛЮЧЕВЫМ СЛОВАМ
# ─────────────────────────────────────────────

async def search_all(keywords: List[str], days: int, max_results: int) -> List[Dict]:
    """Последовательно ищет по каждому ключевому слову и объединяет результаты."""
    all_posts: List[Dict] = []
    total = len(keywords)

    for i, keyword in enumerate(keywords, 1):
        print(f"\n[{i}/{total}] Поиск: «{keyword}»")
        posts = await search_keyword(keyword, days, max_results)
        print(f"  ✅ Найдено {len(posts)} постов за последние {days} дн.")
        all_posts.extend(posts)

    # Финальная дедупликация по URL (посты могли найтись по разным запросам)
    seen = set()
    unique_all = []
    for post in all_posts:
        if post["url"] not in seen:
            seen.add(post["url"])
            unique_all.append(post)

    # Финальная сортировка
    unique_all.sort(key=lambda p: p.get("published_on", ""), reverse=True)
    return unique_all


# ─────────────────────────────────────────────
#  СОХРАНЕНИЕ КУК (запустить один раз вручную)
# ─────────────────────────────────────────────

async def save_cookies():
    """Открывает браузер для ручного входа и сохраняет куки."""
    print("🌐 Открываем браузер. Залогиньтесь в Threads вручную...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.threads.net/login")
        print("✋ После входа нажмите Enter здесь в консоли...")
        input()
        cookies = await context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
        await browser.close()
    print(f"✅ Сохранено {len(cookies)} куков → {COOKIES_FILE}")


# ─────────────────────────────────────────────
#  ТОЧКА ВХОДА
# ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Threads Scraper")
    parser.add_argument("--save-cookies", action="store_true", help="Сохранить куки браузера")
    parser.add_argument("--days", type=int, default=DAYS_BACK,
                        help=f"Максимальный возраст постов в днях (по умолчанию: {DAYS_BACK})")
    parser.add_argument("--max", type=int, default=MAX_RESULTS,
                        help=f"Максимум постов на запрос (по умолчанию: {MAX_RESULTS})")
    args = parser.parse_args()

    if args.save_cookies:
        await save_cookies()
        return

    print(f"🔍 Запросы: {KEYWORDS}")
    print(f"📅 Период: последние {args.days} дн.")
    print(f"📦 Лимит: {args.max} постов на запрос")

    results = await search_all(KEYWORDS, args.days, args.max)

    # Вывод в консоль
    print(f"\n{'='*60}")
    print(f"Итого уникальных постов: {len(results)}")
    print(f"{'='*60}\n")

    for i, post in enumerate(results, 1):
        print(f"[{i}] @{post['username']}  •  {post['published_on']}  •  💬 {post['reply_count']}")
        text_preview = post['text'][:120].replace('\n', ' ')
        print(f"     {text_preview}{'...' if len(post['text']) > 120 else ''}")
        print(f"     🔗 {post['url']}")
        print()

    # Сохранение в файл
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено в {OUTPUT_FILE}")

    from ai_filter import filter_leads

    leads, non_leads = await filter_leads(results, min_score=6)

    # Сохраняем отдельно лиды
    with open("leads.json", "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

    print(f"\n🎯 ЛИДЫ ({len(leads)}):")
    for i, lead in enumerate(leads, 1):
        print(f"[{i}] @{lead['username']} | score: {lead['ai_score']}/10 | {lead['ai_lead_type']}")
        print(f"     {lead['ai_reason']}")
        print(f"     🔗 {lead['url']}\n")


if __name__ == "__main__":
    asyncio.run(main())