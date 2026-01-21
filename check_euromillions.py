#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime

EUROMILLIONS_API = "https://euromillions.api.pedromealha.dev/v1/draws"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def fetch_latest_draw():
    """Fetch the most recent Euromillions draw from the API."""
    req = urllib.request.Request(EUROMILLIONS_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        draws = json.loads(response.read().decode())

    # Sort by date descending and get the latest
    draws_sorted = sorted(draws, key=lambda x: x["date"], reverse=True)
    return draws_sorted[0]


def calculate_matches(my_numbers, my_stars, winning_numbers, winning_stars):
    """Calculate how many numbers and stars match."""
    my_numbers_set = set(my_numbers)
    my_stars_set = set(my_stars)
    winning_numbers_set = set(winning_numbers)
    winning_stars_set = set(winning_stars)

    matched_numbers = len(my_numbers_set & winning_numbers_set)
    matched_stars = len(my_stars_set & winning_stars_set)

    return matched_numbers, matched_stars


def find_prize(prizes, matched_numbers, matched_stars):
    """Find the prize amount for the given matches."""
    for prize in prizes:
        if prize["matched_numbers"] == matched_numbers and prize["matched_stars"] == matched_stars:
            return prize["prize"], prize["winners"]
    return 0, 0


def format_message(draw, my_numbers, my_stars, matched_numbers, matched_stars, prize_amount, winners):
    """Format the Telegram message."""
    winning_numbers = draw["numbers"]
    winning_stars = draw["stars"]
    draw_date = draw["date"]
    has_jackpot_winner = draw.get("has_winner", False)

    # Create visual representation of matches
    my_nums_display = []
    for num in my_numbers:
        if num in winning_numbers:
            my_nums_display.append(f"[{num}]")  # Matched
        else:
            my_nums_display.append(num)

    my_stars_display = []
    for star in my_stars:
        if star in winning_stars:
            my_stars_display.append(f"[{star}]")  # Matched
        else:
            my_stars_display.append(star)

    # Build message
    lines = [
        f"🎰 *Euromillions Result - {draw_date}*",
        "",
        f"🏆 *Winning combination:*",
        f"   Numbers: {' - '.join(winning_numbers)}",
        f"   Stars: {' - '.join(winning_stars)}",
        "",
        f"🎫 *Your combination:*",
        f"   Numbers: {' - '.join(my_nums_display)}",
        f"   Stars: {' - '.join(my_stars_display)}",
        "",
        f"📊 *Results:*",
        f"   Matched numbers: {matched_numbers}/5",
        f"   Matched stars: {matched_stars}/2",
    ]

    if prize_amount > 0:
        lines.extend([
            "",
            f"💰 *YOU WON!*",
            f"   Prize: €{prize_amount:,.2f}",
            f"   Winners in this category: {winners}",
        ])
    else:
        lines.extend([
            "",
            "😢 No prize this time loosers, you are still poor",
        ])

    if matched_numbers == 5 and matched_stars == 2:
        lines.extend([
            "",
            "🎉🎉🎉 *JACKPOT!!! YOU ARE A MILLIONAIRE!!!* 🎉🎉🎉",
        ])

    if has_jackpot_winner:
        lines.append(f"\nℹ️ This draw had a jackpot winner!")

    lines.extend(["official results: https://www.loteriasyapuestas.es/es/resultados"])
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
    my_numbers_str = os.environ.get("MY_NUMBERS", "")
    my_stars_str = os.environ.get("MY_STARS", "")

    if not all([telegram_token, chat_id, my_numbers_str, my_stars_str]):
        print("Error: Missing required environment variables")
        print("Required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MY_NUMBERS, MY_STARS")
        exit(1)

    # Parse numbers (handle both "1,2,3" and "01,02,03" formats)
    my_numbers = [str(int(n.strip())) for n in my_numbers_str.split(",")]
    my_stars = [str(int(s.strip())) for s in my_stars_str.split(",")]

    if len(my_numbers) != 5:
        print(f"Error: Expected 5 numbers, got {len(my_numbers)}")
        exit(1)
    if len(my_stars) != 2:
        print(f"Error: Expected 2 stars, got {len(my_stars)}")
        exit(1)

    print(f"Checking Euromillions results...")
    print(f"Your numbers: {my_numbers}")
    print(f"Your stars: {my_stars}")

    # Fetch latest draw
    draw = fetch_latest_draw()
    print(f"Latest draw date: {draw['date']}")
    print(f"Winning numbers: {draw['numbers']}")
    print(f"Winning stars: {draw['stars']}")

    # Calculate matches
    matched_numbers, matched_stars = calculate_matches(
        my_numbers, my_stars,
        draw["numbers"], draw["stars"]
    )
    print(f"Matched: {matched_numbers} numbers, {matched_stars} stars")

    # Find prize
    prize_amount, winners = find_prize(draw.get("prizes", []), matched_numbers, matched_stars)
    print(f"Prize: €{prize_amount:,.2f} ({winners} winners)")

    # Format and send message
    message = format_message(
        draw, my_numbers, my_stars,
        matched_numbers, matched_stars,
        prize_amount, winners
    )

    print("\nSending Telegram message...")
    result = send_telegram_message(telegram_token, chat_id, message)

    if result.get("ok"):
        print("Message sent successfully!")
    else:
        print(f"Failed to send message: {result}")
        exit(1)


if __name__ == "__main__":
    main()
