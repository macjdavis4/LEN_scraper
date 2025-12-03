# Lennar Homebuilders Listings Scraper

A Python-based web scraper for collecting Lennar Homebuilders listings from multiple sources (Lennar.com and Zillow).

## Features

- **Multi-source scraping**: Scrape from Lennar.com directly or Zillow's builder profiles
- **Comprehensive data extraction**:
  - Location (address, city, state, zip code)
  - House type (single family, townhome, condo)
  - Price (formatted and numeric)
  - Community name
  - Bedrooms, bathrooms, square footage
  - Listing status and URLs
- **Flexible filtering**: Filter by state, location, price range
- **Multiple export formats**: CSV and JSON output
- **Selenium support**: Handle JavaScript-rendered content
- **Rate limiting**: Configurable delays to avoid blocking

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd LEN_scraper

# Install dependencies
pip install -r requirements.txt
```

### Requirements

- Python 3.9+
- Chrome/Chromium browser (for Selenium mode)

## Usage

### Quick Start

```bash
# Scrape from both sources (default)
python scrape.py --states texas florida

# Quick test with limited communities
python scrape.py --states california --max-communities 3
```

### Unified Scraper (Recommended)

The `scrape.py` script provides a unified interface:

```bash
# Scrape from both Lennar.com and Zillow
python scrape.py --both --states texas arizona

# Scrape only from Lennar.com
python scrape.py --source lennar --states florida

# Scrape only from Zillow with specific cities
python scrape.py --source zillow --locations "Dallas, TX" "Houston, TX"

# Use Selenium for JavaScript-heavy pages
python scrape.py --both --selenium --states california

# Custom output files
python scrape.py --states texas --output-csv my_listings.csv --output-json my_listings.json
```

### Lennar.com Direct Scraper

```bash
# Scrape specific states
python lennar_scraper.py --states texas florida california

# Limit communities per state
python lennar_scraper.py --states texas --max-communities 5

# Use Selenium for better JavaScript support
python lennar_scraper.py --selenium --states arizona

# Search mode with filters
python lennar_scraper.py --search --location "Dallas, TX" --min-price 300000 --max-price 500000
```

### Zillow Scraper

```bash
# Search specific locations
python zillow_lennar_scraper.py --locations "Phoenix, AZ" "Las Vegas, NV"

# Scrape Lennar's builder profile page
python zillow_lennar_scraper.py --profile

# Use Selenium for better results
python zillow_lennar_scraper.py --selenium --locations "Miami, FL"
```

## Command Line Options

### scrape.py (Unified)

| Option | Description |
|--------|-------------|
| `--source {lennar,zillow}` | Use single data source |
| `--both` | Use both sources (default) |
| `--states STATE [STATE ...]` | State slugs to scrape (e.g., texas florida) |
| `--locations LOC [LOC ...]` | Specific locations for Zillow |
| `--max-communities N` | Max communities per state |
| `--selenium` | Use Selenium for JS rendering |
| `--no-headless` | Show browser window |
| `--delay SECONDS` | Delay between requests (default: 1.5) |
| `--output-csv FILE` | Output CSV file path |
| `--output-json FILE` | Output JSON file path |
| `-v, --verbose` | Enable verbose logging |

### lennar_scraper.py

| Option | Description |
|--------|-------------|
| `--states STATE [STATE ...]` | States to scrape |
| `--max-communities N` | Limit communities per state |
| `--search` | Enable search mode |
| `--location LOCATION` | Location for search |
| `--min-price PRICE` | Minimum price filter |
| `--max-price PRICE` | Maximum price filter |
| `--bedrooms N` | Minimum bedrooms |
| `--house-type TYPE` | House type filter |

## Output Format

### CSV Output

```csv
community_name,location,city,state,zip_code,price,price_numeric,house_type,bedrooms,bathrooms,sqft,status,plan_name,url,scraped_at
"Sunset Valley","123 Main St","Austin","TX","78701","$450,000",450000,"Single Family","4","3","2500","Move-In Ready","The Hampton","https://...","2024-01-15T10:30:00"
```

### JSON Output

```json
{
  "scraped_at": "2024-01-15T10:30:00",
  "total_listings": 150,
  "listings": [
    {
      "community_name": "Sunset Valley",
      "location": "123 Main St",
      "city": "Austin",
      "state": "TX",
      "zip_code": "78701",
      "price": "$450,000",
      "price_numeric": 450000,
      "house_type": "Single Family",
      "bedrooms": "4",
      "bathrooms": "3",
      "sqft": "2500",
      "status": "Move-In Ready",
      "plan_name": "The Hampton",
      "url": "https://...",
      "scraped_at": "2024-01-15T10:30:00"
    }
  ]
}
```

## Supported States

The scraper covers all states where Lennar operates:

- Arizona, California, Colorado, Florida, Georgia
- Idaho, Indiana, Maryland, Minnesota, Nevada
- New Jersey, North Carolina, Oregon, South Carolina
- Tennessee, Texas, Utah, Virginia, Washington

## Troubleshooting

### No listings found

1. **Enable Selenium mode**: Use `--selenium` flag for JavaScript-heavy pages
2. **Check rate limiting**: Increase delay with `--delay 3.0`
3. **Try Zillow source**: Use `--source zillow` as an alternative

### Selenium not working

1. Ensure Chrome/Chromium is installed
2. The webdriver-manager package auto-downloads the correct ChromeDriver
3. For headless issues, try `--no-headless` to see the browser

### Getting blocked

1. Increase delay between requests: `--delay 5.0`
2. The scraper automatically rotates User-Agent headers
3. Consider using a proxy (not included by default)

## Legal Considerations

This scraper is intended for personal use and research purposes. Please:

- Respect the websites' Terms of Service
- Use reasonable request rates to avoid overloading servers
- Don't use scraped data for commercial purposes without permission
- Be aware that web scraping may be subject to legal restrictions in your jurisdiction

## Project Structure

```
LEN_scraper/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── scrape.py             # Unified scraper CLI
├── lennar_scraper.py     # Lennar.com direct scraper
└── zillow_lennar_scraper.py  # Zillow-based scraper
```

## License

MIT License - See LICENSE file for details.
