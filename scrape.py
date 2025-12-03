#!/usr/bin/env python3
"""
Unified Lennar Listings Scraper

A unified interface to scrape Lennar home listings from multiple sources:
- lennar.com (direct)
- Zillow (builder profile and search)

This provides a simple entry point with intelligent source selection.
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scrape_lennar_direct(args):
    """Scrape from Lennar.com directly."""
    from lennar_scraper import LennarScraper

    scraper = LennarScraper(
        use_selenium=args.selenium,
        headless=not args.no_headless
    )

    try:
        scraper.scrape_all_listings(
            states=args.states,
            max_communities=args.max_communities,
            delay=args.delay
        )
        return scraper
    except Exception as e:
        logger.error(f"Lennar direct scraping failed: {e}")
        raise


def scrape_zillow(args):
    """Scrape Lennar listings from Zillow."""
    from zillow_lennar_scraper import ZillowLennarScraper

    scraper = ZillowLennarScraper(
        use_selenium=args.selenium,
        headless=not args.no_headless
    )

    try:
        if args.locations:
            scraper.scrape_multiple_locations(args.locations, delay=args.delay)
        else:
            # Use major Lennar markets as default
            default_locations = get_default_locations(args.states)
            scraper.scrape_multiple_locations(default_locations, delay=args.delay)

        return scraper
    except Exception as e:
        logger.error(f"Zillow scraping failed: {e}")
        raise


def get_default_locations(states=None):
    """Get default location list based on states."""
    all_locations = {
        'arizona': ["Phoenix, AZ", "Tucson, AZ", "Mesa, AZ"],
        'california': ["Los Angeles, CA", "San Diego, CA", "Sacramento, CA",
                       "San Francisco, CA", "Riverside, CA", "Fresno, CA"],
        'colorado': ["Denver, CO", "Colorado Springs, CO", "Aurora, CO"],
        'florida': ["Miami, FL", "Orlando, FL", "Tampa, FL", "Jacksonville, FL",
                    "Fort Lauderdale, FL", "West Palm Beach, FL", "Naples, FL"],
        'georgia': ["Atlanta, GA", "Savannah, GA"],
        'idaho': ["Boise, ID"],
        'indiana': ["Indianapolis, IN"],
        'maryland': ["Baltimore, MD"],
        'minnesota': ["Minneapolis, MN"],
        'nevada': ["Las Vegas, NV", "Reno, NV", "Henderson, NV"],
        'new-jersey': ["Newark, NJ", "Jersey City, NJ"],
        'north-carolina': ["Charlotte, NC", "Raleigh, NC", "Durham, NC"],
        'oregon': ["Portland, OR"],
        'south-carolina': ["Charleston, SC", "Columbia, SC", "Myrtle Beach, SC"],
        'tennessee': ["Nashville, TN", "Memphis, TN"],
        'texas': ["Dallas, TX", "Houston, TX", "Austin, TX", "San Antonio, TX",
                  "Fort Worth, TX", "El Paso, TX"],
        'utah': ["Salt Lake City, UT"],
        'virginia': ["Richmond, VA", "Virginia Beach, VA"],
        'washington': ["Seattle, WA", "Tacoma, WA"]
    }

    if states:
        locations = []
        for state in states:
            state_key = state.lower().replace(' ', '-')
            locations.extend(all_locations.get(state_key, []))
        return locations if locations else list(sum(all_locations.values(), []))

    return list(sum(all_locations.values(), []))


def combine_results(lennar_scraper, zillow_scraper):
    """Combine and deduplicate results from both scrapers."""
    combined = []
    seen_addresses = set()

    # Convert Lennar listings to common format
    if lennar_scraper and lennar_scraper.listings:
        for listing in lennar_scraper.listings:
            key = (listing.location or listing.community_name, listing.price)
            if key not in seen_addresses:
                seen_addresses.add(key)
                combined.append({
                    'source': 'Lennar.com',
                    'community_name': listing.community_name,
                    'address': listing.location,
                    'city': listing.city,
                    'state': listing.state,
                    'zip_code': listing.zip_code,
                    'price': listing.price,
                    'price_numeric': listing.price_numeric,
                    'house_type': listing.house_type,
                    'bedrooms': listing.bedrooms,
                    'bathrooms': listing.bathrooms,
                    'sqft': listing.sqft,
                    'plan_name': listing.plan_name,
                    'status': listing.status,
                    'url': listing.url,
                    'scraped_at': listing.scraped_at
                })

    # Add Zillow listings
    if zillow_scraper and zillow_scraper.listings:
        for listing in zillow_scraper.listings:
            key = (listing.address, listing.price)
            if key not in seen_addresses:
                seen_addresses.add(key)
                combined.append({
                    'source': 'Zillow',
                    'community_name': listing.community_name,
                    'address': listing.address,
                    'city': listing.city,
                    'state': listing.state,
                    'zip_code': listing.zip_code,
                    'price': listing.price,
                    'price_numeric': listing.price_numeric,
                    'house_type': listing.house_type,
                    'bedrooms': listing.bedrooms,
                    'bathrooms': listing.bathrooms,
                    'sqft': listing.sqft,
                    'plan_name': '',
                    'status': listing.status,
                    'url': listing.listing_url,
                    'scraped_at': listing.scraped_at
                })

    return combined


def export_combined(listings, csv_path, json_path):
    """Export combined listings to CSV and JSON."""
    import csv
    import json
    from datetime import datetime

    if not listings:
        logger.warning("No listings to export")
        return

    # CSV export
    fieldnames = [
        'source', 'community_name', 'address', 'city', 'state', 'zip_code',
        'price', 'price_numeric', 'house_type', 'bedrooms', 'bathrooms',
        'sqft', 'plan_name', 'status', 'url', 'scraped_at'
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(listings)

    # JSON export
    data = {
        'scraped_at': datetime.now().isoformat(),
        'total_listings': len(listings),
        'sources': list(set(l['source'] for l in listings)),
        'listings': listings
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(listings)} listings to {csv_path} and {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Scrape Lennar Homebuilders listings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape from both sources (recommended)
  python scrape.py --both --states texas florida

  # Scrape only from Lennar.com
  python scrape.py --source lennar --states california

  # Scrape only from Zillow for specific cities
  python scrape.py --source zillow --locations "Dallas, TX" "Austin, TX"

  # Quick scrape with limited communities
  python scrape.py --both --states texas --max-communities 3

  # Use Selenium for JavaScript-heavy pages
  python scrape.py --both --selenium --states arizona

Sources:
  lennar  - Scrape directly from lennar.com
  zillow  - Scrape Lennar listings from Zillow
  both    - Scrape from both sources and combine results
        """
    )

    # Source selection
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument('--source', choices=['lennar', 'zillow'],
                             help='Data source to use')
    source_group.add_argument('--both', action='store_true',
                             help='Scrape from both sources')

    # Location filters
    parser.add_argument('--states', nargs='+',
                       help='State slugs to scrape (e.g., texas florida)')
    parser.add_argument('--locations', nargs='+',
                       help='Specific locations for Zillow search')
    parser.add_argument('--max-communities', type=int,
                       help='Max communities per state (Lennar source)')

    # Scraping options
    parser.add_argument('--selenium', action='store_true',
                       help='Use Selenium for JavaScript rendering')
    parser.add_argument('--no-headless', action='store_true',
                       help='Show browser window')
    parser.add_argument('--delay', type=float, default=1.5,
                       help='Delay between requests (default: 1.5)')

    # Output options
    parser.add_argument('--output-csv', default='lennar_listings.csv',
                       help='Output CSV file')
    parser.add_argument('--output-json', default='lennar_listings.json',
                       help='Output JSON file')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default to both sources if none specified
    if not args.source and not args.both:
        args.both = True
        logger.info("No source specified, using both sources")

    lennar_scraper = None
    zillow_scraper = None

    try:
        if args.source == 'lennar' or args.both:
            print("\n=== Scraping from Lennar.com ===")
            try:
                lennar_scraper = scrape_lennar_direct(args)
            except Exception as e:
                logger.error(f"Lennar scraping failed: {e}")
                if not args.both:
                    raise

        if args.source == 'zillow' or args.both:
            print("\n=== Scraping from Zillow ===")
            try:
                zillow_scraper = scrape_zillow(args)
            except Exception as e:
                logger.error(f"Zillow scraping failed: {e}")
                if not args.both:
                    raise

        # Combine and export
        if args.both:
            listings = combine_results(lennar_scraper, zillow_scraper)
            export_combined(listings, args.output_csv, args.output_json)
        elif lennar_scraper:
            lennar_scraper.export_to_csv(args.output_csv)
            lennar_scraper.export_to_json(args.output_json)
            listings = lennar_scraper.listings
        elif zillow_scraper:
            zillow_scraper.export_to_csv(args.output_csv)
            zillow_scraper.export_to_json(args.output_json)
            listings = zillow_scraper.listings
        else:
            listings = []

        # Summary
        print(f"\n{'='*60}")
        print("Scraping Complete!")
        print(f"{'='*60}")
        print(f"Total listings found: {len(listings)}")
        print(f"CSV output: {args.output_csv}")
        print(f"JSON output: {args.output_json}")

        if listings:
            # Show sample data
            print(f"\nSample listing:")
            sample = listings[0] if isinstance(listings[0], dict) else listings[0].__dict__
            for key in ['community_name', 'city', 'state', 'price', 'house_type']:
                if key in sample:
                    print(f"  {key}: {sample.get(key, 'N/A')}")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)
    finally:
        if lennar_scraper:
            lennar_scraper.close()
        if zillow_scraper:
            zillow_scraper.close()


if __name__ == '__main__':
    main()
