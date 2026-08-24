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

# Small delay between Discord messages.
# Helps avoid hitting Discord's rate limit.
DISCORD_DELAY = 1.0

# Maximum number of times to retry a Discord 429.
MAX_DISCORD_RETRIES = 5


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

            name = row.get(
                "card",
                "",
            ).strip()

            if not name:
                continue

            variant_id = row.get(
                "variant_id",
                "",
            ).strip()

            image = row.get(
                "image",
                "",
            ).strip()

            variant = row.get(
                "variant",
                "",
            ).strip()

            # ------------------------------------------------
            # New CSV format:
            #
            # Shopify variant ID is the most reliable key.
            # ------------------------------------------------

            if variant_id:

                key = (
                    "variant",
                    variant_id,
                )

            # ------------------------------------------------
            # Compatibility with older CSV files.
            # ------------------------------------------------

            else:

                key = (
                    "legacy",
                    name.lower(),
                    image,
                    variant.lower(),
                )

            products[key] = row

    return products


# ============================================================
# PARSING
# ============================================================

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

        return False

    for attempt in range(
        1,
        MAX_DISCORD_RETRIES + 1,
    ):

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

            if response.status_code in (
                200,
                204,
            ):

                # Give Discord a little breathing room.
                time.sleep(DISCORD_DELAY)

                return True

            # ------------------------------------------------
            # Rate limited
            # ------------------------------------------------

            if response.status_code == 429:

                retry_after = None

                try:
                    data = response.json()
                    retry_after = data.get(
                        "retry_after"
                    )
                except Exception:
                    pass

                if retry_after is None:

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                try:
                    retry_after = float(
                        retry_after
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    retry_after = 5.0

                # Add a small safety buffer.
                wait_time = retry_after + 1.0

                print(
                    "Discord rate limit reached."
                )

                print(
                    f"Waiting {wait_time:.1f} seconds "
                    f"before retry "
                    f"({attempt}/{MAX_DISCORD_RETRIES})..."
                )

                time.sleep(wait_time)

                continue

            # ------------------------------------------------
            # Other Discord error
            # ------------------------------------------------

            print(
                "Discord returned HTTP "
                f"{response.status_code}:"
            )

            print(response.text)

            return False

        except requests.RequestException as e:

            print(
                "Discord request failed:"
            )

            print(e)

            if attempt < MAX_DISCORD_RETRIES:

                print(
                    "Retrying in 5 seconds..."
                )

                time.sleep(5)

            else:

                return False

    print(
        "Discord notification failed after "
        f"{MAX_DISCORD_RETRIES} attempts."
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

    current = load_csv(CURRENT)
    previous = load_csv(PREVIOUS)

    print(
        f"Current products: {len(current)}"
    )

    print(
        f"Previous products: {len(previous)}"
    )

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


    new_cards = 0
    price_drops = 0
    price_increases = 0
    back_in_stock = 0
    out_of_stock = 0


    # ========================================================
    # CHECK CURRENT PRODUCTS
    # ========================================================

    for key, new_product in current.items():

        old_product = previous.get(key)

        name = new_product.get(
            "card",
            "Unknown",
        ).strip()

        image = new_product.get(
            "image",
            "",
        ).strip()

        new_price = price(
            new_product.get("price")
        )

        new_stock = stock(
            new_product.get("stock")
        )


        # ====================================================
        # NEW CARD
        # ====================================================

        if old_product is None:

            if NOTIFY_NEW_CARDS:

                print(
                    f"NEW CARD: {name}"
                )

                try:

                    embed = new_card_embed(
                        name,
                        new_price or 0,
                        new_stock,
                        image,
                    )

                    if send_discord(embed):
                        new_cards += 1

                except Exception as e:

                    print(
                        "Discord notification failed:"
                    )

                    print(e)

            continue


        # ====================================================
        # EXISTING CARD
        # ====================================================

        old_price = price(
            old_product.get("price")
        )

        old_stock = stock(
            old_product.get("stock")
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

            try:

                embed = price_drop_embed(
                    name,
                    old_price,
                    new_price,
                    new_stock,
                    image,
                )

                if send_discord(embed):
                    price_drops += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)


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

            try:

                embed = price_increase_embed(
                    name,
                    old_price,
                    new_price,
                    new_stock,
                    image,
                )

                if send_discord(embed):
                    price_increases += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)


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

            try:

                embed = back_in_stock_embed(
                    name,
                    new_price or 0,
                    new_stock,
                    image,
                )

                if send_discord(embed):
                    back_in_stock += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)


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

            try:

                embed = out_of_stock_embed(
                    name,
                    new_price or 0,
                    image,
                )

                if send_discord(embed):
                    out_of_stock += 1

            except Exception as e:

                print(
                    "Discord notification failed:"
                )

                print(e)


    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 60)
    print("NOTIFICATION SUMMARY")
    print("=" * 60)

    print(
        f"New cards:       {new_cards}"
    )

    print(
        f"Price drops:     {price_drops}"
    )

    print(
        f"Price increases: {price_increases}"
    )

    print(
        f"Back in stock:   {back_in_stock}"
    )

    print(
        f"Out of stock:    {out_of_stock}"
    )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    compare()
