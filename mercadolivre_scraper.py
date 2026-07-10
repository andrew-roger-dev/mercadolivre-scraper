"""
Mercado Livre Product Scraper
Extracts product data from Mercado Livre search results.

Usage:
    python mercadolivre_scraper.py "geladeira consul" --pages 3 --output products.csv

Author: Andrew
"""

import argparse
import csv
import json
import random
import time
import sys
from dataclasses import dataclass, fields, asdict
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


@dataclass
class Product:
    """Represents a scraped product listing."""
    title: str
    price: float
    original_price: Optional[float]
    discount_pct: Optional[str]
    seller: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    shipping: Optional[str]
    condition: Optional[str]
    url: str


# --- Configuration -----------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

REQUEST_TIMEOUT = 15
DELAY_RANGE = (1.5, 3.5)  # seconds between requests


# --- HTTP Layer --------------------------------------------------------------

def get_session() -> requests.Session:
    """Create a session with randomized User-Agent and realistic headers."""
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    session.headers["User-Agent"] = random.choice(USER_AGENTS)
    return session


def fetch_page(session: requests.Session, url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return parsed HTML. Returns None on failure."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [!] Request failed: {e}", file=sys.stderr)
        return None


# --- Parsing Layer -----------------------------------------------------------

def parse_price(text: str) -> Optional[float]:
    """Parse price string like 'R$ 1.299' or '1299,90' into float."""
    if not text:
        return None
    cleaned = text.replace("R$", "").replace("\xa0", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_product(item) -> Optional[Product]:
    """Extract product data from a single search result element."""
    try:
        # --- Title ---
        title_el = (
            item.select_one("h2.poly-component__title a")
            or item.select_one("a.poly-component__title")
            or item.select_one("h2 a")
            or item.select_one(".ui-search-item__title")
        )
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # --- URL ---
        link_el = (
            item.select_one("h2.poly-component__title a")
            or item.select_one("a.poly-component__title")
            or item.select_one("a[href*='produto.mercadolivre']")
            or item.select_one("a[href*='mercadolivre.com.br']")
            or item.select_one("h2 a")
        )
        url = link_el["href"] if link_el and link_el.get("href") else ""

        # --- Price ---
        price_el = (
            item.select_one(".poly-price__current .andes-money-amount__fraction")
            or item.select_one(".andes-money-amount__fraction")
            or item.select_one(".price-tag-fraction")
        )
        cents_el = (
            item.select_one(".poly-price__current .andes-money-amount__cents")
            or item.select_one(".andes-money-amount__cents")
        )
        
        if not price_el:
            return None
        
        price_text = price_el.get_text(strip=True)
        cents_text = cents_el.get_text(strip=True) if cents_el else "00"
        price = parse_price(f"{price_text},{cents_text}")
        
        if price is None:
            return None

        # --- Original price (before discount) ---
        original_el = item.select_one(
            "s .andes-money-amount__fraction, "
            ".andes-money-amount--previous .andes-money-amount__fraction, "
            ".price-tag-amount--previous .price-tag-fraction"
        )
        original_price = parse_price(original_el.get_text(strip=True)) if original_el else None

        # --- Discount ---
        discount_el = item.select_one(
            ".poly-component__discount, "
            ".ui-search-price__discount, "
            ".andes-money-amount__discount"
        )
        discount_pct = discount_el.get_text(strip=True) if discount_el else None

        # --- Seller ---
        seller_el = item.select_one(
            ".poly-component__seller, "
            ".ui-search-official-store-label, "
            ".shops__item-seller-name"
        )
        seller = seller_el.get_text(strip=True) if seller_el else None

        # --- Rating ---
        rating_el = item.select_one(
            ".poly-reviews__rating, "
            ".ui-search-reviews__rating-number"
        )
        rating = None
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).replace(",", "."))
            except ValueError:
                pass

        # --- Reviews count ---
        reviews_el = item.select_one(
            ".poly-reviews__total, "
            ".ui-search-reviews__amount"
        )
        reviews_count = None
        if reviews_el:
            text = reviews_el.get_text(strip=True)
            digits = "".join(c for c in text if c.isdigit())
            reviews_count = int(digits) if digits else None

        # --- Shipping ---
        shipping_el = item.select_one(
            ".poly-component__shipping, "
            ".ui-search-item__shipping, "
            ".ui-pb-highlight"
        )
        shipping = shipping_el.get_text(strip=True) if shipping_el else None

        # --- Condition ---
        condition_el = item.select_one(
            ".ui-search-item__condition, "
            ".poly-component__condition"
        )
        condition = condition_el.get_text(strip=True) if condition_el else None

        return Product(
            title=title,
            price=price,
            original_price=original_price,
            discount_pct=discount_pct,
            seller=seller,
            rating=rating,
            reviews_count=reviews_count,
            shipping=shipping,
            condition=condition,
            url=url,
        )

    except Exception as e:
        print(f"  [!] Parse error: {e}", file=sys.stderr)
        return None


def parse_search_page(soup: BeautifulSoup) -> list[Product]:
    """Parse all product listings from a search results page."""
    products = []

    # Try multiple container selectors (ML changes layout periodically)
    items = (
        soup.select("li.ui-search-layout__item")
        or soup.select(".poly-card")
        or soup.select(".ui-search-result")
        or soup.select("ol.ui-search-layout li")
    )

    for item in items:
        product = extract_product(item)
        if product:
            products.append(product)

    return products


def get_next_page_url(soup: BeautifulSoup) -> Optional[str]:
    """Extract the 'next page' URL from pagination."""
    next_btn = (
        soup.select_one("li.andes-pagination__button--next a")
        or soup.select_one("a[title='Seguinte']")
        or soup.select_one("a[title='Próxima']")
    )
    return next_btn["href"] if next_btn and next_btn.get("href") else None


# --- Main Scraper ------------------------------------------------------------

def scrape_mercadolivre(
    query: str,
    max_pages: int = 3,
    sort: str = "relevance",
) -> list[Product]:
    """
    Scrape Mercado Livre search results.

    Args:
        query: Search term (e.g. "geladeira consul 300L")
        max_pages: Maximum number of result pages to scrape
        sort: Sort order — "relevance" (default) or "price_asc"

    Returns:
        List of Product objects
    """
    sort_param = ""
    if sort == "price_asc":
        sort_param = "_OrderId_PRICE_PriceRange_0-0"

    encoded = quote_plus(query)
    url = f"https://lista.mercadolivre.com.br/{encoded}{sort_param}"

    session = get_session()
    all_products: list[Product] = []

    for page in range(1, max_pages + 1):
        print(f"  [*] Page {page}/{max_pages}: {url[:80]}...")

        soup = fetch_page(session, url)
        if not soup:
            print(f"  [!] Failed to fetch page {page}, stopping.")
            break

        products = parse_search_page(soup)
        if not products:
            print(f"  [*] No products found on page {page}, stopping.")
            break

        all_products.extend(products)
        print(f"  [+] Extracted {len(products)} products (total: {len(all_products)})")

        # Get next page
        if page < max_pages:
            next_url = get_next_page_url(soup)
            if not next_url:
                print(f"  [*] No next page found, stopping.")
                break
            url = next_url

            # Polite delay
            delay = random.uniform(*DELAY_RANGE)
            print(f"  [~] Waiting {delay:.1f}s...")
            time.sleep(delay)

    return all_products


# --- Output ------------------------------------------------------------------

def save_csv(products: list[Product], filepath: str):
    """Save products to CSV file."""
    if not products:
        print("  [!] No products to save.")
        return

    fieldnames = [f.name for f in fields(Product)]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            writer.writerow(asdict(p))

    print(f"  [✓] Saved {len(products)} products to {filepath}")


def save_json(products: list[Product], filepath: str):
    """Save products to JSON file."""
    if not products:
        print("  [!] No products to save.")
        return

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)

    print(f"  [✓] Saved {len(products)} products to {filepath}")


def print_summary(products: list[Product]):
    """Print a quick summary of scraped data."""
    if not products:
        return

    prices = [p.price for p in products if p.price]
    rated = [p for p in products if p.rating]

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total products:  {len(products)}")
    print(f"  Price range:     R$ {min(prices):,.2f} — R$ {max(prices):,.2f}")
    print(f"  Average price:   R$ {sum(prices)/len(prices):,.2f}")
    print(f"  With ratings:    {len(rated)}/{len(products)}")
    if rated:
        avg_rating = sum(r.rating for r in rated) / len(rated)
        print(f"  Avg rating:      {avg_rating:.1f} ★")
    print(f"{'='*60}\n")


# --- CLI ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape product listings from Mercado Livre",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mercadolivre_scraper.py "iphone 15"
  python mercadolivre_scraper.py "notebook gamer" --pages 5 --output notebooks.csv
  python mercadolivre_scraper.py "cadeira gamer" --format json --sort price_asc
        """,
    )
    parser.add_argument("query", help="Search term (e.g. 'geladeira consul 300L')")
    parser.add_argument("--pages", type=int, default=3, help="Max pages to scrape (default: 3)")
    parser.add_argument("--output", "-o", default=None, help="Output file path (default: auto-generated)")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv", help="Output format (default: csv)")
    parser.add_argument("--sort", choices=["relevance", "price_asc"], default="relevance", help="Sort order")

    args = parser.parse_args()

    print(f"\n  Mercado Livre Scraper")
    print(f"  Query: '{args.query}' | Pages: {args.pages} | Sort: {args.sort}\n")

    products = scrape_mercadolivre(
        query=args.query,
        max_pages=args.pages,
        sort=args.sort,
    )

    print_summary(products)

    # Output
    if not args.output:
        safe_name = args.query.replace(" ", "_")[:30]
        args.output = f"ml_{safe_name}.{args.format}"

    if args.format == "json":
        save_json(products, args.output)
    else:
        save_csv(products, args.output)


if __name__ == "__main__":
    main()
