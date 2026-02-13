#!/usr/bin/env python3
"""
Hunter Boots Stock Checker
Monitors size 9 availability for the Moon Lug Sole Snow Booties
and sends notifications when back in stock.

Enable channels with env vars or CLI flags:
  --ntfy       Enable ntfy.sh push notifications
  --email      Enable email via SMTP
  --whatsapp   Enable WhatsApp via Twilio sandbox
"""

import argparse
import json
import os
import platform
import smtplib
import sys
import time
from datetime import datetime
from email.message import EmailMessage

import requests
from twilio.rest import Client as TwilioClient

# --- Configuration (set via environment variables) ---
PRODUCT_URL = "https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01"
PRODUCT_JS_URL = f"{PRODUCT_URL}.js"
TARGET_VARIANT_ID = 51139451552036  # Size 9 / Black
TARGET_SIZE = "9"
CHECK_INTERVAL_SECONDS = 60
HEARTBEAT_INTERVAL_HOURS = 48


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


def send_ntfy(title: str, message: str, priority: str = "default"):
    """Send a push notification via ntfy.sh."""
    topic = os.environ.get("NTFY_TOPIC", "hunter-boots-size9-stock")
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": "boot",
            "Click": PRODUCT_URL,
        },
        timeout=10,
    )


def send_whatsapp(message: str):
    """Send a WhatsApp message via Twilio sandbox."""
    client = TwilioClient(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        body=message,
        from_="whatsapp:+14155238886",
        to=f"whatsapp:{os.environ['WHATSAPP_TO']}",
    )


def send_email(subject: str, body: str):
    """Send an email via SMTP."""
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["EMAIL_TO"]
    msg["Subject"] = subject
    msg.set_content(body)

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)


def build_channels(args):
    """Build list of enabled notification channels."""
    channels = []
    if args.ntfy:
        channels.append(("ntfy", None))
    if args.email:
        channels.append(("Email", None))
    if args.whatsapp:
        channels.append(("WhatsApp", None))
    return channels


def notify(subject: str, body: str, enabled_channels: list, priority: str = "default"):
    """Send notification via all enabled channels. Log errors but don't crash."""
    dispatch = {
        "ntfy": lambda: send_ntfy(subject, body, priority),
        "Email": lambda: send_email(subject, body),
        "WhatsApp": lambda: send_whatsapp(body),
    }
    for name, _ in enabled_channels:
        try:
            dispatch[name]()
            print(f"    [{name}] sent")
        except Exception as e:
            print(f"    [{name}] FAILED: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Hunter Boots stock checker")
    parser.add_argument("--ntfy", action="store_true",
                        help="Enable ntfy.sh push notifications (set NTFY_TOPIC env var, default: hunter-boots-size9-stock)")
    parser.add_argument("--email", action="store_true",
                        help="Enable email notifications (requires SMTP_USER, SMTP_PASSWORD, EMAIL_TO env vars)")
    parser.add_argument("--whatsapp", action="store_true",
                        help="Enable WhatsApp via Twilio sandbox (requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_TO env vars)")
    return parser.parse_args()


def main():
    args = parse_args()
    channels = build_channels(args)

    if not channels:
        print("  Error: No notification channels enabled.")
        print("  Use --ntfy, --email, and/or --whatsapp to enable channels.")
        print("  Example: python stock_checker.py --ntfy --email")
        sys.exit(1)

    channel_names = [name for name, _ in channels]

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
    notify("Stock Checker Started", startup_msg, channels)

    print("=" * 60)
    print("  Hunter Boots Stock Checker")
    print(f"  Host: {host}")
    print(f"  Product: Moon Lug Sole Snow Booties (Size {TARGET_SIZE})")
    print(f"  Initial status: {initial_status}")
    print(f"  Checking every {CHECK_INTERVAL_SECONDS} seconds")
    print(f"  Heartbeat every {HEARTBEAT_INTERVAL_HOURS} hours")
    print(f"  Channels: {', '.join(channel_names)}")
    print("=" * 60)
    print()

    check_count = 0
    last_heartbeat = time.monotonic()

    while True:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        # Send heartbeat to keep channels alive
        elapsed_hours = (time.monotonic() - last_heartbeat) / 3600
        if elapsed_hours >= HEARTBEAT_INTERVAL_HOURS:
            heartbeat_msg = f"Still watching size {TARGET_SIZE} — {check_count} checks so far, still sold out."
            notify("Stock Checker Heartbeat", heartbeat_msg, channels)
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

                notify("HUNTER BOOTS IN STOCK!", msg, channels, priority="urgent")
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
