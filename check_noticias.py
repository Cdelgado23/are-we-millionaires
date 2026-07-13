#!/usr/bin/env python3
"""Check the Profex oposiciones news page and notify Telegram about new news."""
import html
import json
import os
import re
import urllib.request

NEWS_URL = "https://profex.educarex.es/oposiciones/noticias"
BASE_URL = "https://profex.educarex.es"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
STATE_FILE = "noticias_state.json"

ITEM_RE = re.compile(
    r'<li class="\s*d-table">'
    r'.*?<span class="fecha[^"]*">(?P<fecha>.*?)</span>'
    r'.*?<a href="(?P<href>[^"]*)"[^>]*>'
    r'.*?<div class="categoria-noticia">(?P<categoria>.*?)</div>'
    r'.*?<div class="titular-noticia">(?P<titular>.*?)</div>',
    re.DOTALL,
)


def clean(text):
    """Collapse whitespace and unescape HTML entities."""
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def fetch_news():
    """Fetch the news page and return the list of items (most recent first)."""
    req = urllib.request.Request(NEWS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    items = []
    for m in ITEM_RE.finditer(page):
        items.append({
            "fecha": clean(m.group("fecha")),
            "categoria": clean(m.group("categoria")),
            "titular": clean(m.group("titular")),
            "href": clean(m.group("href")),
        })
    return items


def item_key(item):
    """Stable identity for a news item (date + title)."""
    return f"{item['fecha']}||{item['titular']}"


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, encoding="utf-8") as f:
        return set(json.load(f))


def save_state(items):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump([item_key(i) for i in items], f, ensure_ascii=False, indent=2)


def format_message(item):
    href = item["href"]
    link = href if href.startswith("http") else BASE_URL + href
    return "\n".join([
        "📰 *Nueva noticia - Oposiciones*",
        "",
        f"📅 {item['fecha']}",
        f"🏷️ {item['categoria']}",
        "",
        item["titular"],
        "",
        f"🔗 {link}",
    ])


def send_telegram_message(token, chat_id, message):
    url = TELEGRAM_API.format(token=token)
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("NOTICIAS_TELEGRAM_CHAT_ID")

    if not all([token, chat_id]):
        print("Error: Missing required environment variables")
        print("Required: TELEGRAM_BOT_TOKEN, NOTICIAS_TELEGRAM_CHAT_ID")
        exit(1)

    items = fetch_news()
    print(f"Fetched {len(items)} news items")
    if not items:
        print("Error: no news items parsed - page layout may have changed")
        exit(1)

    known = load_state()

    if known is None:
        # First run: establish baseline, don't spam the group with history.
        save_state(items)
        print("No previous state found. Baseline saved, no notifications sent.")
        return

    new_items = [i for i in items if item_key(i) not in known]
    print(f"Found {len(new_items)} new news items")

    # Notify oldest-first so messages arrive in chronological order.
    for item in reversed(new_items):
        print(f"Notifying: {item['fecha']} - {item['titular']}")
        result = send_telegram_message(token, chat_id, format_message(item))
        if not result.get("ok"):
            print(f"Failed to send message: {result}")
            exit(1)

    save_state(items)
    print("State updated.")


if __name__ == "__main__":
    main()
