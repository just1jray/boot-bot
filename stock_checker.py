#!/usr/bin/env python3
"""
Shopify Stock Checker
Monitors product availability on any Shopify store and sends
notifications when items come back in stock.

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


def resolve_variant(url, size=None):
    """Fetch product JSON and find the matching variant.

    Args:
        url: Shopify product URL (e.g. https://store.com/products/some-item)
        size: Optional size to match (e.g. "9", "M"). If None, uses first variant.

    Returns:
        dict with variant_id, variant_title, price, product_title, product_url

    Raises:
        ValueError: if size is specified but not found among variants
    """
    js_url = url.rstrip("/") + ".js"
    resp = requests.get(js_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    resp.raise_for_status()
    data = resp.json()

    variants = data.get("variants", [])
    if not variants:
        raise ValueError(f"No variants found for {url}")

    if size is None:
        variant = variants[0]
    else:
        variant = None
        available_sizes = []
        for v in variants:
            title = v.get("title", "")
            # Shopify titles: "9 / Black", "M / Blue", "Default Title"
            size_part = title.split(" / ")[0].strip()
            available_sizes.append(size_part)
            if size_part.lower() == size.lower():
                variant = v
                break

        if variant is None:
            raise ValueError(
                f"Size '{size}' not found for {data.get('title', url)}. "
                f"Available sizes: {', '.join(available_sizes)}"
            )

    return {
        "variant_id": variant["id"],
        "variant_title": variant.get("title", ""),
        "price": variant.get("price", 0) / 100,
        "product_title": data.get("title", ""),
        "product_url": url,
    }


def load_products(args):
    """Build list of product dicts from CLI args or config file.

    Returns:
        list of dicts, each with 'url' and optional 'size'
    """
    if args.config:
        with open(args.config) as f:
            products = json.load(f)
        if not isinstance(products, list) or not products:
            print("Error: Config file must contain a non-empty JSON array.")
            sys.exit(1)
        return products
    else:
        product = {"url": args.url}
        if args.size:
            product["size"] = args.size
        return [product]


def check_stock(product):
    """Check stock status for a resolved product's variant.

    Args:
        product: dict with at least 'url' and 'variant_id' keys

    Returns:
        dict with 'available', 'title', 'price', 'product_title'
    """
    js_url = product["url"].rstrip("/") + ".js"
    resp = requests.get(js_url, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    resp.raise_for_status()
    data = resp.json()

    for variant in data.get("variants", []):
        if variant["id"] == product["variant_id"]:
            return {
                "available": variant.get("available", False),
                "title": variant.get("title", ""),
                "price": variant.get("price", 0) / 100,
                "product_title": data.get("title", ""),
            }

    raise ValueError(
        f"Variant {product['variant_id']} no longer found for {product['product_title']}"
    )


def send_ntfy(title, message, priority="default", click_url=None):
    """Send a push notification via ntfy.sh."""
    topic = os.environ.get("NTFY_TOPIC", "shopify-stock-checker")
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": "shopping",
    }
    if click_url:
        headers["Click"] = click_url
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers=headers,
        timeout=10,
    )


def send_whatsapp(message):
    """Send a WhatsApp message via Twilio sandbox."""
    client = TwilioClient(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        body=message,
        from_="whatsapp:+14155238886",
        to=f"whatsapp:{os.environ['WHATSAPP_TO']}",
    )


def send_email(subject, body):
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
        channels.append("ntfy")
    if args.email:
        channels.append("Email")
    if args.whatsapp:
        channels.append("WhatsApp")
    return channels


def notify(subject, body, channels, priority="default", click_url=None):
    """Send notification via all enabled channels. Log errors but don't crash."""
    dispatch = {
        "ntfy": lambda: send_ntfy(subject, body, priority, click_url),
        "Email": lambda: send_email(subject, body),
        "WhatsApp": lambda: send_whatsapp(body),
    }
    for name in channels:
        try:
            dispatch[name]()
            print(f"    [{name}] sent")
        except Exception as e:
            print(f"    [{name}] FAILED: {e}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Shopify stock checker — monitor any product for restocks"
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Shopify product URL to monitor")
    source.add_argument("--config", help="JSON config file with multiple products")

    parser.add_argument("--size",
                        help="Variant size to watch (e.g. 9, M, XL). Omit for single-variant products.")
    parser.add_argument("--interval", type=int, default=60,
                        help="Check interval in seconds (default: 60)")
    parser.add_argument("--heartbeat", type=int, default=48,
                        help="Heartbeat interval in hours (default: 48)")
    parser.add_argument("--ntfy", action="store_true",
                        help="Enable ntfy.sh push notifications (set NTFY_TOPIC env var)")
    parser.add_argument("--email", action="store_true",
                        help="Enable email notifications (requires SMTP_USER, SMTP_PASSWORD, EMAIL_TO)")
    parser.add_argument("--whatsapp", action="store_true",
                        help="Enable WhatsApp via Twilio sandbox")

    args = parser.parse_args()

    if args.size and args.config:
        parser.error("--size cannot be used with --config (set size per-product in the config file)")

    return args


def format_label(product):
    """Short label for a resolved product: 'Product Name (Size X)' or 'Product Name'."""
    title = product["product_title"]
    vt = product["variant_title"]
    if vt and vt != "Default Title":
        return f"{title} ({vt})"
    return title


def main():
    args = parse_args()
    channels = build_channels(args)

    if not channels:
        print("Error: No notification channels enabled.")
        print("Use --ntfy, --email, and/or --whatsapp to enable channels.")
        print("Example: python stock_checker.py --url <url> --ntfy")
        sys.exit(1)

    # Load product specs from CLI or config
    product_specs = load_products(args)

    # Resolve variants for all products at startup (fail fast)
    print("Resolving products...")
    products = []
    for spec in product_specs:
        url = spec["url"]
        size = spec.get("size")
        try:
            resolved = resolve_variant(url, size)
            products.append(resolved)
            label = format_label(resolved)
            print(f"  OK: {label} — ${resolved['price']:.0f}")
        except (requests.RequestException, ValueError) as e:
            print(f"  FAILED: {url} (size={size}) — {e}")
            sys.exit(1)
    print()

    check_interval = args.interval
    heartbeat_hours = args.heartbeat

    # Initial stock check
    host = platform.node()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_lines = []
    for p in products:
        try:
            info = check_stock(p)
            status = "IN STOCK" if info["available"] else "sold out"
        except Exception as e:
            status = f"unknown ({e})"
        status_lines.append(f"  {format_label(p)}: {status}")

    product_summary = "\n".join(f"  - {format_label(p)}" for p in products)
    startup_msg = (
        f"Stock checker started on {host} at {started_at}\n"
        f"Monitoring {len(products)} product(s):\n{product_summary}\n"
        f"Check interval: {check_interval}s\n"
        f"Heartbeat: every {heartbeat_hours}h"
    )
    notify("Stock Checker Started", startup_msg, channels)

    print("=" * 60)
    print("  Shopify Stock Checker")
    print(f"  Host: {host}")
    print(f"  Monitoring {len(products)} product(s):")
    for line in status_lines:
        print(line)
    print(f"  Checking every {check_interval} seconds")
    print(f"  Heartbeat every {heartbeat_hours} hours")
    print(f"  Channels: {', '.join(channels)}")
    print("=" * 60)
    print()

    check_count = 0
    last_heartbeat = time.monotonic()

    while True:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        # Heartbeat
        elapsed_hours = (time.monotonic() - last_heartbeat) / 3600
        if elapsed_hours >= heartbeat_hours:
            heartbeat_msg = (
                f"Still watching {len(products)} product(s) — "
                f"{check_count} checks so far, nothing in stock."
            )
            notify("Stock Checker Heartbeat", heartbeat_msg, channels)
            last_heartbeat = time.monotonic()
            print(f"  [{now}] Heartbeat sent")

        found_stock = False
        for p in products:
            label = format_label(p)
            try:
                info = check_stock(p)
                available = info["available"]
                status = "IN STOCK" if available else "sold out"

                print(f"  [{now}] Check #{check_count}: {label} — {status}")

                if available:
                    found_stock = True
                    msg = (
                        f"{label} IN STOCK! "
                        f"${info['price']:.0f} — Buy now: {p['product_url']}"
                    )
                    print()
                    print("  " + "!" * 50)
                    print(f"  !!! {label} IS BACK IN STOCK !!!")
                    print("  " + "!" * 50)
                    print()
                    notify(
                        f"IN STOCK: {label}",
                        msg,
                        channels,
                        priority="urgent",
                        click_url=p["product_url"],
                    )

            except requests.RequestException as e:
                print(f"  [{now}] Check #{check_count}: {label} — Network error: {e}")
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                print(f"  [{now}] Check #{check_count}: {label} — Parse error: {e}")

        if found_stock:
            print("  Continuing to monitor in case it sells out and restocks...")
            print()
            time.sleep(300)
        else:
            time.sleep(check_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped monitoring. Good luck!")
        sys.exit(0)
