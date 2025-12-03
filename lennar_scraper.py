#!/usr/bin/env python3
"""
Lennar Homebuilders Listings Scraper

Uses Lennar's find-a-home search with market codes loaded from CSV.
Uses Selenium to handle JavaScript rendering and "Load more" pagination.

Extracts:
- Address
- Price
- Beds, Baths, Sq Ft
- Community name
- Status (Move-In Ready, Under Construction, etc.)
- Market/Region
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LennarListing:
    """Data class representing a Lennar home listing."""
    address: str = ""
    city: str = ""
    state: str = ""
    price: str = ""
    price_numeric: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    community: str = ""
    status: str = ""
    market: str = ""
    market_code: str = ""
    url: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


def load_market_codes(csv_path: str = None) -> dict:
    """
    Load market codes from CSV file.

    Args:
        csv_path: Path to market_codes.csv (default: same directory as script)

    Returns:
        Dict of {state_abbr: {market_code: market_name}}
    """
    if csv_path is None:
        # Look for CSV in same directory as script
        script_dir = Path(__file__).parent
        csv_path = script_dir / "market_codes.csv"

    market_codes = {}

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                state = row['state_abbr']
                code = row['market_code']
                region = row['city_region']

                if state not in market_codes:
                    market_codes[state] = {}
                market_codes[state][code] = region

        logger.info(f"Loaded {sum(len(m) for m in market_codes.values())} markets from {len(market_codes)} states")
        return market_codes

    except FileNotFoundError:
        logger.warning(f"Market codes CSV not found at {csv_path}, using fallback")
        return get_fallback_market_codes()


def get_fallback_market_codes() -> dict:
    """Fallback market codes if CSV is not found."""
    return {
        "FL": {
            "TMP": "Tampa / Manatee",
            "ORL": "Orlando",
            "JAX": "Jacksonville / St. Augustine",
            "MIA": "Miami",
            "FTL": "Ft. Lauderdale"
        },
        "TX": {
            "DFW": "Dallas / Ft. Worth",
            "HOU": "Houston",
            "AUS": "Austin / Central Texas",
            "SAT": "San Antonio"
        },
        "AZ": {
            "PHX": "Phoenix",
            "TUC": "Tucson"
        }
    }


# State name to abbreviation mapping
STATE_ABBREV = {
    "alabama": "AL", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "kansas": "KS",
    "maryland": "MD", "minnesota": "MN", "missouri": "MO", "nevada": "NV",
    "new jersey": "NJ", "new-jersey": "NJ", "new york": "NY", "new-york": "NY",
    "north carolina": "NC", "north-carolina": "NC", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "south carolina": "SC",
    "south-carolina": "SC", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "west-virginia": "WV", "wisconsin": "WI"
}


class LennarScraper:
    """Lennar scraper using search API with market codes."""

    BASE_URL = "https://www.lennar.com"
    SEARCH_URL = "https://www.lennar.com/find-a-home"

    def __init__(self, chrome_path: str = None, headless: bool = True,
                 wait_timeout: int = 15, page_load_delay: float = 3.0,
                 market_codes_csv: str = None):
        """
        Initialize the scraper.

        Args:
            chrome_path: Path to chromedriver (optional, uses webdriver-manager if not provided)
            headless: Run browser in headless mode
            wait_timeout: Selenium wait timeout in seconds
            page_load_delay: Delay after page load in seconds
            market_codes_csv: Path to market codes CSV file
        """
        self.chrome_path = chrome_path
        self.headless = headless
        self.wait_timeout = wait_timeout
        self.page_load_delay = page_load_delay
        self.driver = None
        self.listings: list[LennarListing] = []

        # Load market codes from CSV
        self.market_codes = load_market_codes(market_codes_csv)

    def _setup_driver(self):
        """Initialize Selenium WebDriver."""
        if self.driver is not None:
            return

        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Use provided path or webdriver-manager
        if self.chrome_path:
            service = Service(self.chrome_path)
        else:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            except ImportError:
                logger.warning("webdriver-manager not installed, trying default chromedriver")
                service = Service()

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("WebDriver initialized")

    def _accept_cookies(self):
        """Handle cookie consent popup."""
        try:
            wait = WebDriverWait(self.driver, 5)
            accept_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
            accept_btn.click()
            logger.debug("Accepted cookies")
            time.sleep(0.5)
        except TimeoutException:
            logger.debug("No cookie popup found")

    def _load_all_homes(self, max_clicks: int = 100) -> int:
        """
        Click "Load more homes" button until all homes are loaded.

        Args:
            max_clicks: Maximum number of times to click the button

        Returns:
            Number of times the button was clicked
        """
        click_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 3

        while click_count < max_clicks and consecutive_failures < max_consecutive_failures:
            try:
                # Wait for the button with longer timeout
                load_more = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "button[data-testid='search-results-load-more-button']"))
                )

                # Check if button is visible and enabled
                if not load_more.is_displayed():
                    logger.debug("Load more button not visible, all homes loaded")
                    break

                # Scroll button into view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    load_more
                )
                time.sleep(1)

                # Try to click
                try:
                    load_more.click()
                except ElementClickInterceptedException:
                    # Try JavaScript click as fallback
                    self.driver.execute_script("arguments[0].click();", load_more)

                click_count += 1
                consecutive_failures = 0
                logger.debug(f"Clicked 'Load more homes' (#{click_count})")

                # Wait for new content to load
                time.sleep(2)

            except TimeoutException:
                consecutive_failures += 1
                logger.debug(f"Load more button not found (attempt {consecutive_failures})")
                time.sleep(1)
            except NoSuchElementException:
                logger.debug("Load more button no longer exists")
                break
            except Exception as e:
                logger.warning(f"Error clicking load more: {e}")
                consecutive_failures += 1
                time.sleep(1)

        return click_count

    def _scroll_to_load_all(self):
        """Scroll through the page to ensure lazy-loaded content appears."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10

        while scroll_attempts < max_scroll_attempts:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            # Check if we've reached the bottom
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_height = new_height

        # Scroll back to top
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

    def _parse_listings(self, soup: BeautifulSoup, state: str,
                        market_code: str, market_name: str) -> list[LennarListing]:
        """
        Parse home listings from the page HTML.

        Args:
            soup: BeautifulSoup object of the page
            state: State abbreviation
            market_code: Market code
            market_name: Market name

        Returns:
            List of parsed listings
        """
        listings = []

        # Find all price blocks as entry points
        price_blocks = soup.find_all("div", string=lambda text: text and "$" in text)
        logger.debug(f"Found {len(price_blocks)} price blocks")

        for price_block in price_blocks:
            try:
                listing = LennarListing()
                listing.state = state
                listing.market_code = market_code
                listing.market = market_name

                # Get price
                listing.price = price_block.text.strip()
                listing.price_numeric = self._parse_price(listing.price)

                # Find parent card - look for InfoCard or similar container
                card = price_block.find_parent("div", class_=lambda x: x and "InfoCard" in x)
                if not card:
                    # Try alternative parent patterns
                    card = price_block.find_parent("div", class_=lambda x: x and ("card" in x.lower() or "listing" in x.lower()))
                if not card:
                    # Go up a few levels
                    card = price_block
                    for _ in range(5):
                        if card.parent:
                            card = card.parent
                        if card.name == "article" or (card.get("class") and any("card" in c.lower() for c in card.get("class", []))):
                            break

                if not card:
                    continue

                # Extract address
                addr_elem = card.find("div", class_=lambda x: x and "address" in x.lower()) if card else None
                if addr_elem:
                    listing.address = addr_elem.text.strip()
                    # Try to extract city from address
                    city_match = re.search(r',\s*([^,]+),\s*[A-Z]{2}', listing.address)
                    if city_match:
                        listing.city = city_match.group(1).strip()

                # Extract details (beds, baths, sqft)
                details_elem = card.find("div", class_=lambda x: x and "metaDetails" in x) if card else None
                if details_elem:
                    raw_details = details_elem.text.strip()
                    self._parse_details(listing, raw_details)

                # Extract community
                comm_elem = card.find("span", class_=lambda x: x and "newDescription" in x) if card else None
                if not comm_elem:
                    comm_elem = card.find("div", class_=lambda x: x and ("community" in x.lower() or "description" in x.lower())) if card else None
                if comm_elem:
                    listing.community = comm_elem.text.strip()

                # Extract status
                status_elem = card.find("div", class_=lambda x: x and ("status" in x.lower() or "pill" in x.lower())) if card else None
                if status_elem:
                    listing.status = status_elem.text.strip()
                else:
                    # Check for status keywords in card text
                    card_text = card.get_text().lower() if card else ""
                    if "move-in ready" in card_text or "quick move" in card_text:
                        listing.status = "Move-In Ready"
                    elif "under construction" in card_text:
                        listing.status = "Under Construction"
                    elif "coming soon" in card_text:
                        listing.status = "Coming Soon"

                # Extract URL
                link = card.find("a", href=True) if card else None
                if link:
                    href = link.get("href", "")
                    if href.startswith("/"):
                        listing.url = f"{self.BASE_URL}{href}"
                    elif href.startswith("http"):
                        listing.url = href

                # Only add if we have meaningful data
                if listing.price and (listing.address or listing.community):
                    listings.append(listing)

            except Exception as e:
                logger.debug(f"Error parsing listing: {e}")

        return listings

    def _parse_price(self, price_text: str) -> Optional[int]:
        """Extract numeric price from price text."""
        clean = re.sub(r'[^\d]', '', price_text)
        if clean:
            try:
                return int(clean)
            except ValueError:
                pass
        return None

    def _parse_details(self, listing: LennarListing, details_text: str):
        """Parse beds, baths, sqft from details string."""
        # Bedrooms
        bed_match = re.search(r'(\d+)\s*bd', details_text, re.IGNORECASE)
        if bed_match:
            listing.bedrooms = int(bed_match.group(1))

        # Bathrooms
        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*ba', details_text, re.IGNORECASE)
        if bath_match:
            listing.bathrooms = float(bath_match.group(1))

        # Square feet
        sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*)?ft', details_text, re.IGNORECASE)
        if sqft_match:
            listing.sqft = int(sqft_match.group(1).replace(',', ''))

    def scrape_market(self, state: str, market_code: str,
                      market_name: str) -> list[LennarListing]:
        """
        Scrape all listings from a specific market.

        Args:
            state: State abbreviation (e.g., "FL")
            market_code: Market code (e.g., "TMP")
            market_name: Market name (e.g., "Tampa / Manatee")

        Returns:
            List of listings from this market
        """
        self._setup_driver()

        url = f"{self.SEARCH_URL}?state={state}&market={market_code}"
        logger.info(f"Scraping {market_name} ({state}/{market_code})...")

        self.driver.get(url)
        time.sleep(self.page_load_delay)

        # Handle cookie popup
        self._accept_cookies()

        # Load all homes by clicking "Load more"
        clicks = self._load_all_homes()
        logger.info(f"Clicked 'Load more' {clicks} times")

        # Additional scroll to ensure all content is loaded
        self._scroll_to_load_all()

        # Wait a bit more for any final content
        time.sleep(2)

        # Parse the page
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        listings = self._parse_listings(soup, state, market_code, market_name)

        logger.info(f"Found {len(listings)} listings in {market_name}")
        return listings

    def scrape_state(self, state: str) -> list[LennarListing]:
        """
        Scrape all markets in a state.

        Args:
            state: State name or abbreviation

        Returns:
            List of all listings from the state
        """
        # Normalize state to abbreviation
        state_upper = state.upper()
        if len(state_upper) != 2:
            state_upper = STATE_ABBREV.get(state.lower(), state.upper()[:2])

        if state_upper not in self.market_codes:
            logger.warning(f"No market codes found for state: {state}")
            return []

        markets = self.market_codes[state_upper]
        all_listings = []

        for code, name in tqdm(markets.items(), desc=f"Markets in {state_upper}"):
            try:
                listings = self.scrape_market(state_upper, code, name)
                all_listings.extend(listings)
            except Exception as e:
                logger.error(f"Error scraping {name}: {e}")

        return all_listings

    def scrape_all(self, states: list[str] = None) -> list[LennarListing]:
        """
        Scrape all listings from specified states (or all states).

        Args:
            states: List of states to scrape (None for all)

        Returns:
            List of all scraped listings
        """
        if states:
            states_to_scrape = states
        else:
            states_to_scrape = list(self.market_codes.keys())

        all_listings = []

        for state in tqdm(states_to_scrape, desc="States"):
            try:
                listings = self.scrape_state(state)
                all_listings.extend(listings)
            except Exception as e:
                logger.error(f"Error scraping state {state}: {e}")

        self.listings = all_listings
        return all_listings

    def get_available_states(self) -> list[str]:
        """Return list of available state abbreviations."""
        return sorted(self.market_codes.keys())

    def get_markets_for_state(self, state: str) -> dict:
        """Return market codes for a specific state."""
        state_upper = state.upper()
        if len(state_upper) != 2:
            state_upper = STATE_ABBREV.get(state.lower(), state.upper()[:2])
        return self.market_codes.get(state_upper, {})

    def export_to_csv(self, filepath: str = "lennar_listings.csv") -> str:
        """Export listings to CSV."""
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        fieldnames = [
            'address', 'city', 'state', 'price', 'price_numeric',
            'bedrooms', 'bathrooms', 'sqft', 'community', 'status',
            'market', 'market_code', 'url', 'scraped_at'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for listing in self.listings:
                writer.writerow(asdict(listing))

        logger.info(f"Exported {len(self.listings)} listings to {filepath}")
        return filepath

    def export_to_excel(self, filepath: str = "lennar_listings.xlsx") -> str:
        """Export listings to Excel."""
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas not installed, cannot export to Excel")
            return ""

        if not self.listings:
            logger.warning("No listings to export")
            return ""

        df = pd.DataFrame([asdict(l) for l in self.listings])
        df.to_excel(filepath, index=False)
        logger.info(f"Exported {len(self.listings)} listings to {filepath}")
        return filepath

    def export_to_json(self, filepath: str = "lennar_listings.json") -> str:
        """Export listings to JSON."""
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        data = {
            'scraped_at': datetime.now().isoformat(),
            'total_listings': len(self.listings),
            'listings': [asdict(l) for l in self.listings]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(self.listings)} listings to {filepath}")
        return filepath

    def close(self):
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    parser = argparse.ArgumentParser(
        description='Scrape Lennar Homebuilders listings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all Florida markets
  python lennar_scraper.py --states FL

  # Scrape specific states
  python lennar_scraper.py --states FL TX AZ

  # Scrape specific market
  python lennar_scraper.py --state FL --market TMP

  # Scrape all states
  python lennar_scraper.py --all

  # List available states and markets
  python lennar_scraper.py --list-states
  python lennar_scraper.py --list-markets FL

  # Show browser window (not headless)
  python lennar_scraper.py --states FL --no-headless

Market codes are loaded from market_codes.csv in the same directory.
        """
    )

    parser.add_argument('--states', nargs='+', help='States to scrape (abbreviations)')
    parser.add_argument('--state', help='Single state for market-specific scraping')
    parser.add_argument('--market', help='Specific market code to scrape')
    parser.add_argument('--all', action='store_true', help='Scrape all states')
    parser.add_argument('--list-states', action='store_true', help='List available states')
    parser.add_argument('--list-markets', metavar='STATE', help='List markets for a state')
    parser.add_argument('--market-codes-csv', help='Path to market codes CSV file')
    parser.add_argument('--chrome-path', help='Path to chromedriver executable')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    parser.add_argument('--output-csv', default='lennar_listings.csv', help='Output CSV file')
    parser.add_argument('--output-excel', help='Output Excel file (optional)')
    parser.add_argument('--output-json', default='lennar_listings.json', help='Output JSON file')
    parser.add_argument('--timeout', type=int, default=15, help='Selenium wait timeout')
    parser.add_argument('--delay', type=float, default=3.0, help='Page load delay')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = LennarScraper(
        chrome_path=args.chrome_path,
        headless=not args.no_headless,
        wait_timeout=args.timeout,
        page_load_delay=args.delay,
        market_codes_csv=args.market_codes_csv
    )

    try:
        # Handle info commands
        if args.list_states:
            print("Available states:")
            for state in scraper.get_available_states():
                markets = scraper.get_markets_for_state(state)
                print(f"  {state}: {len(markets)} markets")
            return

        if args.list_markets:
            state = args.list_markets.upper()
            markets = scraper.get_markets_for_state(state)
            if markets:
                print(f"Markets in {state}:")
                for code, name in sorted(markets.items()):
                    print(f"  {code}: {name}")
            else:
                print(f"No markets found for state: {state}")
            return

        # Handle scraping commands
        if args.state and args.market:
            # Scrape specific market
            state = args.state.upper()
            market = args.market.upper()
            market_name = scraper.market_codes.get(state, {}).get(market, market)
            listings = scraper.scrape_market(state, market, market_name)
            scraper.listings = listings

        elif args.states:
            # Scrape specified states
            scraper.scrape_all(args.states)

        elif args.all:
            # Scrape everything
            scraper.scrape_all()

        else:
            print("No states specified. Use --states, --all, or --state with --market")
            print("Use --list-states to see available states")
            print("Example: python lennar_scraper.py --states FL TX")
            return

        # Export results
        if scraper.listings:
            scraper.export_to_csv(args.output_csv)
            scraper.export_to_json(args.output_json)
            if args.output_excel:
                scraper.export_to_excel(args.output_excel)

            print(f"\n{'='*60}")
            print("Scraping Complete!")
            print(f"{'='*60}")
            print(f"Total listings found: {len(scraper.listings)}")
            print(f"CSV output: {args.output_csv}")
            print(f"JSON output: {args.output_json}")
            if args.output_excel:
                print(f"Excel output: {args.output_excel}")

            # Show breakdown by market
            market_counts = {}
            for l in scraper.listings:
                key = f"{l.state}/{l.market_code}"
                market_counts[key] = market_counts.get(key, 0) + 1

            print(f"\nListings by market:")
            for market, count in sorted(market_counts.items()):
                print(f"  {market}: {count}")

            print(f"{'='*60}")
        else:
            print("\nNo listings found.")

    except KeyboardInterrupt:
        print("\nScraping interrupted")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise
    finally:
        scraper.close()


if __name__ == '__main__':
    main()
