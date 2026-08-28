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

# If there are more than this many changes of one type,
# use batched Discord messages instead of one message per card.
BATCH_THRESHOLD = 10

# Number of cards per batched Discord message.
BATCH_SIZE = 10

# Delay between individual Discord messages.
MESSAGE_DELAY = 2.1

# Maximum Discord retry attempts after rate limiting.
MAX_RETRIES = 5


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

def send_discord(embed=None, embeds=None):

    if not DISCORD_WEBHOOK:

        print(
            "DISCORD_WEBHOOK is not configured. "
            "Skipping Discord notification."
        )

        return False

    if embeds is None:
        embeds = [embed]

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.post(
                DISCORD_WEBHOOK,
                json={
                    "embeds": embeds
                },
                timeout=30,
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code in (200, 204):

                return True

            # ------------------------------------------------
            # RATE LIMITED
            # ------------------------------------------------

            if response.status_code == 429:

                try:
                    data = response.json()

                    retry_after = float(
                        data.get(
                            "retry_after",
                            2,
                        )
                    )

                except Exception:

                    retry_after = 2

                retry_after = max(
                    retry_after,
                    1.5,
                )

                print(
                    "Discord rate limit reached."
                )

                print(
                    f"Waiting {retry_after:.1f} seconds "
                    f"before retry "
                    f"({attempt}/{MAX_RETRIES})..."
                )

                time.sleep(retry_after)

                continue

            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------

            response.raise_for_status()

        except requests.RequestException as e:

            print(
                f"Discord request failed "
                f"(attempt {attempt}/{MAX_RETRIES}):"
            )

            print(e)

            if attempt < MAX_RETRIES:

                time.sleep(2)

    print(
        "Discord notification failed after "
        f"{MAX_RETRIES} attempts."
    )

    return False


def send_single(embed):

    success = send_discord(embed)

    if success:

        time.sleep(
            MESSAGE_DELAY
        )

    return success


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

        "description": (
            f"**{name}**"
        ),

        "color": 0x9B59B6,

        "fields": [

            {
                "name": "Price",
                "value": (
                    f"${current_price:,.2f}"
                ),
                "inline": True,
            },

            {
                "name": "Stock",
                "value": str(
                    current_stock
                ),
                "inline": True,
            },

        ],
    }

    if image:

        embed["image"] = {
            "url": image
        }

    return embed


def price_drop_embed(
    name,
    old_price,
    new_price,
    current_stock,
    image,
):

    difference = (
        old_price -
        new_price
    )

    percentage = (
        difference /
        old_price *
        100
        if old_price > 0
        else 0
    )

    embed = {

        "title": (
            "📉 Yu-Gi-Oh Price Drop"
        ),

        "description": (
            f"**{name}**"
        ),

        "color": 0x2ECC71,

        "fields": [

            {
                "name": "Previous price",

                "value": (
                    f"${old_price:,.2f}"
                ),

                "inline": True,
            },

            {
                "name": "New price",

                "value": (
                    f"${new_price:,.2f}"
                ),

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

                "value": str(
                    current_stock
                ),

                "inline": True,
            },

        ],
    }

    if image:

        embed["image"] = {
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

    difference = (
        new_price -
        old_price
    )

    percentage = (
        difference /
        old_price *
        100
        if old_price > 0
        else 0
    )

    embed = {

        "title": (
            "📈 Yu-Gi-Oh Price Increase"
        ),

        "description": (
            f"**{name}**"
        ),

        "color": 0xE67E22,

        "fields": [

            {
                "name": "Previous price",

                "value": (
                    f"${old_price:,.2f}"
                ),

                "inline": True,
            },

            {
                "name": "New price",

                "value": (
                    f"${new_price:,.2f}"
                ),

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

                "value": str(
                    current_stock
                ),

                "inline": True,
            },

        ],
    }

    if image:

        embed["image"] = {
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

        "title": (
            "🟢 Yu-Gi-Oh Card Back In Stock"
        ),

        "description": (
            f"**{name}**"
        ),

        "color": 0x3498DB,

        "fields": [

            {
                "name": "Price",

                "value": (
                    f"${current_price:,.2f}"
                ),

                "inline": True,
            },

            {
                "name": "Stock",

                "value": str(
                    current_stock
                ),

                "inline": True,
            },

        ],
    }

    if image:

        embed["image"] = {
            "url": image
        }

    return embed


def out_of_stock_embed(
    name,
    current_price,
    image,
):

    embed = {

        "title": (
            "🔴 Yu-Gi-Oh Card Out Of Stock"
        ),

        "description": (
            f"**{name}**"
        ),

        "color": 0xE74C3C,

        "fields": [

            {
                "name": "Price",

                "value": (
                    f"${current_price:,.2f}"
                ),

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

        embed["image"] = {
            "url": image
        }

    return embed


# ============================================================
# BATCH NOTIFICATIONS
# ============================================================

def batch_new_cards(cards):

    for start in range(
        0,
        len(cards),
        BATCH_SIZE,
    ):

        batch = cards[
            start:
            start + BATCH_SIZE
        ]

        lines = []

        for card in batch:

            lines.append(
                f"• **{card['name']}** — "
                f"${card['price']:,.2f} — "
                f"Stock: {card['stock']}"
            )

        embed = {

            "title": (
                "🆕 New Yu-Gi-Oh Cards Detected"
            ),

            "description": (
                "\n".join(lines)
            ),

            "color": 0x9B59B6,

            "footer": {
                "text": (
                    f"Showing {len(batch)} "
                    "new cards"
                )
            },

        }

        send_single(embed)


def batch_price_drops(cards):

    for start in range(
        0,
        len(cards),
        BATCH_SIZE,
    ):

        batch = cards[
            start:
            start + BATCH_SIZE
        ]

        lines = []

        for card in batch:

            difference = (
                card["old_price"] -
                card["new_price"]
            )

            lines.append(
                f"• **{card['name']}** — "
                f"${card['old_price']:,.2f} → "
                f"${card['new_price']:,.2f} "
                f"(−${difference:,.2f})"
            )

        embed = {

            "title": (
                "📉 Yu-Gi-Oh Price Drops"
            ),

            "description": (
                "\n".join(lines)
            ),

            "color": 0x2ECC71,

            "footer": {
                "text": (
                    f"Showing {len(batch)} "
                    "price drops"
                )
            },

        }

        send_single(embed)


def batch_price_increases(cards):

    for start in range(
        0,
        len(cards),
        BATCH_SIZE,
    ):

        batch = cards[
            start:
            start + BATCH_SIZE
        ]

        lines = []

        for card in batch:

            difference = (
                card["new_price"] -
                card["old_price"]
            )

            lines.append(
                f"• **{card['name']}** — "
                f"${card['old_price']:,.2f} → "
                f"${card['new_price']:,.2f} "
                f"(+${difference:,.2f})"
            )

        embed = {

            "title": (
                "📈 Yu-Gi-Oh Price Increases"
            ),

            "description": (
                "\n".join(lines)
            ),

            "color": 0xE67E22,

            "footer": {
                "text": (
                    f"Showing {len(batch)} "
                    "price increases"
                )
            },

        }

        send_single(embed)


def batch_back_in_stock(cards):

    for start in range(
        0,
        len(cards),
        BATCH_SIZE,
    ):

        batch = cards[
            start:
            start + BATCH_SIZE
        ]

        lines = []

        for card in batch:

            lines.append(
                f"• **{card['name']}** — "
                f"${card['price']:,.2f} — "
                f"Stock: {card['stock']}"
            )

        embed = {

            "title": (
                "🟢 Yu-Gi-Oh Cards Back In Stock"
            ),

            "description": (
                "\n".join(lines)
            ),

            "color": 0x3498DB,

            "footer": {
                "text": (
                    f"Showing {len(batch)} "
                    "cards"
                )
            },

        }

        send_single(embed)


def batch_out_of_stock(cards):

    for start in range(
        0,
        len(cards),
        BATCH_SIZE,
    ):

        batch = cards[
            start:
            start + BATCH_SIZE
        ]

        lines = []

        for card in batch:

            lines.append(
                f"• **{card['name']}** — "
                f"${card['price']:,.2f}"
            )

        embed = {

            "title": (
                "🔴 Yu-Gi-Oh Cards Out Of Stock"
            ),

            "description": (
                "\n".join(lines)
            ),

            "color": 0xE74C3C,

            "footer": {
                "text": (
                    f"Showing {len(batch)} "
                    "cards"
                )
            },

        }

        send_single(embed)


# ============================================================
# COMPARISON
# ============================================================

def compare():

    print("=" * 60)
    print("HARU TCG - TRACKER")
    print("=" * 60)

    current = load_csv(
        CURRENT
    )

    previous = load_csv(
        PREVIOUS
    )

    print(
        f"Current products: "
        f"{len(current)}"
    )

    print(
        f"Previous products: "
        f"{len(previous)}"
    )

    if not previous:

        print()
        print(
            "No previous data found."
        )

        print(
            "This is probably "
            "the first run."
        )

        print(
            "No notifications "
            "will be sent."
        )

        return

    new_cards = []

    price_drops = []

    price_increases = []

    back_in_stock = []

    out_of_stock = []

    # ========================================================
    # COMPARE PRODUCTS
    # ========================================================

    for key, new_product in current.items():

        old_product = previous.get(
            key
        )

        name = new_product.get(
            "card",
            "Unknown",
        )

        image = new_product.get(
            "image",
            "",
        )

        new_price = price(
            new_product.get(
                "price"
            )
        )

        new_stock = stock(
            new_product.get(
                "stock"
            )
        )

        # ====================================================
        # NEW CARD
        # ====================================================

        if old_product is None:

            if NOTIFY_NEW_CARDS:

                print(
                    f"NEW CARD: {name}"
                )

                new_cards.append({

                    "name": name,

                    "price": (
                        new_price or 0
                    ),

                    "stock": new_stock,

                    "image": image,

                })

            continue

        old_price = price(
            old_product.get(
                "price"
            )
        )

        old_stock = stock(
            old_product.get(
                "stock"
            )
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
                f"{old_price} -> "
                f"{new_price}"
            )

            price_drops.append({

                "name": name,

                "old_price": old_price,

                "new_price": new_price,

                "stock": new_stock,

                "image": image,

            })

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
                f"{old_price} -> "
                f"{new_price}"
            )

            price_increases.append({

                "name": name,

                "old_price": old_price,

                "new_price": new_price,

                "stock": new_stock,

                "image": image,

            })

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

            back_in_stock.append({

                "name": name,

                "price": (
                    new_price or 0
                ),

                "stock": new_stock,

                "image": image,

            })

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

            out_of_stock.append({

                "name": name,

                "price": (
                    new_price or 0
                ),

                "image": image,

            })

    # ========================================================
    # SEND NEW CARD NOTIFICATIONS
    # ========================================================

    if new_cards:

        if len(new_cards) <= BATCH_THRESHOLD:

            for card in new_cards:

                send_single(
                    new_card_embed(
                        card["name"],
                        card["price"],
                        card["stock"],
                        card["image"],
                    )
                )

        else:

            print(
                f"Batching {len(new_cards)} "
                "new card notifications."
            )

            batch_new_cards(
                new_cards
            )

    # ========================================================
    # SEND PRICE DROP NOTIFICATIONS
    # ========================================================

    if price_drops:

        if len(price_drops) <= BATCH_THRESHOLD:

            for card in price_drops:

                send_single(
                    price_drop_embed(
                        card["name"],
                        card["old_price"],
                        card["new_price"],
                        card["stock"],
                        card["image"],
                    )
                )

        else:

            print(
                f"Batching {len(price_drops)} "
                "price drop notifications."
            )

            batch_price_drops(
                price_drops
            )

    # ========================================================
    # SEND PRICE INCREASE NOTIFICATIONS
    # ========================================================

    if price_increases:

        if len(price_increases) <= BATCH_THRESHOLD:

            for card in price_increases:

                send_single(
                    price_increase_embed(
                        card["name"],
                        card["old_price"],
                        card["new_price"],
                        card["stock"],
                        card["image"],
                    )
                )

        else:

            print(
                f"Batching {len(price_increases)} "
                "price increase notifications."
            )

            batch_price_increases(
                price_increases
            )

    # ========================================================
    # SEND BACK IN STOCK NOTIFICATIONS
    # ========================================================

    if back_in_stock:

        if len(back_in_stock) <= BATCH_THRESHOLD:

            for card in back_in_stock:

                send_single(
                    back_in_stock_embed(
                        card["name"],
                        card["price"],
                        card["stock"],
                        card["image"],
                    )
                )

        else:

            print(
                f"Batching {len(back_in_stock)} "
                "back-in-stock notifications."
            )

            batch_back_in_stock(
                back_in_stock
            )

    # ========================================================
    # SEND OUT OF STOCK NOTIFICATIONS
    # ========================================================

    if out_of_stock:

        if len(out_of_stock) <= BATCH_THRESHOLD:

            for card in out_of_stock:

                send_single(
                    out_of_stock_embed(
                        card["name"],
                        card["price"],
                        card["image"],
                    )
                )

        else:

            print(
                f"Batching {len(out_of_stock)} "
                "out-of-stock notifications."
            )

            batch_out_of_stock(
                out_of_stock
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 60)
    print("NOTIFICATION SUMMARY")
    print("=" * 60)

    print(
        f"New cards: "
        f"{len(new_cards)}"
    )

    print(
        f"Price drops: "
        f"{len(price_drops)}"
    )

    print(
        f"Price increases: "
        f"{len(price_increases)}"
    )

    print(
        f"Back in stock: "
        f"{len(back_in_stock)}"
    )

    print(
        f"Out of stock: "
        f"{len(out_of_stock)}"
    )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    compare()
