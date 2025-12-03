#!/usr/bin/env python3
"""
Zillow Lennar Listings Scraper

Alternative scraper that fetches Lennar homes from Zillow's platform.
Zillow has a builder profile page for Lennar that aggregates their listings.
"""

import argparse
import csv
import json
import logging
import re
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ZillowLennarListing:
    """Data class for Lennar listing from Zillow."""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    price: str = ""
    price_numeric: Optional[int] = None
    house_type: str = ""
    bedrooms: str = ""
    bathrooms: str = ""
    sqft: str = ""
    community_name: str = ""
    builder: str = "Lennar"
    status: str = ""
    listing_url: str = ""
    image_url: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ZillowLennarScraper:
    """Scraper for Lennar listings via Zillow."""

    ZILLOW_BASE = "https://www.zillow.com"
    LENNAR_BUILDER_ID = "11527"
    LENNAR_PROFILE_URL = f"{ZILLOW_BASE}/home-builder-profile/lennar-homes/{LENNAR_BUILDER_ID}/"

    # Zillow's internal API endpoints
    SEARCH_API = "https://www.zillow.com/search/GetSearchPageState.htm"

    def __init__(self, use_selenium: bool = False, headless: bool = True):
        """Initialize the Zillow scraper."""
        self.session = requests.Session()
        self.ua = UserAgent()
        self.use_selenium = use_selenium
        self.headless = headless
        self.driver = None
        self.listings: list[ZillowLennarListing] = []

        self._setup_session()

    def _setup_session(self):
        """Configure session headers to mimic browser."""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    def _setup_selenium(self):
        """Initialize Selenium WebDriver."""
        if self.driver is not None:
            return

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'--user-agent={self.ua.random}')
            options.add_argument('--window-size=1920,1080')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("Selenium WebDriver initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Selenium: {e}")
            raise

    def _make_request(self, url: str, params: dict = None,
                      retry_count: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with retries."""
        for attempt in range(retry_count):
            try:
                # Rotate user agent on each attempt
                self.session.headers['User-Agent'] = self.ua.random

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)

        return None

    def search_zillow_new_construction(self, location: str,
                                       builder_filter: bool = True) -> list[ZillowLennarListing]:
        """
        Search Zillow for new construction homes, optionally filtering by Lennar.

        Args:
            location: City, state, or zip code to search
            builder_filter: Filter results to Lennar only

        Returns:
            List of listings
        """
        listings = []

        # Construct search URL
        location_slug = quote(location.lower().replace(' ', '-').replace(',', ''))
        search_url = f"{self.ZILLOW_BASE}/{location_slug}/new-construction/"

        if self.use_selenium:
            html = self._scrape_with_selenium(search_url)
            soup = BeautifulSoup(html, 'lxml')
        else:
            response = self._make_request(search_url)
            if not response:
                return listings
            soup = BeautifulSoup(response.text, 'lxml')

        # Parse listing cards
        property_cards = soup.select('[data-test="property-card"], .list-card, .property-card')

        for card in property_cards:
            listing = self._parse_zillow_card(card)
            if listing:
                # Filter for Lennar if requested
                if builder_filter:
                    card_text = card.get_text().lower()
                    if 'lennar' in card_text:
                        listings.append(listing)
                else:
                    listings.append(listing)

        # Also try to extract from JavaScript data
        script_data = self._extract_script_data(soup)
        if script_data:
            js_listings = self._parse_script_listings(script_data, builder_filter)
            listings.extend(js_listings)

        # Deduplicate by address
        seen = set()
        unique = []
        for l in listings:
            key = (l.address, l.zip_code)
            if key not in seen:
                seen.add(key)
                unique.append(l)

        return unique

    def _parse_zillow_card(self, card) -> Optional[ZillowLennarListing]:
        """Parse a Zillow property card element."""
        try:
            listing = ZillowLennarListing()

            # Address
            addr_elem = card.select_one('address, [data-test="property-card-addr"]')
            if addr_elem:
                full_addr = addr_elem.get_text(strip=True)
                listing.address = full_addr
                self._parse_address_components(listing, full_addr)

            # Price
            price_elem = card.select_one('[data-test="property-card-price"], .list-card-price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                listing.price = price_text
                listing.price_numeric = self._extract_price(price_text)

            # Bed/Bath/Sqft
            details_elem = card.select_one('[data-test="property-card-details"], .list-card-details')
            if details_elem:
                details_text = details_elem.get_text()
                self._parse_details(listing, details_text)

            # URL
            link = card.select_one('a[href*="/homedetails/"]')
            if link:
                listing.listing_url = urljoin(self.ZILLOW_BASE, link.get('href', ''))

            # Image
            img = card.select_one('img[src]')
            if img:
                listing.image_url = img.get('src', '')

            # Try to get builder info
            builder_elem = card.select_one('.builder-name, [data-test="builder-name"]')
            if builder_elem:
                builder_text = builder_elem.get_text(strip=True)
                if 'lennar' in builder_text.lower():
                    listing.builder = "Lennar"

            if listing.address:
                return listing

        except Exception as e:
            logger.debug(f"Error parsing card: {e}")

        return None

    def _parse_address_components(self, listing: ZillowLennarListing, full_addr: str):
        """Parse address into components."""
        # Pattern: Street, City, State ZIP
        match = re.match(r'(.+?),\s*([^,]+),\s*([A-Z]{2})\s*(\d{5})?', full_addr)
        if match:
            listing.address = match.group(1).strip()
            listing.city = match.group(2).strip()
            listing.state = match.group(3).strip()
            if match.group(4):
                listing.zip_code = match.group(4).strip()
        else:
            # Try simpler pattern
            parts = full_addr.split(',')
            if len(parts) >= 2:
                listing.address = parts[0].strip()
                if len(parts) >= 3:
                    listing.city = parts[1].strip()

    def _parse_details(self, listing: ZillowLennarListing, details_text: str):
        """Parse bedroom/bathroom/sqft from details text."""
        # Bedrooms
        bed_match = re.search(r'(\d+)\s*(?:bd|bed|bds|beds)', details_text, re.I)
        if bed_match:
            listing.bedrooms = bed_match.group(1)

        # Bathrooms
        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ba|bath|baths)', details_text, re.I)
        if bath_match:
            listing.bathrooms = bath_match.group(1)

        # Square feet
        sqft_match = re.search(r'([\d,]+)\s*(?:sqft|sq\s*ft)', details_text, re.I)
        if sqft_match:
            listing.sqft = sqft_match.group(1).replace(',', '')

        # House type
        if 'condo' in details_text.lower():
            listing.house_type = "Condominium"
        elif 'townhouse' in details_text.lower() or 'townhome' in details_text.lower():
            listing.house_type = "Townhome"
        elif 'house' in details_text.lower() or 'single family' in details_text.lower():
            listing.house_type = "Single Family"

    def _extract_price(self, price_text: str) -> Optional[int]:
        """Extract numeric price from text."""
        clean = re.sub(r'[^\d]', '', price_text)
        if clean:
            try:
                return int(clean)
            except ValueError:
                pass
        return None

    def _extract_script_data(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extract data from embedded JavaScript."""
        scripts = soup.select('script')
        for script in scripts:
            text = script.string or ""
            if 'searchPageState' in text or 'listResults' in text:
                # Try to extract JSON
                json_match = re.search(r'(\{.*"listResults".*\})', text, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
        return None

    def _parse_script_listings(self, data: dict,
                               builder_filter: bool) -> list[ZillowLennarListing]:
        """Parse listings from JavaScript data."""
        listings = []

        try:
            # Navigate to results
            results = data.get('cat1', {}).get('searchResults', {}).get('listResults', [])
            if not results:
                results = data.get('searchResults', {}).get('listResults', [])

            for result in results:
                listing = ZillowLennarListing()

                listing.address = result.get('address', '')
                listing.city = result.get('addressCity', '')
                listing.state = result.get('addressState', '')
                listing.zip_code = result.get('addressZipcode', '')

                price = result.get('price', '') or result.get('unformattedPrice', 0)
                if isinstance(price, str):
                    listing.price = price
                    listing.price_numeric = self._extract_price(price)
                else:
                    listing.price = f"${price:,}"
                    listing.price_numeric = price

                listing.bedrooms = str(result.get('beds', ''))
                listing.bathrooms = str(result.get('baths', ''))
                listing.sqft = str(result.get('area', ''))

                listing.latitude = result.get('latLong', {}).get('latitude')
                listing.longitude = result.get('latLong', {}).get('longitude')

                listing.listing_url = urljoin(self.ZILLOW_BASE, result.get('detailUrl', ''))

                # Check for builder/Lennar
                builder_name = result.get('builderName', '').lower()
                if builder_filter and 'lennar' not in builder_name:
                    continue

                listing.builder = result.get('builderName', 'Lennar')

                if listing.address:
                    listings.append(listing)

        except Exception as e:
            logger.debug(f"Error parsing script data: {e}")

        return listings

    def _scrape_with_selenium(self, url: str) -> str:
        """Scrape page using Selenium."""
        self._setup_selenium()

        try:
            self.driver.get(url)
            time.sleep(3)

            # Scroll to load content
            for _ in range(5):
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(1)

            return self.driver.page_source

        except Exception as e:
            logger.error(f"Selenium error: {e}")
            return ""

    def scrape_lennar_profile(self) -> list[ZillowLennarListing]:
        """
        Scrape Lennar's builder profile page on Zillow.

        Returns:
            List of listings from the profile page
        """
        logger.info("Scraping Lennar builder profile...")
        listings = []

        if self.use_selenium:
            html = self._scrape_with_selenium(self.LENNAR_PROFILE_URL)
            soup = BeautifulSoup(html, 'lxml')
        else:
            response = self._make_request(self.LENNAR_PROFILE_URL)
            if not response:
                return listings
            soup = BeautifulSoup(response.text, 'lxml')

        # Parse community/development cards
        community_cards = soup.select('.community-card, [data-community], .builder-community')
        for card in community_cards:
            # Extract community info
            community_name = ""
            name_elem = card.select_one('.community-name, h2, h3')
            if name_elem:
                community_name = name_elem.get_text(strip=True)

            # Extract homes in community
            home_cards = card.select('.home-card, .property-card')
            for home in home_cards:
                listing = self._parse_zillow_card(home)
                if listing:
                    listing.community_name = community_name
                    listing.builder = "Lennar"
                    listings.append(listing)

        self.listings.extend(listings)
        logger.info(f"Found {len(listings)} listings from builder profile")
        return listings

    def scrape_multiple_locations(self, locations: list[str],
                                  delay: float = 2.0) -> list[ZillowLennarListing]:
        """
        Scrape Lennar listings from multiple locations.

        Args:
            locations: List of location strings (city, state or zip)
            delay: Delay between requests

        Returns:
            Combined list of all listings
        """
        all_listings = []

        for location in tqdm(locations, desc="Locations"):
            time.sleep(delay)

            try:
                listings = self.search_zillow_new_construction(location)
                all_listings.extend(listings)
                logger.info(f"Found {len(listings)} Lennar listings in {location}")
            except Exception as e:
                logger.error(f"Error scraping {location}: {e}")

        self.listings = all_listings
        return all_listings

    def export_to_csv(self, filepath: str = "zillow_lennar_listings.csv") -> str:
        """Export listings to CSV."""
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        fieldnames = [
            'address', 'city', 'state', 'zip_code', 'price', 'price_numeric',
            'house_type', 'bedrooms', 'bathrooms', 'sqft', 'community_name',
            'builder', 'status', 'listing_url', 'latitude', 'longitude', 'scraped_at'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for listing in self.listings:
                row = asdict(listing)
                row.pop('image_url', None)
                writer.writerow(row)

        logger.info(f"Exported {len(self.listings)} listings to {filepath}")
        return filepath

    def export_to_json(self, filepath: str = "zillow_lennar_listings.json") -> str:
        """Export listings to JSON."""
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        data = {
            'source': 'Zillow',
            'builder': 'Lennar',
            'scraped_at': datetime.now().isoformat(),
            'total_listings': len(self.listings),
            'listings': [asdict(listing) for listing in self.listings]
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
        self.session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Scrape Lennar listings from Zillow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for Lennar homes in specific locations
  python zillow_lennar_scraper.py --locations "Dallas, TX" "Houston, TX" "Austin, TX"

  # Use Selenium for better JavaScript support
  python zillow_lennar_scraper.py --selenium --locations "Phoenix, AZ"

  # Scrape Lennar's builder profile page
  python zillow_lennar_scraper.py --profile
        """
    )

    parser.add_argument('--locations', nargs='+',
                       help='Locations to search (city, state format)')
    parser.add_argument('--profile', action='store_true',
                       help='Scrape Lennar builder profile page')
    parser.add_argument('--selenium', action='store_true',
                       help='Use Selenium for JavaScript rendering')
    parser.add_argument('--no-headless', action='store_true',
                       help='Show browser window')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay between requests (default: 2.0)')
    parser.add_argument('--output-csv', default='zillow_lennar_listings.csv',
                       help='Output CSV file')
    parser.add_argument('--output-json', default='zillow_lennar_listings.json',
                       help='Output JSON file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = ZillowLennarScraper(
        use_selenium=args.selenium,
        headless=not args.no_headless
    )

    try:
        if args.profile:
            scraper.scrape_lennar_profile()

        if args.locations:
            scraper.scrape_multiple_locations(args.locations, delay=args.delay)

        if not args.locations and not args.profile:
            # Default locations covering major Lennar markets
            default_locations = [
                "Phoenix, AZ", "Los Angeles, CA", "San Diego, CA",
                "Denver, CO", "Miami, FL", "Orlando, FL", "Tampa, FL",
                "Atlanta, GA", "Las Vegas, NV", "Charlotte, NC",
                "Dallas, TX", "Houston, TX", "Austin, TX", "San Antonio, TX"
            ]
            print(f"No locations specified. Using default markets: {len(default_locations)} locations")
            scraper.scrape_multiple_locations(default_locations, delay=args.delay)

        if scraper.listings:
            scraper.export_to_csv(args.output_csv)
            scraper.export_to_json(args.output_json)

            print(f"\n{'='*60}")
            print("Scraping Complete!")
            print(f"{'='*60}")
            print(f"Total listings found: {len(scraper.listings)}")
            print(f"CSV output: {args.output_csv}")
            print(f"JSON output: {args.output_json}")
            print(f"{'='*60}")
        else:
            print("\nNo listings found. Try using --selenium for better results.")

    except KeyboardInterrupt:
        print("\nScraping interrupted")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise
    finally:
        scraper.close()


if __name__ == '__main__':
    main()
