#!/usr/bin/env python3
"""Test Target location spoofing functionality"""

import asyncio
import sys
from scrapers.target_scraper import TargetLocationScraper

async def test_single_location(url: str, zip_code: str):
    """Test a Target product from a specific ZIP code"""
    
    print(f"\n🎯 Testing Target Product")
    print(f"URL: {url}")
    print(f"ZIP: {zip_code}")
    print("-" * 60)
    
    scraper = TargetLocationScraper(headless=True)
    await scraper.initialize()
    
    try:
        result = await scraper.check_price(url, zip_code=zip_code)
        
        print(f"\nResults:")
        print(f"  Product: {result.product_name}")
        print(f"  Price: ${result.price:.2f}" if result.price else "  Price: Not found")
        print(f"  Shipping: {'✅ Available' if result.shipping_available else '❌ Not available'}")
        
        if result.raw_data and 'shipping_message' in result.raw_data:
            print(f"  Message: {result.raw_data['shipping_message']}")
        
        if result.error:
            print(f"  Error: {result.error}")
            
    finally:
        await scraper.close()

async def test_default():
    """Test with default product and ZIP"""
    # Example product - Fujifilm Instax Mini Film
    test_url = "https://www.target.com/p/fujifilm-instax-mini-instant-film-twin-pack/-/A-17401603"
    test_zip = "10001"  # NYC
    
    await test_single_location(test_url, test_zip)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Test specific URL and ZIP
        url = sys.argv[1]
        zip_code = sys.argv[2]
        asyncio.run(test_single_location(url, zip_code))
    else:
        # Run default test
        print("Usage: python test_target_location.py [url] [zip_code]")
        print("Running default test...")
        asyncio.run(test_default())