import csv
import time
from pathlib import Path
from urllib.parse import urljoin

import requests


STORE = "https://harutcg.com"
OUTPUT = Path("yugioh_cards.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}


def get_products():
    session = requests.Session()
    session.headers.update(HEADERS)

    products = []
    page = 1

    while True:
        print(f"Downloading page {page}...")

        response = session.get(
            f"{STORE}/products.json",
            params={
                "limit": 250,
                "page": page,
            },
            timeout=30,
        )

        print(f"HTTP {response.status_code}")

        response.raise_for_status()

        data = response.json()
        batch = data.get("products", [])

        print(f"Products on page: {len(batch)}")

        if not batch:
            break

        products.extend(batch)
        page += 1

        time.sleep(0.5)

    return products


def is_yugioh(product):
    fields = [
        product.get("title", ""),
        product.get("handle", ""),
        product.get("vendor", ""),
        product.get("product_type", ""),
        product.get("tags", ""),
    ]

    text = " ".join(str(x) for x in fields).lower()

    return (
        "yu-gi-oh" in text
        or "yugioh" in text
        or "ygo" in text
    )


def is_excluded_product(product):
    """
    Exclude actual Folios and Core/Mazo products.

    IMPORTANT:
    We only check how the TITLE STARTS.
    This means a legitimate card containing words such as
    'Core', 'Folios', 'Blackwing', etc. is not automatically removed.
    """

    title = product.get("title", "").strip().lower()

    excluded_prefixes = (
        "folios/",
        "folios /",
        "folio/",
        "folio /",
        "core / mazo",
        "core/mazo",
        "core - mazo",
    )

    return title.startswith(excluded_prefixes)


def get_image(product):
    images = product.get("images", [])

    if not images:
        return ""

    return urljoin(STORE, images[0].get("src", ""))


def scrape(products):
    rows = []

    for product in products:

        if not is_yugioh(product):
            continue

        # Exclude actual Folios and Core/Mazo products.
        # This happens AFTER the Yu-Gi-Oh check.
        if is_excluded_product(product):
            print(
                f"Excluded: {product.get('title', '').strip()}"
            )
            continue

        card = product.get("title", "").strip()
        image = get_image(product)

        for variant in product.get("variants", []):

            stock = variant.get("inventory_quantity")

            if stock is None:
                stock = 1 if variant.get("available") else 0

            rows.append({
                "card": card,
                "price": variant.get("price", ""),
                "stock": stock,
                "image": image,
            })

    return rows


def save_csv(rows):
    with open(
        OUTPUT,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "card",
                "price",
                "stock",
                "image",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)


def main():

    print("=" * 60)
    print("HARU TCG - YU-GI-OH SCRAPER")
    print("=" * 60)

    try:
        products = get_products()

        print()
        print(f"Total products downloaded: {len(products)}")

        rows = scrape(products)

        print(f"Yu-Gi-Oh products found: {len(rows)}")

        # ALWAYS create the CSV.
        save_csv(rows)

        print()
        print(f"CSV created: {OUTPUT.resolve()}")
        print(f"Rows written: {len(rows)}")

        if rows:
            print()
            print("First 5 results:")

            for row in rows[:5]:
                print(
                    f"{row['card']} | "
                    f"${row['price']} | "
                    f"Stock: {row['stock']}"
                )
        else:
            print()
            print(
                "WARNING: No Yu-Gi-Oh products were found. "
                "The CSV was still created."
            )

    except Exception as e:
        print()
        print("ERROR:")
        print(type(e).__name__, e)


if __name__ == "__main__":
    main()