import csv
import os
import time
from pathlib import Path

import requests


CURRENT = Path("yugioh_cards.csv")
PREVIOUS = Path("previous_cards.csv")

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")


# ============================================================
# SETTINGS
# ============================================================

NOTIFY_NEW_CARDS = True
NOTIFY_PRICE_DROPS = True
NOTIFY_PRICE_INCREASES = True
NOTIFY_BACK_IN_STOCK = True
NOTIFY_OUT_OF_STOCK = True

# ------------------------------------------------------------
# DISCORD RATE LIMIT SETTINGS
# ------------------------------------------------------------

# Minimum delay between Discord messages.
DISCORD_DELAY = 1.0

# Maximum number of NEW CARD notifications to send
# individually during one run.
#
# This prevents the first run from flooding Discord.
MAX_NEW_CARD_NOTIFICATIONS = 20

# If more than this many new cards are detected,
# send one summary instead of individual notifications.
NEW_CARD_BATCH_THRESHOLD = 20


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

last_discord_message = 0


def send_discord(embed):

    global last_discord_message

    if not DISCORD_WEBHOOK:

        print(
            "DISCORD_WEBHOOK is not configured. "
            "Skipping Discord notification."
        )

        return False

    # --------------------------------------------------------
    # Wait between messages
    # --------------------------------------------------------

    elapsed = time.time() - last_discord_message

    if elapsed < DISCORD_DELAY:

        wait_time = DISCORD_DELAY - elapsed

        time.sleep(wait_time)

    # --------------------------------------------------------
    # Try sending
    # --------------------------------------------------------

    for attempt in range(5):

        try:

            response = requests.post(
                DISCORD_WEBHOOK,
                json={
                    "embeds": [embed]
                },
                timeout=30,
            )

            # ------------------------------------------------
            # Success
            # ------------------------------------------------

            if response.status_code in (200, 204):

                last_discord_message = time.time()

                return True

            # ------------------------------------------------
            # Rate limited
            # ------------------------------------------------

            if response.status_code == 429:

                try:
                    data = response.json()
                    retry_after = float(
                        data.get("retry_after", 2)
                    )
                except Exception:
                    retry_after = 2

                retry_after = max(
                    retry_after,
                    1.0,
                )

                print(
                    "Discord rate limit reached."
                )

                print(
                    f"Waiting {retry_after:.1f} "
                    f"seconds before retry "
                    f"({attempt + 1}/5)..."
                )

                time.sleep(retry_after)

                continue

            # ------------------------------------------------
            # Other HTTP error
            # ------------------------------------------------

            response.raise_for_status()

        except requests.RequestException as e:

            print(
                "Discord notification failed:"
            )

            print(e)

            if attempt < 4:

                wait_time = 2 ** attempt

                print(
                    f"Retrying in "
                    f"{wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:

                return False

    print(
        "Discord notification failed "
        "after 5 attempts."
    )

    return False


# ============================================================
# DISCORD EMBEDS
# ============================================================

def new_card_embed(
    name,
    current_price,
    current_stock,
    image,
):

    embed = {
        "title": "🆕 New Yu-Gi-Oh Card Detected",
        "description": f"**{name}**",
        "color": 0x9B59B6,

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


def new_cards_summary_embed(
    new_cards,
):

    # --------------------------------------------------------
    # Show up to 20 card names in the summary.
    # --------------------------------------------------------

    displayed = new_cards[:20]

    lines = []

    for card in displayed:

        name = card["name"]
        current_price = card["price"]
        current_stock = card["stock"]

        lines.append(
            f"• **{name}** — "
            f"${current_price:,.2f} "
            f"(Stock: {current_stock})"
        )

    if len(new_cards) > 20:

        lines.append(
            f"\n...and "
            f"{len(new_cards) - 20} more."
        )

    embed = {
        "title": "🆕 New Yu-Gi-Oh Cards Detected",
        "description": (
            f"**{len(new_cards)} new cards detected.**\n\n"
            + "\n".join(lines)
        ),
        "color": 0x9B59B6,
    }

    return embed


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


def price_increase_embed(
    name,
    old_price,
    new_price,
    current_stock,
    image,
):

    difference = new_price - old_price

    percentage = (
        difference / old_price * 100
        if old_price > 0
        else 0
    )

    embed = {
        "title": "📈 Yu-Gi-Oh Price Increase",
        "description": f"**{name}**",
        "color": 0xE67E22,

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
                "name": "Increase",
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

    print("=" * 60)
    print("HARU TCG - TRACKER")
    print("=" * 60)

    current = load_csv(CURRENT)
    previous = load_csv(PREVIOUS)

    print(
        f"Current products: {len(current)}"
    )

    print(
        f"Previous products: {len(previous)}"
    )

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not previous:

        print()
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


    # --------------------------------------------------------
    # COUNTERS
    # --------------------------------------------------------

    new_cards = []
    price_drops = 0
    price_increases = 0
    back_in_stock = 0
    out_of_stock = 0


    # ========================================================
    # CHECK CURRENT PRODUCTS
    # ========================================================

    for key, new_product in current.items():

        old_product = previous.get(key)

        # ====================================================
        # NEW CARD
        # ====================================================

        if old_product is None:

            name = new_product.get(
                "card",
                "Unknown",
            )

            image = new_product.get(
                "image",
                "",
            )

            new_price = price(
                new_product.get("price")
            )

            new_stock = stock(
                new_product.get("stock")
            )

            new_cards.append({
                "name": name,
                "price": new_price or 0,
                "stock": new_stock,
                "image": image,
            })

            continue


        # ====================================================
        # EXISTING CARD
        # ====================================================

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


        # ====================================================
        # PRICE DROP
        # ====================================================

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

            if send_discord(
                price_drop_embed(
                    name,
                    old_price,
                    new_price,
                    new_stock,
                    image,
                )
            ):

                price_drops += 1


        # ====================================================
        # PRICE INCREASE
        # ====================================================

        if (
            NOTIFY_PRICE_INCREASES
            and old_price is not None
            and new_price is not None
            and new_price > old_price
        ):

            print(
                f"PRICE INCREASE: {name} | "
                f"{old_price} -> {new_price}"
            )

            if send_discord(
                price_increase_embed(
                    name,
                    old_price,
                    new_price,
                    new_stock,
                    image,
                )
            ):

                price_increases += 1


        # ====================================================
        # BACK IN STOCK
        # ====================================================

        if (
            NOTIFY_BACK_IN_STOCK
            and old_stock <= 0
            and new_stock > 0
        ):

            print(
                f"BACK IN STOCK: {name}"
            )

            if send_discord(
                back_in_stock_embed(
                    name,
                    new_price or 0,
                    new_stock,
                    image,
                )
            ):

                back_in_stock += 1


        # ====================================================
        # OUT OF STOCK
        # ====================================================

        if (
            NOTIFY_OUT_OF_STOCK
            and old_stock > 0
            and new_stock <= 0
        ):

            print(
                f"OUT OF STOCK: {name}"
            )

            if send_discord(
                out_of_stock_embed(
                    name,
                    new_price or 0,
                    image,
                )
            ):

                out_of_stock += 1


    # ========================================================
    # NEW CARD NOTIFICATIONS
    # ========================================================

    print()
    print(
        f"New cards detected: {len(new_cards)}"
    )

    if NOTIFY_NEW_CARDS and new_cards:

        # ----------------------------------------------------
        # MANY NEW CARDS
        # ----------------------------------------------------

        if len(new_cards) > NEW_CARD_BATCH_THRESHOLD:

            print(
                f"{len(new_cards)} new cards detected."
            )

            print(
                "Sending one summary instead of "
                "individual notifications."
            )

            if send_discord(
                new_cards_summary_embed(
                    new_cards
                )
            ):

                print(
                    "New card summary sent."
                )

        # ----------------------------------------------------
        # SMALL NUMBER OF NEW CARDS
        # ----------------------------------------------------

        else:

            for card in new_cards[
                :MAX_NEW_CARD_NOTIFICATIONS
            ]:

                print(
                    f"NEW CARD: {card['name']}"
                )

                send_discord(
                    new_card_embed(
                        card["name"],
                        card["price"],
                        card["stock"],
                        card["image"],
                    )
                )

            if len(new_cards) > MAX_NEW_CARD_NOTIFICATIONS:

                remaining = (
                    len(new_cards)
                    - MAX_NEW_CARD_NOTIFICATIONS
                )

                print(
                    f"{remaining} additional "
                    f"new cards were not individually "
                    f"notified."
                )


    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 60)
    print("NOTIFICATION SUMMARY")
    print("=" * 60)

    print(
        f"New cards: {len(new_cards)}"
    )

    print(
        f"Price drops: {price_drops}"
    )

    print(
        f"Price increases: {price_increases}"
    )

    print(
        f"Back in stock: {back_in_stock}"
    )

    print(
        f"Out of stock: {out_of_stock}"
    )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    compare()
