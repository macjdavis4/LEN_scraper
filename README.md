# Lennar Homebuilders Listings Scraper

A Python-based web scraper for collecting Lennar Homebuilders listings from lennar.com using their search API with market codes.

## Features

- **Market-based scraping**: Uses Lennar's search API with state/market parameters
- **CSV-driven market codes**: Easy to update market codes via `market_codes.csv`
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
- **All US markets supported**: 95 markets across 28 states

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

### Basic Commands

```bash
# Scrape all Florida markets
python lennar_scraper.py --states FL

# Scrape multiple states
python lennar_scraper.py --states FL TX AZ CA

# Scrape a specific market
python lennar_scraper.py --state FL --market TMP

# Scrape all states
python lennar_scraper.py --all
```

### List Available Markets

```bash
# List all states with market counts
python lennar_scraper.py --list-states

# List markets for a specific state
python lennar_scraper.py --list-markets FL
```

### Additional Options

```bash
# Show browser window (debug mode)
python lennar_scraper.py --states FL --no-headless

# Export to Excel
python lennar_scraper.py --states FL --output-excel lennar_fl.xlsx

# Use custom ChromeDriver path
python lennar_scraper.py --states FL --chrome-path "C:\path\to\chromedriver.exe"

# Verbose logging
python lennar_scraper.py --states FL -v
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--states STATE [STATE ...]` | States to scrape (abbreviations: FL, TX, etc.) |
| `--state STATE` | Single state (use with --market) |
| `--market CODE` | Specific market code (use with --state) |
| `--all` | Scrape all states |
| `--list-states` | List available states and market counts |
| `--list-markets STATE` | List markets for a state |
| `--market-codes-csv PATH` | Path to custom market codes CSV |
| `--chrome-path PATH` | Path to chromedriver executable |
| `--no-headless` | Show browser window |
| `--output-csv FILE` | Output CSV file (default: lennar_listings.csv) |
| `--output-json FILE` | Output JSON file (default: lennar_listings.json) |
| `--output-excel FILE` | Output Excel file (optional) |
| `--timeout SECONDS` | Selenium wait timeout (default: 15) |
| `--delay SECONDS` | Page load delay (default: 3.0) |
| `-v, --verbose` | Enable verbose/debug logging |

## Market Codes CSV

Market codes are loaded from `market_codes.csv`. Format:

```csv
state,state_abbr,city_region,market_code
Florida,FL,Tampa / Manatee,TMP
Florida,FL,Orlando,ORL
...
```

### Updating Market Codes

To add or modify markets, simply edit `market_codes.csv`. The scraper will automatically pick up changes on next run.

## Supported States (28 total)

| State | Abbr | Markets |
|-------|------|---------|
| Alabama | AL | 4 |
| Arizona | AZ | 2 |
| Arkansas | AR | 4 |
| California | CA | 9 |
| Colorado | CO | 3 |
| Delaware | DE | 2 |
| Florida | FL | 12 |
| Georgia | GA | 3 |
| Idaho | ID | 2 |
| Illinois | IL | 1 |
| Indiana | IN | 2 |
| Kansas | KS | 1 |
| Maryland | MD | 4 |
| Minnesota | MN | 2 |
| Missouri | MO | 1 |
| Nevada | NV | 2 |
| New Jersey | NJ | 1 |
| New York | NY | 1 |
| North Carolina | NC | 4 |
| Oklahoma | OK | 3 |
| Oregon | OR | 3 |
| Pennsylvania | PA | 2 |
| South Carolina | SC | 6 |
| Tennessee | TN | 2 |
| Texas | TX | 8 |
| Utah | UT | 2 |
| Virginia | VA | 3 |
| Washington | WA | 3 |
| West Virginia | WV | 2 |
| Wisconsin | WI | 1 |

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
| market_code | Market code (TMP, ORL, etc.) |
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
      "market": "Tampa / Manatee",
      "market_code": "TMP",
      "url": "https://www.lennar.com/...",
      "scraped_at": "2024-01-15T10:30:00"
    }
  ]
}
```

## Troubleshooting

### Missing Homes in Some Markets

If you're missing homes, try increasing delays:
```bash
python lennar_scraper.py --states FL --delay 5.0 --timeout 20 --no-headless
```

### ChromeDriver Issues

If ChromeDriver auto-download fails:
1. Download ChromeDriver manually from https://chromedriver.chromium.org/
2. Use `--chrome-path` to specify the location

### Market Code Not Found

If a market code isn't working:
1. Check `market_codes.csv` for the correct code
2. Use `--list-markets STATE` to see available markets
3. Update the CSV if Lennar has changed their codes

## Project Structure

```
LEN_scraper/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── market_codes.csv       # Market codes database (editable)
├── lennar_scraper.py     # Main scraper
└── .gitignore            # Git ignore file
```

## How It Works

1. **Load Markets**: Reads market codes from `market_codes.csv`
2. **URL Construction**: Uses `https://www.lennar.com/find-a-home?state=XX&market=YYY`
3. **Cookie Handling**: Automatically accepts cookie consent popup
4. **Pagination**: Clicks "Load more homes" button repeatedly until all homes are loaded
5. **Parsing**: Finds price blocks and navigates to parent cards to extract all data
6. **Status Detection**: Looks for status/pill elements or keywords in card text
7. **Export**: Saves to CSV, JSON, and optionally Excel

## Legal Considerations

This scraper is intended for personal use and research purposes. Please:
- Respect Lennar's Terms of Service
- Use reasonable request rates
- Don't use scraped data for commercial purposes without permission

## License

MIT License
