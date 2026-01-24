#!/usr/bin/env python3
import imaplib
import email
import json
import os
import re
import urllib.request

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
IMAP_SERVER = "imap.gmail.com"
SENDER_EMAIL = "envios@loteriasyapuestas.es"


def connect_to_gmail(email_address, app_password):
    """Connect to Gmail via IMAP."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(email_address, app_password)
    return mail


def fetch_latest_lottery_email(mail):
    """Fetch the most recent email from the lottery sender."""
    mail.select("inbox")

    # Search for emails from the lottery sender
    status, messages = mail.search(None, f'FROM "{SENDER_EMAIL}"')
    if status != "OK" or not messages[0]:
        raise Exception(f"No emails found from {SENDER_EMAIL}")

    # Get the latest email
    email_ids = messages[0].split()
    latest_email_id = email_ids[-1]

    status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
    if status != "OK":
        raise Exception("Failed to fetch email")

    return email.message_from_bytes(msg_data[0][1])


def get_email_html(msg):
    """Extract HTML content from email."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset)
    else:
        if msg.get_content_type() == "text/html":
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset)

    raise Exception("No HTML content found in email")


def extract_ticket_data(html_content):
    """Extract all ticket data from the email HTML."""
    data = {
        "numbers": [],
        "stars": [],
        "millon_code": None,
        "millon_date": None,
        "draw_date": None,
        "price": None,
        "bet_count": "1",
        "balance": None,
        "reference": None,
    }

    # Extract balance
    balance_match = re.search(r'saldo actual es[:\s]*<[^>]*>\s*([\d,]+)\s*€', html_content, re.IGNORECASE)
    if balance_match:
        data["balance"] = balance_match.group(1) + "€"
    else:
        balance_match = re.search(r'saldo actual es[:\s]*([\d,]+)\s*€', html_content, re.IGNORECASE)
        if balance_match:
            data["balance"] = balance_match.group(1) + "€"

    # Extract numbers (5 main numbers) and stars (2)
    # They appear in td elements with width:30px and text-align:center
    # Use a flexible pattern that handles whitespace and newlines
    number_pattern = re.compile(
        r'<td[^>]*style="[^"]*width:\s*30px[^"]*"[^>]*>\s*(\d{2})\s*</td>',
        re.IGNORECASE | re.DOTALL
    )

    # Find position of "+" separator to distinguish numbers from stars
    plus_match = re.search(r'<td[^>]*>\s*\+\s*</td>', html_content, re.IGNORECASE | re.DOTALL)
    if plus_match:
        plus_pos = plus_match.start()
        before_plus = html_content[:plus_pos]
        after_plus = html_content[plus_pos:]

        numbers_before = number_pattern.findall(before_plus)
        numbers_after = number_pattern.findall(after_plus)

        data["numbers"] = numbers_before[-5:] if len(numbers_before) >= 5 else numbers_before
        data["stars"] = numbers_after[:2] if len(numbers_after) >= 2 else numbers_after

    # Fallback: try simpler pattern if no numbers found
    if not data["numbers"]:
        # Look for 2-digit numbers in td elements within the coupon area
        simple_pattern = re.compile(r'<td[^>]*>\s*(\d{2})\s*</td>', re.IGNORECASE | re.DOTALL)
        all_numbers = simple_pattern.findall(html_content)
        # Filter to likely lottery numbers (01-50 for numbers, 01-12 for stars)
        lottery_numbers = [n for n in all_numbers if 1 <= int(n) <= 50]
        if len(lottery_numbers) >= 7:
            data["numbers"] = lottery_numbers[:5]
            data["stars"] = lottery_numbers[5:7]

    # Extract El Millón code (pattern: 3 letters + 5 digits)
    millon_match = re.search(r'([A-Z]{3}\d{5})', html_content)
    if millon_match:
        data["millon_code"] = millon_match.group(1)

    # Extract El Millón date (pattern like "23 ENE 26" or "27 ENE 26 - 30 ENE 26")
    millon_date_match = re.search(
        r'game_millon_ticket\.gif.*?<p[^>]*>\s*(\d{1,2}\s+[A-Z]{3}\s+\d{2}(?:\s*-\s*\d{1,2}\s+[A-Z]{3}\s+\d{2})?)\s*</p>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    if millon_date_match:
        data["millon_date"] = millon_date_match.group(1)

    # Extract draw date (pattern like "23 ENE 2026" or "27 ENE 2026 - 30 ENE 2026")
    draw_date_match = re.search(
        r'(\d{1,2}\s+[A-Z]{3}\s+\d{4}(?:\s*-\s*\d{1,2}\s+[A-Z]{3}\s+\d{4})?)',
        html_content
    )
    if draw_date_match:
        data["draw_date"] = draw_date_match.group(1)

    # Extract price
    price_match = re.search(r'([\d,]+)\s*EUR', html_content)
    if price_match:
        data["price"] = price_match.group(1) + " EUR"

    # Extract bet count
    bet_match = re.search(r'(\d+)\s*apuesta', html_content, re.IGNORECASE)
    if bet_match:
        data["bet_count"] = bet_match.group(1)

    # Extract reference number
    ref_match = re.search(r'(\d{5}-\d{4}-\d{5}-\d{5}-\d{5}-\d{5}-\d{5})', html_content)
    if ref_match:
        data["reference"] = ref_match.group(1)

    return data


def format_ticket_message(data):
    """Format the ticket data as a Telegram message."""
    numbers_str = " - ".join(data["numbers"]) if data["numbers"] else "N/A"
    stars_str = " - ".join(data["stars"]) if data["stars"] else "N/A"

    # Check if it's a multi-draw ticket
    draw_date = data['draw_date'] or 'N/A'
    millon_date = data['millon_date'] or 'N/A'

    # Use "Sorteos" (plural) if it's a date range
    sorteo_label = "Sorteos" if " - " in draw_date else "Sorteo"

    lines = [
        "🎫 *EUROMILLONES - Resguardo*",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "📍 *Tu combinación:*",
        f"   Números: {numbers_str}",
        f"   Estrellas: {stars_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "🎰 *EL MILLÓN*",
        f"   Código: {data['millon_code'] or 'N/A'}",
        f"   Fecha: {millon_date}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📅 {sorteo_label}: {draw_date}",
        f"💶 Importe: {data['price'] or 'N/A'}",
        f"🎟️ Apuestas: {data['bet_count']}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 *Saldo disponible:* {data['balance'] or 'N/A'}",
        "",
        f"🔖 Ref: {data['reference'] or 'N/A'}",
    ]

    return "\n".join(lines)


def send_telegram_message(token, chat_id, message):
    """Send a message via Telegram Bot API."""
    url = TELEGRAM_API.format(token=token)
    data = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    })

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def main():
    # Get configuration from environment
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([telegram_token, chat_id, gmail_address, gmail_app_password]):
        print("Error: Missing required environment variables")
        print("Required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GMAIL_ADDRESS, GMAIL_APP_PASSWORD")
        exit(1)

    print("Connecting to Gmail...")
    mail = connect_to_gmail(gmail_address, gmail_app_password)

    print(f"Fetching latest email from {SENDER_EMAIL}...")
    msg = fetch_latest_lottery_email(mail)

    print("Extracting email content...")
    html_content = get_email_html(msg)

    # Extract ticket data
    print("Extracting ticket data...")
    ticket_data = extract_ticket_data(html_content)
    print(f"  Numbers: {ticket_data['numbers']}")
    print(f"  Stars: {ticket_data['stars']}")
    print(f"  El Millón code: {ticket_data['millon_code']}")
    print(f"  El Millón date: {ticket_data['millon_date']}")
    print(f"  Draw date: {ticket_data['draw_date']}")
    print(f"  Price: {ticket_data['price']}")
    print(f"  Balance: {ticket_data['balance']}")
    print(f"  Reference: {ticket_data['reference']}")

    # Format message
    message = format_ticket_message(ticket_data)

    print("\nSending to Telegram...")
    result = send_telegram_message(telegram_token, chat_id, message)

    if result.get("ok"):
        print("Message sent successfully!")
    else:
        print(f"Failed to send message: {result}")
        exit(1)

    mail.logout()


if __name__ == "__main__":
    main()
