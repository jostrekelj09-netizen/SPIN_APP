# SPIN Alert Bot

A lightweight Python bot that monitors the Slovenian SPIN emergency notifications feed (SOS 112) and automatically forwards new alerts to Telegram groups.

Built to run unattended on a Raspberry Pi.

> **Disclaimer:** This is an unofficial hobby project and is not affiliated with SOS 112 or the Administration for Civil Protection and Disaster Relief. Do not rely on it as a replacement for official emergency channels.

## Features

- Forwards new SPIN notifications to Telegram as formatted messages with a link to the original.
- Supports **multiple feeds and groups** with a single bot token.
- Remembers the last sent alert per feed (no duplicates after restarts).
- Handles Telegram rate limits (HTTP 429) with automatic retry.
- Built-in safeguards:
  - On first run, sends only the single latest alert.
  - If the stored ID is no longer in the feed, sends only the latest alert.
  - Sends at most 3 alerts per run.
- One failing feed never stops the others.
- Optional `--boot` flag sends a startup message to all groups.

## Requirements

- Python 3.8+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- The bot added to your Telegram group(s) with permission to send messages

```bash
pip install feedparser requests
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/spin-alert-bot.git
cd spin-alert-bot
```

### 2. Get a bot token

Create a bot with [@BotFather](https://t.me/BotFather) using `/newbot` and copy the token.

### 3. Get the group chat ID

1. Add your bot to the group.
2. Send a command in the group, for example `/test`.
3. Open this URL in your browser (replace `TOKEN` with your token):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
4. Find `"chat":{"id":-100...}` in the response. Group IDs are negative and usually start with `-100`.

### 4. Configure

Configuration is read from environment variables. Anything you leave unset falls back to the `VNESI_...` placeholder in `main.py`.

| Variable | Description |
| --- | --- |
| `TELEGRAM_TOKEN` | Bot token (shared by all groups) |
| `RSS_URL_1` | SPIN feed URL for group 1 (default: the public SPIN feed) |
| `TELEGRAM_CHAT_ID_1` | Chat ID of group 1 |
| `RSS_URL_2` | SPIN feed URL for group 2 |
| `TELEGRAM_CHAT_ID_2` | Chat ID of group 2 |

Example:

```bash
export TELEGRAM_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID_1="-100xxxxxxxxxx"
export RSS_URL_2="https://example.com/feed"
export TELEGRAM_CHAT_ID_2="-100yyyyyyyyyy"
```

A feed is skipped while any of its values still contains `VNESI_`, so you can run with just one group configured. If the token is missing, the script exits.

To add more groups, add another entry to the `VIRI` list in `main.py` with its own `datoteka_id` file.

## Usage

Run a single check:

```bash
python3 main.py
```

Run a check and send a startup message to all configured groups:

```bash
python3 main.py --boot
```

The script performs one check per run, so schedule it to run periodically.

### Running on a Raspberry Pi (cron)

```bash
crontab -e
```

```cron
# check every 5 minutes
*/5 * * * * cd /home/pi/spin-alert-bot && /usr/bin/python3 main.py >> bot.log 2>&1

# startup message after reboot
@reboot sleep 30 && cd /home/pi/spin-alert-bot && /usr/bin/python3 main.py --boot >> bot.log 2>&1
```

If you keep the token in environment variables, define them at the top of the crontab or in a small wrapper script.

## How it works

1. Downloads the SPIN feed and parses it with `feedparser`.
2. Compares the newest entry ID with the one stored in `last_id.txt` (`last_id_2.txt` for the second feed).
3. Collects entries newer than the stored one, sends them oldest-first to Telegram, and updates the stored ID after each successful send.

## Security

- **Never commit your bot token.** Keep it in an environment variable or an untracked file.
- If a token is ever exposed, revoke it immediately via @BotFather (`/revoke`) and use the new one.
- Add a `.gitignore`:

```gitignore
last_id*.txt
.env
bot.log
__pycache__/
```

## Project structure

```
.
├── main.py          # the bot
├── last_id.txt      # generated: last sent alert for feed 1
├── last_id_2.txt    # generated: last sent alert for feed 2
└── README.md
```

## License

Choose a license (for example [MIT](https://choosealicense.com/licenses/mit/)) and add a `LICENSE` file.
