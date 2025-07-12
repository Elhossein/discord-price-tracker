#!/usr/bin/env python3
"""Walmart scraper for shipping and pickup checks"""

import cloudscraper
import json
import re
import time
import uuid
import base64
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, PriceResult

class WalmartScraper(BaseScraper):
    """Walmart scraper that checks both shipping and pickup availability"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        super().__init__(max_retries, timeout)
        self.scraper = cloudscraper.create_scraper()
    
    async def check_price(self, url: str, store_id: str = None, zip_code: str = None) -> PriceResult:
        """Check price and availability at Walmart"""
        
        # Build location cookies if store_id provided
        headers = self._get_headers()
        if store_id and zip_code:
            headers['Cookie'] = self._build_location_cookie(store_id, zip_code)
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Checking Walmart product: {url} (attempt {attempt + 1})")
                
                response = self.scraper.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                
                return self._parse_response(response.text, url, store_id or "online")
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
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
        """Get request headers"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _build_location_cookie(self, store_id: str, zip_code: str) -> str:
        """Build location cookie for store-specific checks"""
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
            data = json.loads(script_tag.string)
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
        """Close scraper session"""
        if hasattr(self.scraper, 'close'):
            self.scraper.close()