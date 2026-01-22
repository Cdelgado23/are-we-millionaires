#!/usr/bin/env python3
import imaplib
import email
import json
import os
import re
import urllib.request
from email.header import decode_header

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendPhoto"
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


def extract_balance(html_content):
    """Extract the account balance from the email."""
    # Look for pattern like "tu saldo actual es: 17,50€" or similar
    match = re.search(r'saldo actual es[:\s]*<[^>]*>\s*([\d,]+)\s*€', html_content, re.IGNORECASE)
    if match:
        return match.group(1) + "€"

    # Alternative pattern
    match = re.search(r'saldo actual es[:\s]*([\d,]+)\s*€', html_content, re.IGNORECASE)
    if match:
        return match.group(1) + "€"

    return None


def extract_coupon_html(html_content):
    """Extract the coupon/ticket section from the email HTML."""
    # Find the coupon div by its id
    coupon_match = re.search(r'<div[^>]*id="[^"]*coupon[^"]*"[^>]*>(.*?)</div>\s*</td>', html_content, re.DOTALL | re.IGNORECASE)

    if not coupon_match:
        # Try alternative pattern - look for the table with the ticket
        coupon_match = re.search(
            r'(<td[^>]*background="[^"]*bg-resguardo\.png[^"]*"[^>]*>.*?</td>)',
            html_content,
            re.DOTALL | re.IGNORECASE
        )

    if not coupon_match:
        raise Exception("Could not find coupon section in email")

    coupon_html = coupon_match.group(1)

    # Wrap in a complete HTML document for rendering
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background-color: #ffffff;
                font-family: Verdana, Arial, Helvetica, sans-serif;
            }}
            table {{
                border-collapse: collapse;
            }}
            img {{
                max-width: 100%;
            }}
        </style>
    </head>
    <body>
        <table border="0" cellpadding="0" cellspacing="0" width="280">
            <tr>
                <td background="https://www.loteriasyapuestas.es/f/loterias/imagenes/mailing/bg-resguardo.png"
                    bgcolor="#fff" valign="top" width="280"
                    style="background-image: url('https://www.loteriasyapuestas.es/f/loterias/imagenes/mailing/bg-resguardo.png');
                           background-repeat: no-repeat;
                           background-size: cover;
                           padding: 10px;">
                    {coupon_html}
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Fix image URLs - replace Google proxy URLs with original URLs
    full_html = re.sub(
        r'https://ci3\.googleusercontent\.com/meips/[^#]+#([^"]+)',
        r'\1',
        full_html
    )

    return full_html


def render_html_to_image(html_content, output_path):
    """Render HTML to a PNG image using Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 350, "height": 800})

        page.set_content(html_content)
        page.wait_for_load_state("networkidle")

        # Get the actual content height
        content_height = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({"width": 350, "height": content_height + 40})

        page.screenshot(path=output_path, full_page=True)
        browser.close()


def send_telegram_photo(token, chat_id, image_path, caption):
    """Send a photo via Telegram Bot API."""
    url = TELEGRAM_API.format(token=token)

    # Read the image file
    with open(image_path, "rb") as f:
        image_data = f.read()

    # Create multipart form data
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
        f"Markdown\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="ticket.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8")

    body += image_data
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Mozilla/5.0"
        }
    )

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

    # Extract balance
    balance = extract_balance(html_content)
    print(f"Account balance: {balance}")

    # Extract and render coupon
    print("Extracting coupon section...")
    coupon_html = extract_coupon_html(html_content)

    print("Rendering ticket image...")
    image_path = "/tmp/ticket.png"
    render_html_to_image(coupon_html, image_path)

    # Build caption
    caption_lines = ["🎫 *Tu resguardo de Euromillones*"]
    if balance:
        caption_lines.append(f"\n💰 *Saldo disponible:* {balance}")
    caption_lines.append("\n¡Buena suerte en el sorteo!")
    caption = "\n".join(caption_lines)

    print("Sending to Telegram...")
    result = send_telegram_photo(telegram_token, chat_id, image_path, caption)

    if result.get("ok"):
        print("Photo sent successfully!")
    else:
        print(f"Failed to send photo: {result}")
        exit(1)

    mail.logout()


if __name__ == "__main__":
    main()
