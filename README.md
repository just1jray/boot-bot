# boot-bot-hunter

Stock checker for [Hunter Boots Moon Lug Sole Snow Booties](https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01) (Size 9). Polls the Shopify product API every 60 seconds and sends a WhatsApp message via Twilio when back in stock.

## Prerequisites

- Python 3.9+
- A [Twilio account](https://www.twilio.com/try-twilio) (free trial works)
- WhatsApp on your phone

## Install

```bash
git clone git@github.com:just1jray/boot-bot-hunter.git
cd boot-bot-hunter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Twilio WhatsApp Setup

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio)
2. From the [Twilio Console](https://console.twilio.com/), copy your **Account SID** and **Auth Token**
3. Go to **Messaging > Try it out > Send a WhatsApp message** in the console
4. Follow the instructions to join the sandbox: send the provided code (e.g. "join <two-words>") from your WhatsApp to the Twilio sandbox number **+1 415 523 8886**
5. Once you receive a confirmation reply, your WhatsApp is connected

**Note:** The sandbox session expires after 72 hours of inactivity. If the checker stops delivering messages, re-send the join code from step 4 to reconnect.

## Configure

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WHATSAPP_TO=+12125556789
```

`WHATSAPP_TO` is your personal phone number (the one linked to your WhatsApp).

## Run

```bash
source venv/bin/activate
export $(cat .env | xargs)
python stock_checker.py
```

You'll receive a confirmation WhatsApp message on startup. The checker logs each poll to stdout:

```
  [14:32:01] Check #1: Size 9 is sold out
  [14:33:01] Check #2: Size 9 is sold out
```

When size 9 comes back in stock, you'll get a WhatsApp message with the buy link.

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
        <key>WHATSAPP_TO</key>
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
