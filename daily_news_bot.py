#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Щоденний збирач новин → Telegram (версія для GitHub Actions)
------------------------------------------------------------
Збирає останні новини з угорських медіа (через RSS) і надсилає їх
у ваш Telegram: заголовок + короткий опис + посилання.

Токен і chat_id беруться з "секретів" GitHub (змінних оточення),
а НЕ вписуються у файл.
"""

import os
import re
import html
import feedparser
import requests
from datetime import datetime

# ============ НАЛАШТУВАННЯ ============

# Підтягуються із секретів GitHub — вписувати сюди нічого не треба.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Сайти-джерела (RSS-стрічки).
SOURCES = {
    "Telex": "https://telex.hu/rss",
    "444.hu": "https://444.hu/feed",
    "HVG": "https://hvg.hu/rss",
    "Index": "https://index.hu/24ora/rss/",
    "Átlátszó": "https://atlatszo.hu/feed/",
    "Átlátszó (English)": "https://english.atlatszo.hu/feed/",
}

# Скільки новин брати з кожного сайту
NEWS_PER_SOURCE = 4

# Максимальна довжина короткого опису (символів)
SUMMARY_LENGTH = 220

# ======================================


def clean_text(raw: str) -> str:
    """Прибирає HTML-теги з тексту RSS і зайві пробіли."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)      # прибрати теги
    text = html.unescape(text)               # &amp; -> &
    text = re.sub(r"\s+", " ", text).strip()  # зайві пробіли
    return text


def shorten(text: str, limit: int) -> str:
    """Обрізає текст по межі слова і додає трикрапку."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def fetch_news(source_name: str, rss_url: str, limit: int) -> list:
    """Завантажує RSS-стрічку, повертає список новин з описами."""
    news = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:limit]:
            summary = clean_text(entry.get("summary", ""))
            news.append({
                "title": clean_text(entry.get("title", "Без заголовка")),
                "link": entry.get("link", ""),
                "summary": shorten(summary, SUMMARY_LENGTH),
            })
    except Exception as e:
        print(f"[!] Помилка при зборі з «{source_name}»: {e}")
    return news


def build_message() -> str:
    """Формує текст повідомлення з усіх джерел."""
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [f"🗞 <b>Новини за {today}</b>"]

    for source_name, rss_url in SOURCES.items():
        items = fetch_news(source_name, rss_url, NEWS_PER_SOURCE)
        lines.append(f"\n\n📌 <b>{html.escape(source_name)}</b>")
        if not items:
            lines.append("— не вдалося отримати новини")
            continue
        for item in items:
            title = html.escape(item["title"])
            link = html.escape(item["link"], quote=True)
            block = f'\n\n<a href="{link}"><b>{title}</b></a>'
            if item["summary"]:
                block += f'\n{html.escape(item["summary"])}'
            lines.append(block)

    return "".join(lines)


def send_to_telegram(text: str) -> None:
    """Надсилає повідомлення в Telegram, розбиваючи задовгі на частини."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    chunks = []
    while text:
        if len(text) <= 3800:
            chunks.append(text)
            break
        cut = text.rfind("\n\n", 0, 3800)   # ріжемо між новинами
        if cut == -1:
            cut = text.rfind("\n", 0, 3800)
        if cut == -1:
            cut = 3800
        chunks.append(text[:cut])
        text = text[cut:]

    for chunk in chunks:
        if not chunk.strip():
            continue
        resp = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        if resp.status_code != 200:
            print(f"[!] Telegram повернув помилку: {resp.text}")
        else:
            print("[✓] Частину повідомлення надіслано")


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[!] Не задано BOT_TOKEN або CHAT_ID. "
              "Перевірте секрети в налаштуваннях GitHub.")
        return

    print("Збираю новини...")
    message = build_message()
    print("Надсилаю в Telegram...")
    send_to_telegram(message)
    print("Готово!")


if __name__ == "__main__":
    main()
