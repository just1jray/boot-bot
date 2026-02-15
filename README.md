# boot-bot-hunter

Shopify stock checker. Monitors any product for restocks — boots with numeric sizes, clothing with letter sizes (S/M/L/XL), or single-variant products like bags and accessories. Polls the Shopify product API and sends notifications when items come back in stock.

## Usage

### Single product with a size

```bash
python stock_checker.py --url "https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01" --size 9 --ntfy
```

### Single product without a size (bags, accessories, one-size items)

```bash
python stock_checker.py --url "https://example.com/products/tote-bag" --ntfy --email
```

When `--size` is omitted, the checker monitors the first variant.

### Multiple products via config file

```bash
python stock_checker.py --config products.json --ntfy --email
```

See `products.json.example` for the format:

```json
[
  {
    "url": "https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01",
    "size": "9",
    "interval": 60
  },
  {
    "url": "https://shop-usa.palaceskateboards.com/products/2xfzwa123s9w",
    "size": "XL",
    "interval": 30
  },
  {
    "url": "https://example.com/products/tote-bag"
  }
]
```

Each product can have its own `interval` (in seconds). Products without an `interval` use the `--interval` default (60s).

### Custom intervals

```bash
python stock_checker.py --url <url> --size M --interval 30 --heartbeat 24 --ntfy
```

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | — | Shopify product URL (required unless `--config`) |
| `--config` | — | JSON config file with multiple products (required unless `--url`) |
| `--size` | — | Variant size to watch (e.g. `9`, `M`, `XL`). Omit for single-variant products |
| `--interval` | `60` | Default check interval in seconds (can be overridden per-product in config) |
| `--heartbeat` | `48` | Heartbeat interval in hours |

## Notification Channels

Enable any combination with CLI flags:

| Flag | Channel | Reliability | Required env vars |
|------|---------|------------|-------------------|
| `--ntfy` | ntfy.sh push | Always works | `NTFY_TOPIC` |
| `--email` | Email (SMTP) | Always works | `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` |
| `--whatsapp` | WhatsApp (Twilio) | Best-effort, 24h window | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `WHATSAPP_TO` |

All enabled channels fire on every notification. If one fails, the others still send.

## Install

```bash
git clone git@github.com:just1jray/boot-bot-hunter.git
cd boot-bot-hunter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Channel Setup

### ntfy (instant push notifications)

1. Install the **ntfy** app on your phone — [iOS](https://apps.apple.com/us/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. Open the app, tap **+**, subscribe to your topic (e.g. `shopify-stock-checker`)
3. Done — no account needed

To use a custom topic, set `NTFY_TOPIC` in your `.env`.

### Email (Gmail)

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords) (requires 2FA enabled)
2. Create an app password for "Mail"
3. Copy the 16-character password — **remove spaces** before adding to `.env`

For non-Gmail providers, set `SMTP_HOST` and `SMTP_PORT` accordingly.

### WhatsApp (optional)

WhatsApp via Twilio sandbox only delivers messages within 24 hours of your last WhatsApp message to the sandbox number. It's included as a bonus channel but **not reliable for long-running monitoring**.

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio)
2. From the [Twilio Console](https://console.twilio.com/), copy your **Account SID** and **Auth Token**
3. Go to **Messaging > Try it out > Send a WhatsApp message** in the console
4. Send the join code from your WhatsApp to **+1 415 523 8886**

## Configure

```bash
cp .env.example .env
```

Edit `.env` with values for the channels you plan to enable.

## Run

```bash
source venv/bin/activate
export $(cat .env | xargs)
python stock_checker.py --url <shopify-product-url> --size 9 --ntfy --email
```

Pick any combination of flags:

```bash
# Single product, ntfy only
python stock_checker.py --url <url> --size 9 --ntfy

# Multiple products from config
python stock_checker.py --config products.json --ntfy --email

# All channels
python stock_checker.py --url <url> --ntfy --email --whatsapp
```

## Run on a Headless Server

### Using nohup

```bash
source venv/bin/activate
export $(cat .env | xargs)
nohup python stock_checker.py --url <url> --size 9 --ntfy --email >> stock_check.log 2>&1 &
echo $! > checker.pid
```

Check logs: `tail -f stock_check.log`

Stop it: `kill $(cat checker.pid)`

### Using systemd (Linux / Raspberry Pi)

Create `/etc/systemd/system/boot-bot-hunter.service`:

```ini
[Unit]
Description=Shopify Stock Checker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/boot-bot-hunter
EnvironmentFile=/home/pi/boot-bot-hunter/.env
ExecStart=/home/pi/boot-bot-hunter/venv/bin/python stock_checker.py --config products.json --ntfy --email
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable boot-bot-hunter
sudo systemctl start boot-bot-hunter
```

View logs: `journalctl -u boot-bot-hunter -f`

### Using launchd (headless Mac)

Create `~/Library/LaunchAgents/com.bootbothunter.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bootbothunter</string>
    <key>WorkingDirectory</key>
    <string>/Users/YOU/boot-bot-hunter</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOU/boot-bot-hunter/venv/bin/python</string>
        <string>stock_checker.py</string>
        <string>--config</string>
        <string>products.json</string>
        <string>--ntfy</string>
        <string>--email</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NTFY_TOPIC</key>
        <string>shopify-stock-checker</string>
        <key>SMTP_HOST</key>
        <string>smtp.gmail.com</string>
        <key>SMTP_PORT</key>
        <string>587</string>
        <key>SMTP_USER</key>
        <string>you@gmail.com</string>
        <key>SMTP_PASSWORD</key>
        <string>abcdefghijklmnop</string>
        <key>EMAIL_TO</key>
        <string>you@gmail.com</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOU/boot-bot-hunter/stock_check.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOU/boot-bot-hunter/stock_check.log</string>
</dict>
</plist>
```

Replace `/Users/YOU/` with your actual home directory and fill in your credentials, then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.bootbothunter.plist
```

View logs: `tail -f ~/boot-bot-hunter/stock_check.log`

Stop it: `launchctl unload ~/Library/LaunchAgents/com.bootbothunter.plist`
