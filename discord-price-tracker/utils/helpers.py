#!/usr/bin/env python3
"""Helper utilities"""

import re
from typing import Tuple, Optional
from urllib.parse import urlparse

def validate_url(url: str) -> Tuple[bool, str, Optional[str], str]:
    """
    Validate product URL and extract info
    Returns: (is_valid, message, product_id, site)
    """
    try:
        parsed = urlparse(url)
        
        # Walmart URL
        if 'walmart.com' in parsed.netloc.lower():
            if '/ip/' not in parsed.path:
                return False, "Walmart URL must contain '/ip/'", None, "walmart"
            
            # Extract product ID
            match = re.search(r'/ip/[^/]+/(\d+)', parsed.path)
            if match:
                product_id = match.group(1)
                return True, "Valid Walmart URL", product_id, "walmart"
            
            return False, "Could not extract Walmart product ID", None, "walmart"
        
        # Target URL
        elif 'target.com' in parsed.netloc.lower():
            if '/p/' not in parsed.path or '/-/A-' not in parsed.path:
                return False, "Target URL must contain '/p/' and '/-/A-'", None, "target"
            
            # Extract DPCI
            match = re.search(r'/A-(\d+)', parsed.path)
            if match:
                product_id = match.group(1)
                return True, "Valid Target URL", product_id, "target"
            
            return False, "Could not extract Target product ID", None, "target"
        
        else:
            return False, "URL must be from walmart.com or target.com", None, "unknown"
            
    except Exception as e:
        return False, f"Invalid URL: {str(e)}", None, "unknown"

def validate_threshold(threshold: float) -> Tuple[bool, str]:
    """Validate price threshold"""
    if threshold <= 0:
        return False, "Threshold must be greater than $0"
    
    if threshold > 10000:
        return False, "Threshold cannot exceed $10,000"
    
    return True, "Valid threshold"

def validate_store_id(store_id: str) -> Tuple[bool, str]:
    """Validate Walmart store ID"""
    # Clean the input
    store_id = re.sub(r'[^\d]', '', store_id)
    
    if not store_id:
        return False, "Store ID cannot be empty"
    
    if len(store_id) < 3 or len(store_id) > 6:
        return False, "Store ID must be 3-6 digits"
    
    return True, store_id

def validate_zip_code(zip_code: str) -> Tuple[bool, str]:
    """Validate US ZIP code"""
    # Clean the input
    zip_code = re.sub(r'[^\d]', '', zip_code)
    
    if len(zip_code) != 5:
        return False, "ZIP code must be 5 digits"
    
    return True, zip_code

def extract_product_name(url: str, site: str) -> str:
    """Extract product name from URL"""
    try:
        if site == "walmart":
            # /ip/Product-Name-Here/12345
            match = re.search(r'/ip/([^/]+)/\d+', url)
            if match:
                name = match.group(1)
                return name.replace('-', ' ').title()
        
        elif site == "target":
            # /p/product-name/-/A-12345
            match = re.search(r'/p/([^/]+)/-/', url)
            if match:
                name = match.group(1)
                return name.replace('-', ' ').title()
    except:
        pass
    
    return f"{site.title()} Product"

def format_price(price: float) -> str:
    """Format price for display"""
    return f"${price:.2f}"

def format_store_info(store_id: str, zip_code: str, site: str = "walmart") -> str:
    """Format store information for display"""
    if site == "target":
        return "Target.com (Online)"
    
    return f"Store #{store_id} (ZIP: {zip_code})"

def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."