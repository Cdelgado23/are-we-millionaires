# Are We Millionaires?

A Euromillions lottery checker that automatically verifies your numbers against draw results and sends notifications via Telegram.

## Features

- **Results Checker**: Fetches latest Euromillions draw results and compares them against your numbers
- **Ticket Extractor**: Parses lottery receipt emails from Gmail to extract ticket details
- **Telegram Notifications**: Sends formatted messages with results, matched numbers, and prize information
- **Automated Scheduling**: Runs via GitHub Actions on draw days

## Setup

### Prerequisites

- Python 3.12+
- Telegram Bot (create via [BotFather](https://t.me/botfather))
- Gmail account with [App Password](https://support.google.com/accounts/answer/185833) enabled

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Chat ID to send notifications to |
| `MY_NUMBERS` | Your 5 Euromillions numbers (comma-separated) |
| `MY_STARS` | Your 2 star numbers (comma-separated) |
| `GMAIL_ADDRESS` | Gmail address for ticket extraction |
| `GMAIL_APP_PASSWORD` | Gmail app password |

### Running Locally

```bash
# Check lottery results
python check_euromillions.py

# Extract ticket from email
python send_ticket_image.py
```

### GitHub Actions

The workflows run automatically:
- **Check Results**: Tuesdays and Fridays at 21:00 UTC
- **Send Ticket**: Wednesdays and Saturdays at 12:00 UTC

Configure the environment variables as repository secrets to enable automated runs.

## Project Structure

```
├── check_euromillions.py      # Lottery results checker
├── send_ticket_image.py       # Email ticket extractor
└── .github/workflows/
    ├── check-euromillions.yml # Results check schedule
    └── send-ticket.yml        # Ticket extraction schedule
```
