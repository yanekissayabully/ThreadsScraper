"""
AI-фильтрация постов через OpenAI.
Определяет: является ли пост реальным лидом для CRM-интегратора.
"""

from openai import AsyncOpenAI
import asyncio
from typing import Optional

client = AsyncOpenAI(api_key="YOUR_OPENAI_API_KEY")  # или через env

SYSTEM_PROMPT = """
Ты — аналитик лидов для компании, которая занимается:
- Внедрением и настройкой CRM-систем (amoCRM, Битрикс24)
- Интеграциями (WABA, WhatsApp, телефония, мессенджеры)
- Автоматизацией бизнес-процессов

Твоя задача: определить, является ли пост из Threads РЕАЛЬНЫМ ЛИДОМ.

РЕАЛЬНЫЙ ЛИД — это пост, где:
- Человек или компания ИЩЕТ подрядчика/интегратора CRM
- Задаёт вопрос про внедрение/настройку CRM
- Жалуется на проблему, которую мы можем решить
- Спрашивает рекомендации по CRM или интеграциям
- Пишет что хочет автоматизировать бизнес

НЕ ЛИД — это:
- Реклама чужих услуг / кто-то сам предлагает CRM-услуги
- Общие разговоры без запроса
- Новости и обзоры без конкретного запроса
- Посты конкурентов

Отвечай ТОЛЬКО в формате JSON:
{
  "is_lead": true/false,
  "score": 1-10,
  "reason": "краткое объяснение на русском (1-2 предложения)",
  "lead_type": "тип лида: поиск_подрядчика | вопрос_про_crm | проблема_автоматизации | не_лид"
}
"""

async def classify_post(post: dict) -> dict:
    """Классифицирует один пост через GPT."""
    text = post.get("text", "")[:800]  # обрезаем длинные посты

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # дёшево и быстро
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Пост от @{post.get('username')}:\n\n{text}"}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = response.choices[0].message.content
        import json
        classification = json.loads(result)

        return {
            **post,
            "ai_is_lead":   classification.get("is_lead", False),
            "ai_score":     classification.get("score", 0),
            "ai_reason":    classification.get("reason", ""),
            "ai_lead_type": classification.get("lead_type", "не_лид"),
        }

    except Exception as e:
        print(f"  ⚠️ Ошибка GPT для @{post.get('username')}: {e}")
        return {**post, "ai_is_lead": False, "ai_score": 0, "ai_reason": "ошибка", "ai_lead_type": "не_лид"}


async def filter_leads(posts: list, min_score: int = 6, concurrency: int = 5) -> tuple[list, list]:
    """
    Классифицирует все посты параллельно.
    Возвращает (лиды, не_лиды).
    concurrency — сколько запросов к GPT одновременно.
    """
    print(f"\n🤖 Запускаем AI-анализ {len(posts)} постов...")

    semaphore = asyncio.Semaphore(concurrency)

    async def classify_with_limit(post):
        async with semaphore:
            return await classify_post(post)

    classified = await asyncio.gather(*[classify_with_limit(p) for p in posts])

    leads     = [p for p in classified if p["ai_is_lead"] and p["ai_score"] >= min_score]
    non_leads = [p for p in classified if not p["ai_is_lead"] or p["ai_score"] < min_score]

    leads.sort(key=lambda p: p["ai_score"], reverse=True)

    print(f"  ✅ Лидов найдено: {len(leads)} из {len(posts)}")
    return leads, non_leads