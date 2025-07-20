#!/usr/bin/env python3
"""Walmart scraper using ScrapeOps API"""

import requests
import json
import re
import asyncio
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PriceResult
from config import Config

class WalmartScraper(BaseScraper):
    """Walmart scraper using ScrapeOps API to bypass bot detection"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        super().__init__(max_retries, timeout)
        
        # ScrapeOps API configuration
        self.api_key = Config.SCRAPEOPS_API_KEY
        self.base_url = 'https://proxy.scrapeops.io/v1/'
        
        if not self.api_key:
            self.logger.warning("❌ SCRAPEOPS_API_KEY not configured - Walmart scraping will fail")
        else:
            self.logger.info("✅ Using ScrapeOps API for Walmart scraping")
    
    async def check_price(self, url: str, store_id: str = None, zip_code: str = None) -> PriceResult:
        """Check price and availability at Walmart using ScrapeOps API"""
        
        if not self.api_key:
            return PriceResult(
                url=url,
                store_id=store_id or "online",
                price=None,
                shipping_available=False,
                pickup_available=False,
                in_stock=False,
                error="ScrapeOps API key not configured"
            )
        
        # Build location cookies if store_id provided
        cookies = None
        if store_id and zip_code:
            cookies = self._build_location_cookie(store_id, zip_code)
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"🔄 Checking Walmart product: {url} (attempt {attempt + 1}/{self.max_retries})")
                
                # Add delay between retries
                if attempt > 0:
                    delay = 2 ** attempt  # Exponential backoff
                    self.logger.debug(f"Retry delay: {delay}s...")
                    await asyncio.sleep(delay)
                
                # Prepare ScrapeOps API request
                params = {
                    'api_key': self.api_key,
                    'url': url,
                    'country': 'us',
                    'render_js': 'true',  # Enable JavaScript rendering
                    'premium': 'true',    # Use premium proxies
                }
                
                # Add cookies if available
                if cookies:
                    params['cookies'] = cookies
                
                # Make request to ScrapeOps API
                self.logger.debug("Making ScrapeOps API request...")
                response = requests.get(
                    url=self.base_url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # Check if we got blocked or error response
                if response.status_code != 200:
                    self.logger.warning(f"ScrapeOps API returned status {response.status_code}")
                    continue
                
                # Parse the response
                return self._parse_response(response.text, url, store_id or "online")
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"🌐 Request error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    continue
            except Exception as e:
                self.logger.error(f"❌ Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    continue
        
        return PriceResult(
            url=url,
            store_id=store_id or "online",
            price=None,
            shipping_available=False,
            pickup_available=False,
            in_stock=False,
            error="Failed after all retries"
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for ScrapeOps API"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'Connection': 'keep-alive'
        }
    
    def _build_location_cookie(self, store_id: str, zip_code: str) -> str:
        """Build location cookie for store-specific checks"""
        import time
        import uuid
        import base64
        
        timestamp = int(time.time() * 1000)
        acid = str(uuid.uuid4())
        
        location_data = {
            "intent": "SHIPPING",
            "storeIntent": "PICKUP",
            "mergeFlag": True,
            "pickup": {
                "nodeId": store_id,
                "timestamp": timestamp
            },
            "postalCode": {
                "base": zip_code,
                "timestamp": timestamp
            },
            "validateKey": f"prod:v2:{acid}"
        }
        
        loc_guest_data = base64.urlsafe_b64encode(
            json.dumps(location_data).encode()
        ).decode()
        
        return (
            f"ACID={acid}; hasACID=true; hasLocData=1; "
            f"locDataV3={json.dumps(location_data)}; "
            f"assortmentStoreId={store_id}; locGuestData={loc_guest_data}"
        )
    
    def _parse_response(self, html: str, url: str, store_id: str) -> PriceResult:
        """Parse Walmart response"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find __NEXT_DATA__ script tag
        script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
        if not script_tag:
            return PriceResult(
                url=url,
                store_id=store_id,
                price=None,
                shipping_available=False,
                pickup_available=False,
                in_stock=False,
                error="Could not find product data"
            )
        
        try:
            script_content = script_tag.get_text() if script_tag else None
            if not script_content:
                return PriceResult(
                    url=url,
                    store_id=store_id,
                    price=None,
                    shipping_available=False,
                    pickup_available=False,
                    in_stock=False,
                    error="Empty script content"
                )
            data = json.loads(script_content)
            product = data['props']['pageProps']['initialData']['data']['product']
            
            # Extract price
            price_info = product.get('priceInfo', {})
            current_price = price_info.get('currentPrice', {})
            price = current_price.get('price')
            
            # Extract product name
            product_name = product.get('name', 'Unknown Product')
            
            # Check availability
            availability_status = product.get('availabilityStatus', 'OUT_OF_STOCK')
            in_stock = availability_status == 'IN_STOCK'
            
            # Check fulfillment options
            shipping_available = False
            pickup_available = False
            
            fulfillment_options = product.get('fulfillmentOptions', [])
            for option in fulfillment_options:
                if option['type'] == 'SHIPPING':
                    shipping_available = option.get('availabilityStatus') in ['IN_STOCK', 'AVAILABLE']
                elif option['type'] == 'PICKUP':
                    pickup_available = option.get('availabilityStatus') in ['IN_STOCK', 'AVAILABLE']
            
            return PriceResult(
                url=url,
                store_id=store_id,
                price=price,
                shipping_available=shipping_available,
                pickup_available=pickup_available,
                in_stock=in_stock,
                product_name=product_name,
                raw_data={'product': product}
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Error parsing Walmart data: {e}")
            return PriceResult(
                url=url,
                store_id=store_id,
                price=None,
                shipping_available=False,
                pickup_available=False,
                in_stock=False,
                error=f"Parse error: {str(e)}"
            )
    
    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract Walmart product ID from URL"""
        # Pattern: /ip/product-name/12345
        match = re.search(r'/ip/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        return None
    
    async def close(self):
        """Close scraper session (no cleanup needed for ScrapeOps API)"""
        pass