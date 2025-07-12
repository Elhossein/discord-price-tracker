#!/usr/bin/env python3
"""Base scraper class"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

@dataclass
class PriceResult:
    """Result from price check"""
    url: str
    store_id: str
    price: Optional[float]
    shipping_available: bool
    pickup_available: bool
    in_stock: bool
    product_name: Optional[str] = None
    error: Optional[str] = None
    raw_data: Optional[dict] = None

class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def check_price(self, url: str, store_id: str = None, zip_code: str = None) -> PriceResult:
        """Check price for a product"""
        pass
    
    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass
    
    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID from URL"""
        return None