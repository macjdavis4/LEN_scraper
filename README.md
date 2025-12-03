# Lennar Homebuilders Listings Scraper

A Python-based web scraper for collecting Lennar Homebuilders listings from lennar.com using their search API with market codes.

## Features

- **Market-based scraping**: Uses Lennar's internal search API with market codes for comprehensive coverage
- **Full pagination handling**: Automatically clicks "Load more homes" to get all listings
- **Status extraction**: Captures home status (Move-In Ready, Under Construction, Coming Soon)
- **Comprehensive data**:
  - Address and city
  - Price (formatted and numeric)
  - Beds, baths, square footage
  - Community name
  - Status
  - Market/Region info
- **Multiple export formats**: CSV, JSON, and Excel
- **All US markets supported**: FL, TX, AZ, CA, CO, GA, ID, IN, MD, MN, NV, NJ, NC, OR, SC, TN, UT, VA, WA

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
- Chrome/Chromium browser
- ChromeDriver (auto-downloaded via webdriver-manager, or provide path manually)

## Usage

### Scrape All Florida Markets

```bash
python lennar_scraper.py --states FL
```

### Scrape Multiple States

```bash
python lennar_scraper.py --states FL TX AZ CA
```

### Scrape a Specific Market

```bash
python lennar_scraper.py --state FL --market TAM
```

### Scrape All States

```bash
python lennar_scraper.py --all
```

### Show Browser Window (Debug Mode)

```bash
python lennar_scraper.py --states FL --no-headless
```

### Export to Excel

```bash
python lennar_scraper.py --states FL --output-excel lennar_fl.xlsx
```

### Use Custom ChromeDriver Path

```bash
python lennar_scraper.py --states FL --chrome-path "C:\path\to\chromedriver.exe"
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--states STATE [STATE ...]` | States to scrape (abbreviations: FL, TX, etc.) |
| `--state STATE` | Single state (use with --market) |
| `--market CODE` | Specific market code (use with --state) |
| `--all` | Scrape all states |
| `--chrome-path PATH` | Path to chromedriver executable |
| `--no-headless` | Show browser window |
| `--output-csv FILE` | Output CSV file (default: lennar_listings.csv) |
| `--output-json FILE` | Output JSON file (default: lennar_listings.json) |
| `--output-excel FILE` | Output Excel file (optional) |
| `--timeout SECONDS` | Selenium wait timeout (default: 15) |
| `--delay SECONDS` | Page load delay (default: 3.0) |
| `-v, --verbose` | Enable verbose/debug logging |

## Market Codes

### Florida (FL)
| Code | Market |
|------|--------|
| TAM | Tampa and Manatee |
| TRE | Treasure Coast |
| ORL | Orlando |
| OCA | Ocala |
| JAX | Jacksonville |
| PEN | Gulf Coast |
| SPA | Space Coast |
| SAR | Sarasota |
| FTM | Fort Myers |
| PLM | Palm Beach |
| FTL | Fort Lauderdale |
| MIA | Miami |

### Texas (TX)
| Code | Market |
|------|--------|
| DAL | Dallas/Fort Worth |
| HOU | Houston |
| AUS | Austin |
| SAN | San Antonio |

### Arizona (AZ)
| Code | Market |
|------|--------|
| PHO | Phoenix |
| TUC | Tucson |

### California (CA)
| Code | Market |
|------|--------|
| BAY | Bay Area |
| SAC | Sacramento |
| LAX | Los Angeles |
| SBD | Inland Empire |
| SDG | San Diego |
| ORA | Orange County |

### Other States
See `MARKET_CODES` dictionary in `lennar_scraper.py` for complete list.

## Output Format

### CSV/Excel Columns

| Column | Description |
|--------|-------------|
| address | Full street address |
| city | City name |
| state | State abbreviation |
| price | Formatted price (e.g., "$450,000") |
| price_numeric | Numeric price for sorting/filtering |
| bedrooms | Number of bedrooms |
| bathrooms | Number of bathrooms |
| sqft | Square footage |
| community | Community/subdivision name |
| status | Move-In Ready, Under Construction, etc. |
| market | Market name |
| market_code | Market code (TAM, ORL, etc.) |
| url | Link to listing page |
| scraped_at | Timestamp of scrape |

### JSON Output

```json
{
  "scraped_at": "2024-01-15T10:30:00",
  "total_listings": 150,
  "listings": [
    {
      "address": "123 Palm Dr",
      "city": "Tampa",
      "state": "FL",
      "price": "$450,000",
      "price_numeric": 450000,
      "bedrooms": 4,
      "bathrooms": 3.0,
      "sqft": 2500,
      "community": "Sunset Valley",
      "status": "Move-In Ready",
      "market": "Tampa and Manatee",
      "market_code": "TAM",
      "url": "https://www.lennar.com/...",
      "scraped_at": "2024-01-15T10:30:00"
    }
  ]
}
```

## Troubleshooting

### Missing Homes in Some Markets

The scraper includes improvements over basic approaches:
- Extended wait times for AJAX content
- Multiple attempts for "Load more" button
- Additional scrolling to trigger lazy loading
- JavaScript click fallback when normal click fails

If you're still missing homes, try:
```bash
python lennar_scraper.py --states FL --delay 5.0 --timeout 20 --no-headless
```

### ChromeDriver Issues

If ChromeDriver auto-download fails:
1. Download ChromeDriver manually from https://chromedriver.chromium.org/
2. Use `--chrome-path` to specify the location

### Blocked/Timeout Errors

- Increase delays: `--delay 5.0`
- Run in non-headless mode to debug: `--no-headless`
- Check your internet connection

## Project Structure

```
LEN_scraper/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── lennar_scraper.py     # Main scraper
└── .gitignore            # Git ignore file
```

## How It Works

1. **URL Construction**: Uses `https://www.lennar.com/find-a-home?state=XX&market=YYY`
2. **Cookie Handling**: Automatically accepts cookie consent popup
3. **Pagination**: Clicks "Load more homes" button repeatedly until all homes are loaded
4. **Parsing**: Finds price blocks and navigates to parent cards to extract all data
5. **Status Detection**: Looks for status/pill elements or keywords in card text

## Legal Considerations

This scraper is intended for personal use and research purposes. Please:
- Respect Lennar's Terms of Service
- Use reasonable request rates
- Don't use scraped data for commercial purposes without permission

## License

MIT License
