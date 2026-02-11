#!/usr/bin/env python3
"""
Hunter Boots Stock Checker
Monitors size 9 availability for the Moon Lug Sole Snow Booties
and sends a WhatsApp message via Twilio when back in stock.
"""

import json
import os
import sys
import time
from datetime import datetime

import requests
from twilio.rest import Client as TwilioClient

# --- Configuration (set via environment variables) ---
PRODUCT_URL = "https://hunterboots.com/products/womens-moon-lug-sole-insulated-waterproof-snow-booties-in-black-w-moon-blk01"
PRODUCT_JS_URL = f"{PRODUCT_URL}.js"
TARGET_VARIANT_ID = 51139451552036  # Size 9 / Black
TARGET_SIZE = "9"
CHECK_INTERVAL_SECONDS = 60

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
WHATSAPP_TO = os.environ["WHATSAPP_TO"]  # Your number, e.g. +12125556789


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


def send_whatsapp(message: str):
    """Send a WhatsApp message via Twilio sandbox."""
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_="whatsapp:+14155238886",  # Twilio sandbox number
        to=f"whatsapp:{WHATSAPP_TO}",
    )


def main():
    # Validate Twilio credentials on startup
    send_whatsapp(f"Hunter Boots stock checker started. Monitoring size {TARGET_SIZE} every {CHECK_INTERVAL_SECONDS}s.")

    print("=" * 60)
    print("  Hunter Boots Stock Checker")
    print(f"  Product: Moon Lug Sole Snow Booties (Size {TARGET_SIZE})")
    print(f"  Checking every {CHECK_INTERVAL_SECONDS} seconds")
    print(f"  WhatsApp notifications to: {WHATSAPP_TO}")
    print("=" * 60)
    print()
    print("  Startup WhatsApp message sent successfully.")
    print()

    check_count = 0

    while True:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")

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

                send_whatsapp(msg)
                print("  WhatsApp message sent!")
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
