# БАЗОВЫЙ СКРЕПЕР, ИСПОЛЬЗУЕТ 1 ЗАПРОС
# Пошаговый запуск
# Шаг 1 — сохранить куки (один раз):
# python scraper.py --save-cookies
# Откроется браузер → логинитесь → Enter
# Шаг 2 — запустить поиск:
# python scraper.py


import json
import asyncio
from typing import Dict, List
from playwright.async_api import async_playwright
from nested_lookup import nested_lookup
import jmespath
from parsel import Selector


# ─── Парсеры ───────────────────────────────────────────────────

def parse_thread(data: Dict) -> Dict:
    result = jmespath.search("""{
        text: post.caption.text,
        published_on: post.taken_at,
        id: post.id,
        code: post.code,
        username: post.user.username,
        user_verified: post.user.is_verified,
        like_count: post.like_count,
        reply_count: post.text_post_app_info.direct_reply_count,
        images: post.carousel_media[].image_versions2.candidates[1].url,
        videos: post.video_versions[].url
    }""", data)
    
    if result and result.get("code") and result.get("username"):
        result["url"] = f"https://www.threads.net/@{result['username']}/post/{result['code']}"
    
    result["videos"] = list(set(result.get("videos") or []))
    return result


# ─── Поиск по ключевому слову ───────────────────────────────────

async def search_threads(keyword: str, max_results: int = 50) -> List[Dict]:
    """
    Ищет посты по ключевому слову.
    Требует: в браузере должны быть куки авторизованного аккаунта Threads.
    """
    results = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # headless=True в production
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-KZ",  # Казахстанская локаль
            timezone_id="Asia/Almaty",
        )
        
        # Загружаем сохранённые куки (получаем один раз вручную)
        try:
            with open("threads_cookies.json", "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
        except FileNotFoundError:
            print("⚠️  Куки не найдены. Запустите save_cookies() сначала.")
            return []
        
        page = await context.new_page()
        
        # Перехватываем XHR-запросы к GraphQL
        captured_posts = []
        
        async def handle_response(response):
            if "api/graphql" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    # Ищем данные поиска
                    thread_items = nested_lookup("thread_items", data)
                    for thread_list in thread_items:
                        for item in thread_list:
                            post = parse_thread(item)
                            if post.get("text") and keyword.lower() in post["text"].lower():
                                captured_posts.append(post)
                except:
                    pass
        
        page.on("response", handle_response)
        
        # Открываем страницу поиска
        search_url = f"https://www.threads.net/search?q={keyword}&serp_type=default"
        await page.goto(search_url)
        await page.wait_for_timeout(3000)
        
        # Также парсим hidden JSON на странице
        selector = Selector(await page.content())
        hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
        
        for hidden_dataset in hidden_datasets:
            if '"ScheduledServerJS"' not in hidden_dataset:
                continue
            if "thread_items" not in hidden_dataset:
                continue
            data = json.loads(hidden_dataset)
            thread_items = nested_lookup("thread_items", data)
            for thread_list in thread_items:
                for item in thread_list:
                    post = parse_thread(item)
                    if post.get("text"):
                        captured_posts.append(post)
        
        # Скроллим для загрузки большего количества постов
        for _ in range(5):
            await page.keyboard.press("End")
            await page.wait_for_timeout(2000)
        
        await browser.close()
        
        # Дедупликация по id
        seen = set()
        unique_posts = []
        for post in captured_posts:
            pid = post.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                unique_posts.append(post)
        
        return unique_posts[:max_results]


# ─── Сохранение куков (запускается один раз вручную) ────────────

async def save_cookies():
    """
    Открывает браузер, вы логинитесь вручную, куки сохраняются.
    Запустить один раз: python scraper.py --save-cookies
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://www.threads.net/login")
        print("✅ Залогиньтесь вручную и нажмите Enter в консоли...")
        input()
        
        cookies = await context.cookies()
        with open("threads_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)
        
        print(f"✅ Сохранено {len(cookies)} куков в threads_cookies.json")
        await browser.close()


# ─── Запуск ────────────────────────────────────────────────────

async def main():
    keyword = "телефония срм"
    print(f"🔍 Ищем посты по запросу: '{keyword}'")
    
    posts = await search_threads(keyword, max_results=50)
    
    print(f"\n✅ Найдено {len(posts)} постов:\n")
    for i, post in enumerate(posts, 1):
        print(f"[{i}] {post.get('username')} | ❤️ {post.get('like_count', 0)}")
        print(f"     {post.get('text', '')[:100]}...")
        print(f"     🔗 {post.get('url')}")
        print()
    
    # Сохраняем в JSON
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print("💾 Результаты сохранены в results.json")


if __name__ == "__main__":
    import sys
    if "--save-cookies" in sys.argv:
        asyncio.run(save_cookies())
    else:
        asyncio.run(main())