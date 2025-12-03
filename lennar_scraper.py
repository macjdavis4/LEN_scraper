#!/usr/bin/env python3
"""
Lennar Homebuilders Listings Scraper

Scrapes Lennar home listings from lennar.com, extracting:
- Location (address, city, state, zip)
- House type (single family, townhome, etc.)
- Price
- Community name
- Additional details (bedrooms, bathrooms, sqft)
"""

import argparse
import csv
import json
import logging
import re
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
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
    community_name: str = ""
    location: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    price: str = ""
    price_numeric: Optional[int] = None
    house_type: str = ""
    bedrooms: str = ""
    bathrooms: str = ""
    sqft: str = ""
    status: str = ""
    url: str = ""
    plan_name: str = ""
    features: list = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LennarScraper:
    """Scraper for Lennar Homebuilders website."""

    BASE_URL = "https://www.lennar.com"
    SEARCH_API_URL = "https://www.lennar.com/api/v2/search"
    COMMUNITIES_API_URL = "https://www.lennar.com/api/v2/communities"
    HOMES_API_URL = "https://www.lennar.com/api/v2/homes"

    # Alternative API endpoints discovered through web analysis
    GRAPHQL_URL = "https://www.lennar.com/graphql"

    def __init__(self, use_selenium: bool = False, headless: bool = True):
        """
        Initialize the scraper.

        Args:
            use_selenium: Whether to use Selenium for JavaScript rendering
            headless: Run browser in headless mode (if using Selenium)
        """
        self.session = requests.Session()
        self.ua = UserAgent()
        self.use_selenium = use_selenium
        self.headless = headless
        self.driver = None
        self.listings: list[LennarListing] = []

        self._setup_session()

    def _setup_session(self):
        """Configure the requests session with appropriate headers."""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.lennar.com/',
            'Origin': 'https://www.lennar.com',
        })

    def _setup_selenium(self):
        """Initialize Selenium WebDriver if needed."""
        if self.driver is not None:
            return

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument(f'--user-agent={self.ua.random}')
            options.add_argument('--window-size=1920,1080')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Selenium: {e}")
            raise

    def _make_request(self, url: str, method: str = 'GET',
                      params: dict = None, json_data: dict = None,
                      retry_count: int = 3) -> Optional[requests.Response]:
        """
        Make an HTTP request with retry logic.

        Args:
            url: URL to request
            method: HTTP method
            params: Query parameters
            json_data: JSON body data
            retry_count: Number of retries

        Returns:
            Response object or None if failed
        """
        for attempt in range(retry_count):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=30)
                elif method.upper() == 'POST':
                    response = self.session.post(url, params=params, json=json_data, timeout=30)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    # Rotate user agent
                    self.session.headers['User-Agent'] = self.ua.random

        return None

    def get_states(self) -> list[dict]:
        """Get list of states where Lennar operates."""
        logger.info("Fetching available states...")

        # Try the API first
        response = self._make_request(f"{self.BASE_URL}/new-homes")
        if response:
            soup = BeautifulSoup(response.text, 'lxml')

            # Look for state links in the navigation
            states = []
            state_links = soup.select('a[href*="/new-homes/"]')

            for link in state_links:
                href = link.get('href', '')
                # Extract state from URL pattern /new-homes/state-name
                match = re.search(r'/new-homes/([a-z-]+)/?$', href)
                if match:
                    state_slug = match.group(1)
                    state_name = link.get_text(strip=True)
                    if state_name and state_slug not in ['find-a-home', 'search']:
                        states.append({
                            'slug': state_slug,
                            'name': state_name,
                            'url': urljoin(self.BASE_URL, href)
                        })

            # Remove duplicates
            seen = set()
            unique_states = []
            for s in states:
                if s['slug'] not in seen:
                    seen.add(s['slug'])
                    unique_states.append(s)

            logger.info(f"Found {len(unique_states)} states")
            return unique_states

        # Fallback to known Lennar operating states
        logger.info("Using fallback state list")
        return self._get_fallback_states()

    def _get_fallback_states(self) -> list[dict]:
        """Return known states where Lennar operates."""
        states = [
            "arizona", "california", "colorado", "florida", "georgia",
            "idaho", "indiana", "maryland", "minnesota", "nevada",
            "new-jersey", "north-carolina", "oregon", "south-carolina",
            "tennessee", "texas", "utah", "virginia", "washington"
        ]
        return [
            {
                'slug': s,
                'name': s.replace('-', ' ').title(),
                'url': f"{self.BASE_URL}/new-homes/{s}"
            }
            for s in states
        ]

    def get_communities_in_state(self, state_slug: str) -> list[dict]:
        """
        Get all communities in a given state.

        Args:
            state_slug: State URL slug (e.g., 'texas', 'florida')

        Returns:
            List of community dictionaries
        """
        logger.info(f"Fetching communities in {state_slug}...")
        communities = []

        # Try the state page
        url = f"{self.BASE_URL}/new-homes/{state_slug}"
        response = self._make_request(url)

        if response:
            soup = BeautifulSoup(response.text, 'lxml')

            # Look for community cards/links
            community_elements = soup.select('[data-community], .community-card, a[href*="/community/"]')

            for elem in community_elements:
                href = elem.get('href', '')
                if not href:
                    link = elem.select_one('a[href*="/community/"]')
                    if link:
                        href = link.get('href', '')

                if '/community/' in href:
                    name = elem.get_text(strip=True)
                    if not name or len(name) > 200:
                        name_elem = elem.select_one('.community-name, h2, h3, .title')
                        if name_elem:
                            name = name_elem.get_text(strip=True)

                    communities.append({
                        'name': name,
                        'url': urljoin(self.BASE_URL, href),
                        'state': state_slug
                    })

            # Also try to find metro area pages
            metro_links = soup.select('a[href*="/new-homes/" + state_slug + "/"]')
            for link in metro_links:
                href = link.get('href', '')
                if re.search(rf'/new-homes/{state_slug}/[a-z-]+/?$', href):
                    # This is a metro area, fetch its communities too
                    metro_response = self._make_request(urljoin(self.BASE_URL, href))
                    if metro_response:
                        metro_soup = BeautifulSoup(metro_response.text, 'lxml')
                        metro_communities = metro_soup.select('a[href*="/community/"]')
                        for mc in metro_communities:
                            mc_href = mc.get('href', '')
                            mc_name = mc.get_text(strip=True)
                            if mc_href and mc_name:
                                communities.append({
                                    'name': mc_name,
                                    'url': urljoin(self.BASE_URL, mc_href),
                                    'state': state_slug
                                })

        # Remove duplicates
        seen_urls = set()
        unique_communities = []
        for c in communities:
            if c['url'] not in seen_urls:
                seen_urls.add(c['url'])
                unique_communities.append(c)

        logger.info(f"Found {len(unique_communities)} communities in {state_slug}")
        return unique_communities

    def get_listings_from_community(self, community: dict) -> list[LennarListing]:
        """
        Get all home listings from a specific community.

        Args:
            community: Community dictionary with name, url, and state

        Returns:
            List of LennarListing objects
        """
        listings = []
        community_url = community['url']

        response = self._make_request(community_url)
        if not response:
            logger.warning(f"Failed to fetch community: {community['name']}")
            return listings

        soup = BeautifulSoup(response.text, 'lxml')

        # Extract community info
        community_name = community.get('name', '')
        if not community_name:
            name_elem = soup.select_one('h1, .community-title, .community-name')
            if name_elem:
                community_name = name_elem.get_text(strip=True)

        # Extract location info
        location_elem = soup.select_one('.community-location, .location, address')
        location_text = location_elem.get_text(strip=True) if location_elem else ""

        # Parse location components
        city, state, zip_code = self._parse_location(location_text, community.get('state', ''))

        # Find home listings/plans
        home_cards = soup.select(
            '.home-card, .plan-card, .qmi-card, '
            '[data-home], [data-plan], .inventory-home, '
            '.floorplan-card, .home-listing'
        )

        for card in home_cards:
            listing = self._parse_home_card(card, community_name, city, state, zip_code)
            if listing:
                listings.append(listing)

        # Also check for floor plans section
        plan_section = soup.select('.floorplans, .floor-plans, #floorplans')
        for section in plan_section:
            plan_cards = section.select('.plan, .floorplan, [data-plan]')
            for card in plan_cards:
                listing = self._parse_home_card(card, community_name, city, state, zip_code)
                if listing:
                    listings.append(listing)

        # Check for QMI (Quick Move-In) homes
        qmi_section = soup.select('.qmi-homes, .move-in-ready, .inventory')
        for section in qmi_section:
            qmi_cards = section.select('.home, .qmi, [data-qmi]')
            for card in qmi_cards:
                listing = self._parse_home_card(card, community_name, city, state, zip_code)
                if listing:
                    listing.status = "Move-In Ready"
                    listings.append(listing)

        logger.info(f"Found {len(listings)} listings in {community_name}")
        return listings

    def _parse_home_card(self, card, community_name: str,
                         city: str, state: str, zip_code: str) -> Optional[LennarListing]:
        """Parse a home card element into a LennarListing."""
        try:
            listing = LennarListing()
            listing.community_name = community_name
            listing.city = city
            listing.state = state
            listing.zip_code = zip_code

            # Extract plan/home name
            name_elem = card.select_one('.plan-name, .home-name, h2, h3, .title, .name')
            if name_elem:
                listing.plan_name = name_elem.get_text(strip=True)

            # Extract price
            price_elem = card.select_one('.price, .home-price, .plan-price, [data-price]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                listing.price = price_text
                listing.price_numeric = self._parse_price(price_text)

            # Extract house type
            type_elem = card.select_one('.home-type, .type, .property-type')
            if type_elem:
                listing.house_type = type_elem.get_text(strip=True)
            else:
                # Try to infer from other elements
                card_text = card.get_text().lower()
                if 'townhome' in card_text or 'townhouse' in card_text:
                    listing.house_type = "Townhome"
                elif 'condo' in card_text:
                    listing.house_type = "Condominium"
                elif 'single family' in card_text or 'single-family' in card_text:
                    listing.house_type = "Single Family"
                else:
                    listing.house_type = "Single Family"  # Default

            # Extract bedrooms
            bed_elem = card.select_one('.beds, .bedrooms, [data-beds]')
            if bed_elem:
                listing.bedrooms = self._extract_number(bed_elem.get_text())
            else:
                bed_match = re.search(r'(\d+)\s*(?:bed|br|bedroom)', card.get_text(), re.I)
                if bed_match:
                    listing.bedrooms = bed_match.group(1)

            # Extract bathrooms
            bath_elem = card.select_one('.baths, .bathrooms, [data-baths]')
            if bath_elem:
                listing.bathrooms = self._extract_number(bath_elem.get_text())
            else:
                bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|ba|bathroom)', card.get_text(), re.I)
                if bath_match:
                    listing.bathrooms = bath_match.group(1)

            # Extract square footage
            sqft_elem = card.select_one('.sqft, .square-feet, [data-sqft]')
            if sqft_elem:
                listing.sqft = self._extract_number(sqft_elem.get_text())
            else:
                sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft|sf)', card.get_text(), re.I)
                if sqft_match:
                    listing.sqft = sqft_match.group(1).replace(',', '')

            # Extract address/location
            addr_elem = card.select_one('.address, .location, .home-address')
            if addr_elem:
                listing.location = addr_elem.get_text(strip=True)

            # Extract URL
            link_elem = card.select_one('a[href]')
            if link_elem:
                listing.url = urljoin(self.BASE_URL, link_elem.get('href', ''))

            # Extract status
            status_elem = card.select_one('.status, .availability, .home-status')
            if status_elem:
                listing.status = status_elem.get_text(strip=True)

            # Only return if we have meaningful data
            if listing.plan_name or listing.price or listing.community_name:
                return listing

        except Exception as e:
            logger.debug(f"Error parsing home card: {e}")

        return None

    def _parse_location(self, location_text: str, state_hint: str = "") -> tuple[str, str, str]:
        """Parse location text into city, state, zip components."""
        city = ""
        state = ""
        zip_code = ""

        # Try to extract zip code
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', location_text)
        if zip_match:
            zip_code = zip_match.group(1)

        # Try to extract state (2-letter code)
        state_match = re.search(r'\b([A-Z]{2})\b', location_text)
        if state_match:
            state = state_match.group(1)
        elif state_hint:
            # Convert state slug to abbreviation
            state = self._state_slug_to_abbrev(state_hint)

        # Try to extract city (text before state)
        if state:
            city_match = re.search(rf'([A-Za-z\s]+),?\s*{state}', location_text)
            if city_match:
                city = city_match.group(1).strip()

        return city, state, zip_code

    def _state_slug_to_abbrev(self, slug: str) -> str:
        """Convert state URL slug to abbreviation."""
        mapping = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new-hampshire': 'NH', 'new-jersey': 'NJ', 'new-mexico': 'NM', 'new-york': 'NY',
            'north-carolina': 'NC', 'north-dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode-island': 'RI', 'south-carolina': 'SC',
            'south-dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west-virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY'
        }
        return mapping.get(slug.lower(), slug.upper()[:2])

    def _parse_price(self, price_text: str) -> Optional[int]:
        """Extract numeric price from price text."""
        # Remove currency symbols and commas
        clean = re.sub(r'[^\d]', '', price_text)
        if clean:
            try:
                return int(clean)
            except ValueError:
                pass
        return None

    def _extract_number(self, text: str) -> str:
        """Extract the first number from text."""
        match = re.search(r'[\d,.]+', text)
        return match.group(0) if match else ""

    def scrape_all_listings(self, states: list[str] = None,
                           max_communities: int = None,
                           delay: float = 1.0) -> list[LennarListing]:
        """
        Scrape all Lennar listings.

        Args:
            states: List of state slugs to scrape (None for all)
            max_communities: Maximum number of communities to scrape per state
            delay: Delay between requests in seconds

        Returns:
            List of all scraped listings
        """
        all_listings = []

        # Get states to scrape
        available_states = self.get_states()
        if states:
            available_states = [s for s in available_states if s['slug'] in states]

        logger.info(f"Scraping {len(available_states)} states...")

        for state in tqdm(available_states, desc="States"):
            time.sleep(delay)

            communities = self.get_communities_in_state(state['slug'])

            if max_communities:
                communities = communities[:max_communities]

            for community in tqdm(communities, desc=f"Communities in {state['name']}", leave=False):
                time.sleep(delay)

                try:
                    listings = self.get_listings_from_community(community)
                    all_listings.extend(listings)
                except Exception as e:
                    logger.error(f"Error scraping community {community['name']}: {e}")

        self.listings = all_listings
        logger.info(f"Total listings scraped: {len(all_listings)}")
        return all_listings

    def scrape_with_selenium(self, url: str) -> str:
        """
        Scrape a page using Selenium for JavaScript rendering.

        Args:
            url: URL to scrape

        Returns:
            Page HTML content
        """
        self._setup_selenium()

        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for JavaScript to render

            # Scroll to load lazy content
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            while True:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            return self.driver.page_source

        except Exception as e:
            logger.error(f"Selenium scraping error: {e}")
            return ""

    def search_homes(self, location: str = None,
                    min_price: int = None, max_price: int = None,
                    bedrooms: int = None, house_type: str = None) -> list[LennarListing]:
        """
        Search for homes with filters using Lennar's search functionality.

        Args:
            location: City, state, or zip code
            min_price: Minimum price filter
            max_price: Maximum price filter
            bedrooms: Minimum bedrooms filter
            house_type: Type of home (single family, townhome, etc.)

        Returns:
            List of matching listings
        """
        search_url = f"{self.BASE_URL}/find-a-home"
        params = {}

        if location:
            params['location'] = location
        if min_price:
            params['minPrice'] = min_price
        if max_price:
            params['maxPrice'] = max_price
        if bedrooms:
            params['beds'] = bedrooms
        if house_type:
            params['homeType'] = house_type

        if self.use_selenium:
            html = self.scrape_with_selenium(f"{search_url}?{urlencode(params)}")
            soup = BeautifulSoup(html, 'lxml')
        else:
            response = self._make_request(search_url, params=params)
            if not response:
                return []
            soup = BeautifulSoup(response.text, 'lxml')

        listings = []

        # Parse search results
        result_cards = soup.select('.search-result, .home-card, .community-card')
        for card in result_cards:
            listing = self._parse_home_card(card, "", "", "", "")
            if listing:
                listings.append(listing)

        return listings

    def export_to_csv(self, filepath: str = "lennar_listings.csv") -> str:
        """
        Export scraped listings to CSV.

        Args:
            filepath: Output file path

        Returns:
            Path to created file
        """
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        fieldnames = [
            'community_name', 'location', 'city', 'state', 'zip_code',
            'price', 'price_numeric', 'house_type', 'bedrooms', 'bathrooms',
            'sqft', 'status', 'plan_name', 'url', 'scraped_at'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for listing in self.listings:
                row = asdict(listing)
                row.pop('features', None)  # Exclude list field
                writer.writerow(row)

        logger.info(f"Exported {len(self.listings)} listings to {filepath}")
        return filepath

    def export_to_json(self, filepath: str = "lennar_listings.json") -> str:
        """
        Export scraped listings to JSON.

        Args:
            filepath: Output file path

        Returns:
            Path to created file
        """
        if not self.listings:
            logger.warning("No listings to export")
            return ""

        data = {
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
    """Main entry point for the scraper."""
    parser = argparse.ArgumentParser(
        description='Scrape Lennar Homebuilders listings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all listings from Texas and Florida
  python lennar_scraper.py --states texas florida

  # Scrape with Selenium (for JavaScript-heavy pages)
  python lennar_scraper.py --selenium --states california

  # Scrape first 5 communities per state, export to both formats
  python lennar_scraper.py --max-communities 5 --output-csv results.csv --output-json results.json

  # Search for homes in a specific location
  python lennar_scraper.py --search --location "Dallas, TX" --min-price 300000 --max-price 500000
        """
    )

    parser.add_argument('--states', nargs='+',
                       help='State slugs to scrape (e.g., texas florida california)')
    parser.add_argument('--max-communities', type=int,
                       help='Maximum communities to scrape per state')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--selenium', action='store_true',
                       help='Use Selenium for JavaScript rendering')
    parser.add_argument('--no-headless', action='store_true',
                       help='Show browser window (when using Selenium)')
    parser.add_argument('--output-csv', default='lennar_listings.csv',
                       help='Output CSV file path')
    parser.add_argument('--output-json', default='lennar_listings.json',
                       help='Output JSON file path')

    # Search mode arguments
    parser.add_argument('--search', action='store_true',
                       help='Use search mode instead of scraping all')
    parser.add_argument('--location', help='Location to search (city, state, or zip)')
    parser.add_argument('--min-price', type=int, help='Minimum price filter')
    parser.add_argument('--max-price', type=int, help='Maximum price filter')
    parser.add_argument('--bedrooms', type=int, help='Minimum bedrooms filter')
    parser.add_argument('--house-type', help='House type filter')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = LennarScraper(
        use_selenium=args.selenium,
        headless=not args.no_headless
    )

    try:
        if args.search:
            # Search mode
            listings = scraper.search_homes(
                location=args.location,
                min_price=args.min_price,
                max_price=args.max_price,
                bedrooms=args.bedrooms,
                house_type=args.house_type
            )
            scraper.listings = listings
        else:
            # Full scrape mode
            scraper.scrape_all_listings(
                states=args.states,
                max_communities=args.max_communities,
                delay=args.delay
            )

        # Export results
        if scraper.listings:
            scraper.export_to_csv(args.output_csv)
            scraper.export_to_json(args.output_json)

            print(f"\n{'='*60}")
            print(f"Scraping Complete!")
            print(f"{'='*60}")
            print(f"Total listings found: {len(scraper.listings)}")
            print(f"CSV output: {args.output_csv}")
            print(f"JSON output: {args.output_json}")
            print(f"{'='*60}")
        else:
            print("\nNo listings found. Try different parameters or enable Selenium mode.")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise
    finally:
        scraper.close()


if __name__ == '__main__':
    main()
