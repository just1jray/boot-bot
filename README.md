# boot-bot-hunter

Stock checker for [Hunter Boots Moon Lug Sole Snow Booties](https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01) (Size 9). Polls the Shopify product API every 60 seconds and sends an SMS via Twilio when back in stock.

## Prerequisites

- Python 3.9+
- A [Twilio account](https://www.twilio.com/try-twilio) (free trial works)

## Install

```bash
git clone git@github.com:just1jray/boot-bot-hunter.git
cd boot-bot-hunter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Twilio Setup

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio) — the free trial includes $15+ in credit
2. From the [Twilio Console](https://console.twilio.com/), copy your **Account SID** and **Auth Token**
3. A phone number is assigned automatically — find it under **Phone Numbers > Manage > Active numbers**
4. On a trial account, verify your personal phone number under **Phone Numbers > Manage > Verified Caller IDs**

## Configure

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+12125551234
SMS_TO_NUMBER=+12125556789
```

## Run

```bash
source venv/bin/activate
export $(cat .env | xargs)
python stock_checker.py
```

You'll receive a confirmation SMS on startup. The checker logs each poll to stdout:

```
  [14:32:01] Check #1: Size 9 is sold out
  [14:33:01] Check #2: Size 9 is sold out
```

When size 9 comes back in stock, you'll get an SMS with the buy link.

## Run on a Headless Server

### Using nohup

```bash
source venv/bin/activate
export $(cat .env | xargs)
nohup python stock_checker.py >> stock_check.log 2>&1 &
echo $! > checker.pid
```

Check logs: `tail -f stock_check.log`

Stop it: `kill $(cat checker.pid)`

### Using systemd (Linux / Raspberry Pi)

Create `/etc/systemd/system/boot-bot-hunter.service`:

```ini
[Unit]
Description=Hunter Boots Stock Checker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/boot-bot-hunter
EnvironmentFile=/home/pi/boot-bot-hunter/.env
ExecStart=/home/pi/boot-bot-hunter/venv/bin/python stock_checker.py
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
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TWILIO_ACCOUNT_SID</key>
        <string>ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx</string>
        <key>TWILIO_AUTH_TOKEN</key>
        <string>xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx</string>
        <key>TWILIO_FROM_NUMBER</key>
        <string>+12125551234</string>
        <key>SMS_TO_NUMBER</key>
        <string>+12125556789</string>
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

Replace `/Users/YOU/` with your actual home directory and fill in the Twilio values, then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.bootbothunter.plist
```

View logs: `tail -f ~/boot-bot-hunter/stock_check.log`

Stop it: `launchctl unload ~/Library/LaunchAgents/com.bootbothunter.plist`
