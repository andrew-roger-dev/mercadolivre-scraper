# 🛒 Mercado Livre Product Scraper

A fast, reliable Python scraper that extracts product listings from [Mercado Livre](https://www.mercadolivre.com.br) search results.

Built with anti-detection in mind: randomized User-Agents, realistic browser headers, and polite request delays.

## Features

- **Multi-page scraping** — follow pagination automatically
- **Rich data extraction** — title, price, original price, discount %, seller, rating, reviews, shipping, condition, URL
- **Anti-detection** — rotating User-Agents, full browser header simulation, configurable delays
- **Multiple output formats** — CSV, JSON
- **Sort options** — by relevance or lowest price
- **Summary stats** — price range, average, rating distribution

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Basic usage
python mercadolivre_scraper.py "geladeira consul"

# Advanced: 5 pages, sorted by price, JSON output
python mercadolivre_scraper.py "notebook gamer" --pages 5 --sort price_asc --format json

# Custom output file
python mercadolivre_scraper.py "iphone 15" --pages 3 --output iphones.csv
```

## Output Example

| title | price | original_price | discount_pct | seller | rating | reviews_count | shipping | url |
|-------|-------|----------------|--------------|--------|--------|---------------|----------|-----|
| Geladeira Consul Frost Free 300L | 2299.00 | 2899.00 | 20% OFF | Consul Oficial | 4.7 | 1523 | Frete grátis | https://... |
| Geladeira Consul CRB36 | 1899.90 | — | — | Loja Premium | 4.5 | 892 | Full | https://... |

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Product title |
| `price` | float | Current price in BRL |
| `original_price` | float\|null | Price before discount |
| `discount_pct` | string\|null | Discount percentage (e.g. "20% OFF") |
| `seller` | string\|null | Seller or store name |
| `rating` | float\|null | Average rating (0-5) |
| `reviews_count` | int\|null | Number of reviews |
| `shipping` | string\|null | Shipping info (e.g. "Frete grátis") |
| `condition` | string\|null | New/Used |
| `url` | string | Direct link to listing |

## Architecture

```
mercadolivre_scraper.py
├── HTTP Layer        → Session management, headers, retries
├── Parsing Layer     → BeautifulSoup selectors (multiple fallbacks per field)
├── Data Layer        → Dataclass model, type conversion
└── Output Layer      → CSV / JSON serialization + summary stats
```

The scraper uses **multiple CSS selector fallbacks** per field to handle Mercado Livre's frequent layout changes. If one selector breaks, alternatives kick in automatically.

## Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`

## Disclaimer

This tool is for educational and personal research purposes. Respect the website's `robots.txt` and Terms of Service. Use responsibly and with reasonable request rates.

## License

MIT
