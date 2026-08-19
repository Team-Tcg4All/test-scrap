import csv
import os
from pathlib import Path

import requests


CURRENT = Path("yugioh_cards.csv")
PREVIOUS = Path("previous_cards.csv")

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")


# ============================================================
# SETTINGS
# ============================================================

# Notify for ANY price decrease.
NOTIFY_PRICE_DROPS = True

# Notify when something goes from zero stock to available.
NOTIFY_BACK_IN_STOCK = True

# Notify when something goes from available to zero.
NOTIFY_OUT_OF_STOCK = True


# ============================================================
# CSV
# ============================================================

def load_csv(path):

    if not path.exists():
        return {}

    products = {}

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            name = row.get("card", "").strip()

            if not name:
                continue

            image = row.get("image", "").strip()

            key = (
                name.lower(),
                image,
            )

            products[key] = row

    return products


def price(value):

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def stock(value):

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return 0


# ============================================================
# DISCORD
# ============================================================

def send_discord(embed):

    if not DISCORD_WEBHOOK:

        print(
            "DISCORD_WEBHOOK is not configured. "
            "Skipping Discord notification."
        )

        return

    response = requests.post(
        DISCORD_WEBHOOK,
        json={
            "embeds": [embed]
        },
        timeout=30,
    )

    response.raise_for_status()


def price_drop_embed(
    name,
    old_price,
    new_price,
    current_stock,
    image,
):

    difference = old_price - new_price

    percentage = (
        difference / old_price * 100
        if old_price > 0
        else 0
    )

    embed = {
        "title": "📉 Yu-Gi-Oh Price Drop",
        "description": f"**{name}**",
        "color": 0x2ECC71,
        "fields": [
            {
                "name": "Previous price",
                "value": f"${old_price:,.2f}",
                "inline": True,
            },
            {
                "name": "New price",
                "value": f"${new_price:,.2f}",
                "inline": True,
            },
            {
                "name": "Drop",
                "value": (
                    f"${difference:,.2f} "
                    f"({percentage:.2f}%)"
                ),
                "inline": False,
            },
            {
                "name": "Stock",
                "value": str(current_stock),
                "inline": True,
            },
        ],
    }

    if image:

        embed["thumbnail"] = {
            "url": image
        }

    return embed


def back_in_stock_embed(
    name,
    current_price,
    current_stock,
    image,
):

    embed = {
        "title": "🟢 Yu-Gi-Oh Card Back In Stock",
        "description": f"**{name}**",
        "color": 0x3498DB,
        "fields": [
            {
                "name": "Price",
                "value": f"${current_price:,.2f}",
                "inline": True,
            },
            {
                "name": "Stock",
                "value": str(current_stock),
                "inline": True,
            },
        ],
    }

    if image:

        embed["thumbnail"] = {
            "url": image
        }

    return embed


def out_of_stock_embed(
    name,
    current_price,
    image,
):

    embed = {
        "title": "🔴 Yu-Gi-Oh Card Out Of Stock",
        "description": f"**{name}**",
        "color": 0xE74C3C,
        "fields": [
            {
                "name": "Price",
                "value": f"${current_price:,.2f}",
                "inline": True,
            },
            {
                "name": "Stock",
                "value": "0",
                "inline": True,
            },
        ],
    }

    if image:

        embed["thumbnail"] = {
            "url": image
        }

    return embed


# ============================================================
# COMPARISON
# ============================================================

def compare():

    current = load_csv(CURRENT)
    previous = load_csv(PREVIOUS)

    if not previous:

        print(
            "No previous data found."
        )

        print(
            "This is probably the first run."
        )

        print(
            "No notifications will be sent."
        )

        return

    price_drops = 0
    back_in_stock = 0
    out_of_stock = 0

    for key, new_product in current.items():

        old_product = previous.get(key)

        if not old_product:
            continue

        name = new_product.get(
            "card",
            "Unknown",
        )

        image = new_product.get(
            "image",
            "",
        )

        old_price = price(
            old_product.get("price")
        )

        new_price = price(
            new_product.get("price")
        )

        old_stock = stock(
            old_product.get("stock")
        )

        new_stock = stock(
            new_product.get("stock")
        )

        # ----------------------------------------------------
        # ANY PRICE DROP
        # ----------------------------------------------------

        if (
            NOTIFY_PRICE_DROPS
            and old_price is not None
            and new_price is not None
            and new_price < old_price
        ):

            print(
                f"PRICE DROP: {name} | "
                f"{old_price} -> {new_price}"
            )

            try:

                send_discord(
                    price_drop_embed(
                        name,
                        old_price,
                        new_price,
                        new_stock,
                        image,
                    )
                )

                price_drops += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)

        # ----------------------------------------------------
        # BACK IN STOCK
        # ----------------------------------------------------

        if (
            NOTIFY_BACK_IN_STOCK
            and old_stock <= 0
            and new_stock > 0
        ):

            print(
                f"BACK IN STOCK: {name}"
            )

            try:

                send_discord(
                    back_in_stock_embed(
                        name,
                        new_price or 0,
                        new_stock,
                        image,
                    )
                )

                back_in_stock += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)

        # ----------------------------------------------------
        # OUT OF STOCK
        # ----------------------------------------------------

        if (
            NOTIFY_OUT_OF_STOCK
            and old_stock > 0
            and new_stock <= 0
        ):

            print(
                f"OUT OF STOCK: {name}"
            )

            try:

                send_discord(
                    out_of_stock_embed(
                        name,
                        new_price or 0,
                        image,
                    )
                )

                out_of_stock += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)

    print()
    print("Notification summary:")
    print(f"Price drops: {price_drops}")
    print(f"Back in stock: {back_in_stock}")
    print(f"Out of stock: {out_of_stock}")


if __name__ == "__main__":
    compare()