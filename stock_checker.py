#!/usr/bin/env python3
"""
Hunter Boots Stock Checker
Monitors size 9 availability for the Moon Lug Sole Snow Booties
and sends WhatsApp + email notifications when back in stock.
"""

import json
import os
import platform
import smtplib
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests
from twilio.rest import Client as TwilioClient

# --- Configuration (set via environment variables) ---
PRODUCT_URL = "https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01"
PRODUCT_JS_URL = f"{PRODUCT_URL}.js"
TARGET_VARIANT_ID = 51139451552036  # Size 9 / Black
TARGET_SIZE = "9"
CHECK_INTERVAL_SECONDS = 60
HEARTBEAT_INTERVAL_HOURS = 48

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
WHATSAPP_TO = os.environ["WHATSAPP_TO"]  # Your number, e.g. +12125556789

# Email credentials
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

# Path to cache the Twilio Content Template SID
CONTENT_SID_FILE = Path(__file__).parent / ".content_sid"


def check_stock() -> dict:
    """Check stock status for size 9 variant."""
    resp = requests.get(PRODUCT_JS_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    resp.raise_for_status()
    data = resp.json()

    for variant in data.get("variants", []):
        if variant["id"] == TARGET_VARIANT_ID:
            return {
                "available": variant.get("available", False),
                "title": variant.get("title", ""),
                "price": variant.get("price", 0) / 100,
                "product_title": data.get("title", ""),
            }

    raise ValueError(f"Variant {TARGET_VARIANT_ID} (size {TARGET_SIZE}) not found")


def get_or_create_content_template() -> str:
    """Get or create a Twilio Content Template for WhatsApp.

    WhatsApp requires template messages outside the 24-hour session window.
    This creates a simple template with one variable and caches the SID locally.
    """
    if CONTENT_SID_FILE.exists():
        sid = CONTENT_SID_FILE.read_text().strip()
        if sid:
            return sid

    resp = requests.post(
        "https://content.twilio.com/v1/Content",
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        json={
            "friendly_name": "boot_bot_hunter_alert",
            "language": "en",
            "variables": {"1": "message text"},
            "types": {
                "twilio/text": {
                    "body": "{{1}}"
                }
            }
        }
    )
    resp.raise_for_status()
    sid = resp.json()["sid"]
    CONTENT_SID_FILE.write_text(sid)
    return sid


def send_whatsapp(message: str, content_sid: str):
    """Send a WhatsApp message via Twilio using a Content Template."""
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        content_sid=content_sid,
        content_variables=json.dumps({"1": message}),
        from_="whatsapp:+14155238886",  # Twilio sandbox number
        to=f"whatsapp:{WHATSAPP_TO}",
    )


def send_email(subject: str, body: str):
    """Send an email via SMTP."""
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def notify(subject: str, body: str, content_sid: str):
    """Send notification via both WhatsApp and email. Log errors but don't crash."""
    for name, fn in [("WhatsApp", lambda: send_whatsapp(body, content_sid)),
                     ("Email", lambda: send_email(subject, body))]:
        try:
            fn()
            print(f"    [{name}] sent")
        except Exception as e:
            print(f"    [{name}] FAILED: {e}")


def main():
    # Set up WhatsApp content template
    print("  Setting up WhatsApp content template...")
    content_sid = get_or_create_content_template()
    print(f"  Content template SID: {content_sid}")

    # Run initial stock check and send startup message
    host = platform.node()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        info = check_stock()
        initial_status = "IN STOCK" if info["available"] else "sold out"
    except Exception as e:
        initial_status = f"unknown ({e})"

    startup_msg = (
        f"Stock checker started on {host} at {started_at}\n"
        f"Product: Moon Lug Sole Snow Booties\n"
        f"Size: {TARGET_SIZE}\n"
        f"Current status: {initial_status}\n"
        f"Check interval: {CHECK_INTERVAL_SECONDS}s\n"
        f"Heartbeat: every {HEARTBEAT_INTERVAL_HOURS}h"
    )
    notify("Stock Checker Started", startup_msg, content_sid)

    print("=" * 60)
    print("  Hunter Boots Stock Checker")
    print(f"  Host: {host}")
    print(f"  Product: Moon Lug Sole Snow Booties (Size {TARGET_SIZE})")
    print(f"  Initial status: {initial_status}")
    print(f"  Checking every {CHECK_INTERVAL_SECONDS} seconds")
    print(f"  Heartbeat every {HEARTBEAT_INTERVAL_HOURS} hours")
    print(f"  WhatsApp: {WHATSAPP_TO}")
    print(f"  Email: {EMAIL_TO}")
    print("=" * 60)
    print()

    check_count = 0
    last_heartbeat = time.monotonic()

    while True:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        # Send heartbeat every 48 hours to keep Twilio sandbox alive
        elapsed_hours = (time.monotonic() - last_heartbeat) / 3600
        if elapsed_hours >= HEARTBEAT_INTERVAL_HOURS:
            heartbeat_msg = f"Still watching size {TARGET_SIZE} — {check_count} checks so far, still sold out."
            notify("Stock Checker Heartbeat", heartbeat_msg, content_sid)
            last_heartbeat = time.monotonic()
            print(f"  [{now}] Heartbeat sent")

        try:
            info = check_stock()
            available = info["available"]
            status = "IN STOCK" if available else "sold out"

            print(f"  [{now}] Check #{check_count}: Size {TARGET_SIZE} is {status}")

            if available:
                msg = (
                    f"Size {TARGET_SIZE} Hunter Boots IN STOCK! "
                    f"${info['price']:.0f} - Buy now: {PRODUCT_URL}"
                )

                print()
                print("  " + "!" * 50)
                print(f"  !!! SIZE {TARGET_SIZE} IS BACK IN STOCK !!!")
                print("  " + "!" * 50)
                print()

                notify("HUNTER BOOTS IN STOCK!", msg, content_sid)
                print("  Continuing to monitor in case it sells out and restocks...")
                print()

                # Wait 5 minutes after finding stock to avoid spamming
                time.sleep(300)
                continue

        except requests.RequestException as e:
            print(f"  [{now}] Check #{check_count}: Network error - {e}")
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"  [{now}] Check #{check_count}: Parse error - {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped monitoring. Good luck!")
        sys.exit(0)
