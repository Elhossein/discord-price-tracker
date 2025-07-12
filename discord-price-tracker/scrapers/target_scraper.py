#!/usr/bin/env python3
"""Target scraper with location spoofing for shipping checks"""

import re
import logging
import asyncio
import json
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Page, Browser
import aiohttp

from .base_scraper import BaseScraper, PriceResult

class TargetLocationScraper(BaseScraper):
    """Target scraper with location spoofing via cookies"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30, headless: bool = True):
        super().__init__(max_retries, timeout)
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._playwright = None
        self.geocode_cache = {}
        
    async def initialize(self):
        """Initialize browser"""
        if not self._browser:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.logger.info("Target scraper browser initialized")
    
    async def geocode_zip(self, zip_code: str) -> Optional[Dict[str, float]]:
        """Convert ZIP code to coordinates using free geocoding service"""
        
        # Check cache first
        if zip_code in self.geocode_cache:
            return self.geocode_cache[zip_code]
        
        try:
            # Use Nominatim (free OpenStreetMap geocoding)
            url = f"https://nominatim.openstreetmap.org/search"
            params = {
                'postalcode': zip_code,
                'country': 'USA',
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'Discord-Price-Tracker/1.0'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            result = {
                                'lat': float(data[0]['lat']),
                                'lon': float(data[0]['lon']),
                                'display_name': data[0]['display_name']
                            }
                            self.geocode_cache[zip_code] = result
                            self.logger.debug(f"Geocoded {zip_code}: {result['lat']}, {result['lon']}")
                            return result
            
            # Fallback: Use hardcoded coordinates for common ZIP codes
            fallback_coords = {
                '10001': {'lat': 40.7508, 'lon': -73.9961},  # NYC
                '90210': {'lat': 34.1030, 'lon': -118.4105}, # Beverly Hills
                '60601': {'lat': 41.8858, 'lon': -87.6181},  # Chicago
                '33101': {'lat': 25.7783, 'lon': -80.1886},  # Miami
                '94102': {'lat': 37.7795, 'lon': -122.4187}, # San Francisco
                '98101': {'lat': 47.6097, 'lon': -122.3331}, # Seattle
                '30301': {'lat': 33.7537, 'lon': -84.3863},  # Atlanta
                '02108': {'lat': 42.3575, 'lon': -71.0636},  # Boston
                '75201': {'lat': 32.7815, 'lon': -96.7968},  # Dallas
                '85001': {'lat': 33.4494, 'lon': -112.0771}, # Phoenix
            }
            
            if zip_code in fallback_coords:
                coords = fallback_coords[zip_code]
                self.geocode_cache[zip_code] = coords
                return coords
            
            # If all else fails, use a default (center of USA)
            default = {'lat': 39.8283, 'lon': -98.5795}
            self.logger.warning(f"Could not geocode {zip_code}, using default coordinates")
            return default
            
        except Exception as e:
            self.logger.error(f"Geocoding error for {zip_code}: {e}")
            return None
    
    async def set_location_cookies(self, page: Page, zip_code: str) -> bool:
        """Set Target location cookies to spoof location"""
        
        # Get coordinates for the ZIP code
        coords = await self.geocode_zip(zip_code)
        if not coords:
            return False
        
        # Extract state code from ZIP (rough approximation)
        state_codes = {
            '0': 'MA', '1': 'MA', '2': 'MA', '3': 'NH', '4': 'ME',
            '5': 'VT', '6': 'CT', '7': 'NJ', '8': 'NY', '9': 'NY',
            '10': 'NY', '11': 'NY', '12': 'NY', '13': 'NY', '14': 'NY',
            '15': 'PA', '16': 'PA', '17': 'PA', '18': 'PA', '19': 'PA',
            '20': 'DC', '21': 'MD', '22': 'VA', '23': 'VA', '24': 'WV',
            '25': 'WV', '26': 'WV', '27': 'NC', '28': 'NC', '29': 'SC',
            '30': 'GA', '31': 'GA', '32': 'FL', '33': 'FL', '34': 'FL',
            '35': 'AL', '36': 'AL', '37': 'TN', '38': 'TN', '39': 'MS',
            '40': 'KY', '41': 'KY', '42': 'KY', '43': 'OH', '44': 'OH',
            '45': 'OH', '46': 'IN', '47': 'IN', '48': 'MI', '49': 'MI',
            '50': 'IA', '51': 'IA', '52': 'IA', '53': 'WI', '54': 'WI',
            '55': 'MN', '56': 'MN', '57': 'SD', '58': 'ND', '59': 'MT',
            '60': 'IL', '61': 'IL', '62': 'IL', '63': 'MO', '64': 'MO',
            '65': 'MO', '66': 'KS', '67': 'KS', '68': 'NE', '69': 'NE',
            '70': 'LA', '71': 'LA', '72': 'AR', '73': 'OK', '74': 'OK',
            '75': 'TX', '76': 'TX', '77': 'TX', '78': 'TX', '79': 'TX',
            '80': 'CO', '81': 'CO', '82': 'WY', '83': 'ID', '84': 'UT',
            '85': 'AZ', '86': 'AZ', '87': 'NM', '88': 'NM', '89': 'NV',
            '90': 'CA', '91': 'CA', '92': 'CA', '93': 'CA', '94': 'CA',
            '95': 'CA', '96': 'CA', '97': 'OR', '98': 'WA', '99': 'WA'
        }
        
        # Get state from first 2 digits of ZIP
        state = state_codes.get(zip_code[:2], 'NY')
        
        # Format location string for Target cookies
        location_string = f"{zip_code}|{coords['lat']:.3f}|{coords['lon']:.3f}|{state}|US"
        
        # Set Target location cookies
        await page.context.add_cookies([
            {
                'name': 'GuestLocation',
                'value': location_string,
                'domain': '.target.com',
                'path': '/'
            },
            {
                'name': 'UserLocation', 
                'value': location_string,
                'domain': '.target.com',
                'path': '/'
            }
        ])
        
        self.logger.info(f"Set Target location to ZIP {zip_code} ({state})")
        return True
    
    async def check_price(self, url: str, store_id: str = None, zip_code: str = None) -> PriceResult:
        """Check price and shipping availability at Target"""
        
        # Default ZIP code if none provided
        if not zip_code:
            zip_code = "10001"  # Default to NYC
        
        # Ensure browser is initialized
        await self.initialize()
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Checking Target product: {url} from ZIP {zip_code} (attempt {attempt + 1})")
                
                # Create new context for each request
                context = await self._browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                try:
                    # Set location cookies before navigating
                    await self.set_location_cookies(page, zip_code)
                    
                    # Navigate to product page
                    await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
                    
                    # Wait for price to load
                    await page.wait_for_selector('[data-test="product-price"]', timeout=10000)
                    
                    # Wait a bit for location to take effect
                    await asyncio.sleep(2)
                    
                    # Wait for shipping info to update
                    await page.wait_for_function(
                        """() => {
                            const shipping = document.querySelector('[data-test="fulfillment-cell-shipping"]');
                            return shipping && !shipping.textContent.includes('loading');
                        }""",
                        timeout=10000
                    )
                    
                    result = await self._extract_product_info(page, url, zip_code)
                    return result
                    
                finally:
                    await context.close()
                    
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return PriceResult(
            url=url,
            store_id=f"target.com-{zip_code}",
            price=None,
            shipping_available=False,
            pickup_available=False,
            in_stock=False,
            error="Failed after all retries"
        )
    
    async def check_multiple_locations(self, url: str, zip_codes: List[str]) -> List[PriceResult]:
        """Check product from multiple ZIP codes"""
        results = []
        
        for zip_code in zip_codes:
            self.logger.info(f"Checking from ZIP {zip_code}...")
            result = await self.check_price(url, zip_code=zip_code)
            results.append(result)
            
            # Wait between requests to avoid rate limiting
            if zip_code != zip_codes[-1]:
                await asyncio.sleep(3)
        
        return results
    
    async def _extract_product_info(self, page: Page, url: str, zip_code: str) -> PriceResult:
        """Extract product information from Target page"""
        
        try:
            # Extract product name
            product_name = "Unknown Product"
            try:
                name_elem = await page.query_selector('h1[data-test="product-title"]')
                if name_elem:
                    product_name = await name_elem.text_content()
                    product_name = product_name.strip()
            except:
                pass
            
            # Extract price
            price = None
            try:
                price_elem = await page.query_selector('[data-test="product-price"]')
                if price_elem:
                    price_text = await price_elem.text_content()
                    # Extract numeric price from text like "$19.99"
                    price_match = re.search(r'\$([\d,]+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1).replace(',', ''))
            except:
                pass
            
            # Check shipping availability
            shipping_available = False
            shipping_message = ""
            try:
                shipping_elem = await page.query_selector('[data-test="fulfillment-cell-shipping"]')
                
                if shipping_elem:
                    shipping_text = await shipping_elem.text_content()
                    shipping_message = shipping_text.strip()
                    
                    # Check for positive shipping indicators
                    shipping_keywords = [
                        'arrives', 'get it by', 'available', 
                        'free shipping', 'deliver', 'ships',
                        'standard shipping', '2-day shipping'
                    ]
                    
                    # Check for negative indicators
                    negative_keywords = [
                        'not available', 'unavailable', 
                        'cannot ship', 'sold out'
                    ]
                    
                    shipping_available = (
                        any(keyword in shipping_message.lower() for keyword in shipping_keywords) and
                        not any(keyword in shipping_message.lower() for keyword in negative_keywords)
                    )
            except:
                self.logger.debug("Could not find shipping information")
            
            # In stock if shipping is available
            in_stock = shipping_available
            
            self.logger.info(f"Target {product_name}: ${price} - Shipping from {zip_code}: {shipping_available}")
            
            return PriceResult(
                url=url,
                store_id=f"target-{zip_code}",
                price=price,
                shipping_available=shipping_available,
                pickup_available=False,  # Target pickup not supported
                in_stock=in_stock,
                product_name=product_name,
                raw_data={
                    'shipping_message': shipping_message,
                    'zip_code': zip_code
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting Target data: {e}")
            return PriceResult(
                url=url,
                store_id=f"target-{zip_code}",
                price=None,
                shipping_available=False,
                pickup_available=False,
                in_stock=False,
                error=f"Extract error: {str(e)}"
            )
    
    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract Target product ID (DPCI) from URL"""
        # Pattern: /p/product-name/-/A-12345678
        match = re.search(r'/A-(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    async def close(self):
        """Close browser"""
        if self._browser:
            await self._browser.close()
            self.logger.info("Target scraper browser closed")
        if self._playwright:
            await self._playwright.stop()