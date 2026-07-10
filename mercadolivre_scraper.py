"""
Mercado Livre Product Scraper
Extracts product data using headless Edge browser to bypass bot detection.

Usage:
    python mercadolivre_scraper.py "geladeira consul" --pages 3
    python mercadolivre_scraper.py "iphone 15" --format json --sort price_asc

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

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager


@dataclass
class Product:
    title: str
    price: float
    original_price: Optional[float]
    discount_pct: Optional[str]
    seller: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    shipping: Optional[str]
    url: str


DELAY_RANGE = (2.0, 4.0)
PAGE_LOAD_TIMEOUT = 15


def create_driver(headless=True):
    options = EdgeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    service = EdgeService(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    })
    return driver


def parse_price(text):
    if not text:
        return None
    cleaned = text.replace("R$", "").replace("\xa0", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def safe_text(element, selector):
    try:
        el = element.find_element(By.CSS_SELECTOR, selector)
        return el.text.strip()
    except:
        return None


def extract_product(item):
    try:
        title = None
        for sel in [".ui-search-item__title", "h2 a", "h2", "[class*='title']"]:
            title = safe_text(item, sel)
            if title:
                break
        if not title:
            return None

        url = ""
        try:
            link = item.find_element(By.CSS_SELECTOR, "a[href*='mercadolivre'], a[href*='mercadolibre'], a[href]")
            url = link.get_attribute("href") or ""
        except:
            pass

        price_text = safe_text(item, ".andes-money-amount__fraction")
        if not price_text:
            return None
        cents_text = safe_text(item, ".andes-money-amount__cents") or "00"
        price = parse_price(f"{price_text},{cents_text}")
        if price is None:
            return None

        original_price = None
        orig_text = safe_text(item, "s .andes-money-amount__fraction")
        if orig_text:
            original_price = parse_price(orig_text)

        discount_pct = safe_text(item, "[class*='discount']")
        seller = safe_text(item, "[class*='seller']") or safe_text(item, "[class*='official-store']")

        rating = None
        rating_text = safe_text(item, "[class*='reviews__rating']")
        if rating_text:
            try:
                rating = float(rating_text.replace(",", "."))
            except ValueError:
                pass

        reviews_count = None
        reviews_text = safe_text(item, "[class*='reviews__total']") or safe_text(item, "[class*='reviews__amount']")
        if reviews_text:
            digits = "".join(c for c in reviews_text if c.isdigit())
            reviews_count = int(digits) if digits else None

        shipping = safe_text(item, "[class*='shipping']") or safe_text(item, "[class*='highlight']")

        return Product(
            title=title, price=price, original_price=original_price,
            discount_pct=discount_pct, seller=seller, rating=rating,
            reviews_count=reviews_count, shipping=shipping, url=url,
        )
    except:
        return None


def scrape_mercadolivre(query, max_pages=3, sort="relevance", headless=True):
    sort_param = ""
    if sort == "price_asc":
        sort_param = "_OrderId_PRICE_PriceRange_0-0"
    elif sort == "price_desc":
        sort_param = "_OrderId_PRICE*DESC"

    print(f"  [*] Starting browser (headless={headless})...")
    driver = create_driver(headless=headless)
    all_products = []

    try:
        for page in range(1, max_pages + 1):
            if page == 1:
                encoded = quote_plus(query)
                url = f"https://lista.mercadolivre.com.br/{encoded}{sort_param}"
            else:
                offset = (page - 1) * 50 + 1
                encoded = quote_plus(query)
                url = f"https://lista.mercadolivre.com.br/{encoded}{sort_param}_Desde_{offset}"

            print(f"  [*] Page {page}/{max_pages}: {url[:80]}...")
            driver.get(url)

            try:
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "li.ui-search-layout__item, div.ui-search-result, .poly-card, ol.ui-search-layout li"
                    ))
                )
            except:
                print(f"  [!] Timeout waiting for products on page {page}.")
                driver.save_screenshot(f"debug_page_{page}.png")
                print(f"  [DEBUG] Screenshot saved to debug_page_{page}.png")
                break

            time.sleep(1)

            items = []
            for sel in [
                "li.ui-search-layout__item",
                "div.ui-search-result__content-wrapper",
                "div.poly-card",
                "ol.ui-search-layout li",
            ]:
                items = driver.find_elements(By.CSS_SELECTOR, sel)
                if items:
                    break

            if not items:
                print(f"  [*] No product containers found on page {page}, stopping.")
                driver.save_screenshot(f"debug_page_{page}.png")
                print(f"  [DEBUG] Screenshot saved to debug_page_{page}.png")
                break

            parsed = 0
            for item in items:
                product = extract_product(item)
                if product:
                    all_products.append(product)
                    parsed += 1

            print(f"  [+] Extracted {parsed} products (total: {len(all_products)})")

            if page < max_pages:
                delay = random.uniform(*DELAY_RANGE)
                print(f"  [~] Waiting {delay:.1f}s...")
                time.sleep(delay)

    finally:
        driver.quit()
        print(f"  [*] Browser closed.")

    return all_products


def save_csv(products, filepath):
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


def save_json(products, filepath):
    if not products:
        print("  [!] No products to save.")
        return
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)
    print(f"  [✓] Saved {len(products)} products to {filepath}")


def print_summary(products):
    if not products:
        return
    prices = [p.price for p in products]
    rated = [p for p in products if p.rating]
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total products:  {len(products)}")
    print(f"  Price range:     R$ {min(prices):,.2f} — R$ {max(prices):,.2f}")
    print(f"  Average price:   R$ {sum(prices)/len(prices):,.2f}")
    if rated:
        avg_rating = sum(r.rating for r in rated) / len(rated)
        print(f"  Avg rating:      {avg_rating:.1f} ★ ({len(rated)} rated)")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape product listings from Mercado Livre",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mercadolivre_scraper.py "iphone 15"
  python mercadolivre_scraper.py "notebook gamer" --pages 5 -o notebooks.csv
  python mercadolivre_scraper.py "cadeira gamer" --format json --sort price_asc
  python mercadolivre_scraper.py "iphone 15" --visible
        """,
    )
    parser.add_argument("query", help="Search term")
    parser.add_argument("--pages", type=int, default=3, help="Max pages (default: 3)")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv")
    parser.add_argument("--sort", choices=["relevance", "price_asc", "price_desc"], default="relevance")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    args = parser.parse_args()

    print(f"\n  Mercado Livre Scraper")
    print(f"  Query: '{args.query}' | Pages: {args.pages} | Sort: {args.sort}\n")

    products = scrape_mercadolivre(args.query, args.pages, args.sort, headless=not args.visible)
    print_summary(products)

    if not args.output:
        safe_name = args.query.replace(" ", "_")[:30]
        args.output = f"ml_{safe_name}.{args.format}"

    if args.format == "json":
        save_json(products, args.output)
    else:
        save_csv(products, args.output)


if __name__ == "__main__":
    main()
