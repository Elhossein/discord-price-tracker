#!/usr/bin/env python3
"""Database management for price tracker"""

import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class User:
    id: int
    discord_id: str
    name: str
    primary_store_id: str
    zip_code: str
    notifications_enabled: bool
    created_at: str

@dataclass
class Product:
    id: int
    url: str
    name: Optional[str]
    site: str
    created_at: str

@dataclass
class TrackedProduct:
    id: int
    user_id: int
    product_id: int
    threshold: float
    is_active: bool
    created_at: str

@dataclass
class Store:
    id: int
    user_id: int
    store_id: str
    zip_code: str
    created_at: str

class Database:
    """Database handler for price tracker"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    primary_store_id TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    notifications_enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Products table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    name TEXT,
                    site TEXT NOT NULL CHECK(site IN ('walmart', 'target')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tracked products
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    threshold REAL NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                    UNIQUE(user_id, product_id)
                )
            """)
            
            # User stores (for Walmart pickup only)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_stores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    store_id TEXT NOT NULL,
                    zip_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, store_id)
                )
            """)
            
            # Price history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    store_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    shipping_available BOOLEAN DEFAULT 0,
                    pickup_available BOOLEAN DEFAULT 0,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            
            # Alert history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    store_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL CHECK(alert_type IN ('shipping', 'pickup')),
                    price REAL NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            
            # Alert states (prevent spam)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_states (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    store_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    last_alert_price REAL,
                    last_alert_at TIMESTAMP,
                    PRIMARY KEY (user_id, product_id, store_id, alert_type),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            
            # User ZIP codes table (NEW)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_zip_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    zip_code TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT 0,
                    label TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, zip_code)
                )
            """)
            
            # Migration: Copy existing user ZIP codes to new table
            conn.execute("""
                INSERT OR IGNORE INTO user_zip_codes (user_id, zip_code, is_primary, label)
                SELECT id, zip_code, 1, 'Primary' FROM users WHERE zip_code IS NOT NULL
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    # User operations
    def create_user(self, discord_id: str, name: str, primary_store_id: str, zip_code: str) -> int:
        """Create a new user"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO users (discord_id, name, primary_store_id, zip_code)
                   VALUES (?, ?, ?, ?)""",
                (discord_id, name, primary_store_id, zip_code)
            )
            return cursor.lastrowid
    
    def get_user(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE discord_id = ?", 
                (discord_id,)
            ).fetchone()
            
            if row:
                return User(**dict(row))
            return None
    
    def update_user_store(self, discord_id: str, store_id: str, zip_code: str) -> bool:
        """Update user's primary store"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE users SET primary_store_id = ?, zip_code = ? 
                   WHERE discord_id = ?""",
                (store_id, zip_code, discord_id)
            )
            return cursor.rowcount > 0
    
    def delete_user(self, discord_id: str) -> bool:
        """Delete user and all associated data"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE discord_id = ?",
                (discord_id,)
            )
            return cursor.rowcount > 0
    
    def get_all_users(self) -> List[User]:
        """Get all users"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
            return [User(**dict(row)) for row in rows]
    
    # Product operations
    def create_product(self, url: str, name: Optional[str], site: str) -> int:
        """Create or get product"""
        with self._get_connection() as conn:
            # Try to insert
            cursor = conn.execute(
                """INSERT OR IGNORE INTO products (url, name, site)
                   VALUES (?, ?, ?)""",
                (url, name, site)
            )
            
            if cursor.rowcount > 0:
                return cursor.lastrowid
            
            # Already exists, get ID
            row = conn.execute(
                "SELECT id FROM products WHERE url = ?",
                (url,)
            ).fetchone()
            return row['id']
    
    def get_product_by_url(self, url: str) -> Optional[Product]:
        """Get product by URL"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE url = ?",
                (url,)
            ).fetchone()
            
            if row:
                return Product(**dict(row))
            return None
    
    def update_product_name(self, product_id: int, name: str) -> bool:
        """Update product name"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE products SET name = ? WHERE id = ?",
                (name, product_id)
            )
            return cursor.rowcount > 0
    
    # Tracking operations
    def add_tracked_product(self, user_id: int, product_id: int, threshold: float) -> int:
        """Add product to user's tracking list"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO tracked_products 
                   (user_id, product_id, threshold, is_active)
                   VALUES (?, ?, ?, 1)""",
                (user_id, product_id, threshold)
            )
            return cursor.lastrowid
    
    def get_user_products(self, user_id: int) -> List[Tuple[TrackedProduct, Product]]:
        """Get all products tracked by user"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT tp.*, p.*
                FROM tracked_products tp
                JOIN products p ON tp.product_id = p.id
                WHERE tp.user_id = ? AND tp.is_active = 1
                ORDER BY tp.created_at DESC
            """, (user_id,)).fetchall()
            
            results = []
            for row in rows:
                tracked = TrackedProduct(
                    id=row['id'],
                    user_id=row['user_id'],
                    product_id=row['product_id'],
                    threshold=row['threshold'],
                    is_active=row['is_active'],
                    created_at=row['created_at']
                )
                product = Product(
                    id=row['product_id'],
                    url=row['url'],
                    name=row['name'],
                    site=row['site'],
                    created_at=row['created_at']
                )
                results.append((tracked, product))
            
            return results
    
    def remove_tracked_product(self, user_id: int, tracked_id: int) -> bool:
        """Remove product from tracking"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE tracked_products SET is_active = 0 
                   WHERE user_id = ? AND id = ?""",
                (user_id, tracked_id)
            )
            return cursor.rowcount > 0
    
    def get_all_active_tracking(self) -> List[Dict[str, Any]]:
        """Get all active tracking requests"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT u.*, tp.*, p.*
                FROM tracked_products tp
                JOIN users u ON tp.user_id = u.id
                JOIN products p ON tp.product_id = p.id
                WHERE tp.is_active = 1 AND u.notifications_enabled = 1
                ORDER BY u.id, p.id
            """).fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'user': User(
                        id=row['id'],
                        discord_id=row['discord_id'],
                        name=row['name'],
                        primary_store_id=row['primary_store_id'],
                        zip_code=row['zip_code'],
                        notifications_enabled=row['notifications_enabled'],
                        created_at=row['created_at']
                    ),
                    'tracked': TrackedProduct(
                        id=row['id'],
                        user_id=row['user_id'],
                        product_id=row['product_id'],
                        threshold=row['threshold'],
                        is_active=row['is_active'],
                        created_at=row['created_at']
                    ),
                    'product': Product(
                        id=row['product_id'],
                        url=row['url'],
                        name=row['name'],
                        site=row['site'],
                        created_at=row['created_at']
                    ),
                    'pickup_stores': self.get_user_stores(row['user_id'])
                })
            
            return results
    
    # Store operations (Walmart pickup only)
    def add_user_store(self, user_id: int, store_id: str, zip_code: str) -> int:
        """Add Walmart pickup store for user"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO user_stores 
                   (user_id, store_id, zip_code)
                   VALUES (?, ?, ?)""",
                (user_id, store_id, zip_code)
            )
            return cursor.lastrowid
    
    def get_user_stores(self, user_id: int) -> List[Store]:
        """Get user's Walmart pickup stores"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM user_stores 
                   WHERE user_id = ? 
                   ORDER BY created_at""",
                (user_id,)
            ).fetchall()
            
            return [Store(**dict(row)) for row in rows]
    
    def remove_user_store(self, user_id: int, store_id: str) -> bool:
        """Remove Walmart pickup store"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM user_stores 
                   WHERE user_id = ? AND store_id = ?""",
                (user_id, store_id)
            )
            return cursor.rowcount > 0
    
    # Price history
    def log_price(self, product_id: int, store_id: str, price: float, 
                  shipping: bool = False, pickup: bool = False):
        """Log price check"""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO price_history 
                   (product_id, store_id, price, shipping_available, pickup_available)
                   VALUES (?, ?, ?, ?, ?)""",
                (product_id, store_id, price, shipping, pickup)
            )
    
    # Alert management
    def should_send_alert(self, user_id: int, product_id: int, store_id: str, 
                         alert_type: str, current_price: float, threshold: float) -> bool:
        """Check if alert should be sent"""
        if current_price > threshold:
            # Price above threshold, reset alert state
            self._reset_alert_state(user_id, product_id, store_id, alert_type)
            return False
        
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM alert_states 
                   WHERE user_id = ? AND product_id = ? 
                   AND store_id = ? AND alert_type = ?""",
                (user_id, product_id, store_id, alert_type)
            ).fetchone()
            
            if not row:
                # No previous alert state, send alert
                return True
            
            # Check if price has changed since last alert
            last_alert_price = row['last_alert_price']
            last_alert_time = datetime.fromisoformat(row['last_alert_at'].replace('Z', '+00:00'))
            current_time = datetime.utcnow()
            
            # If price is different, send new alert
            if abs(current_price - last_alert_price) > 0.01:  # Allow for small floating point differences
                return True
            
            # If price is same, check if enough time has passed (24 hours)
            time_diff = current_time - last_alert_time
            if time_diff.total_seconds() > 24 * 3600:  # 24 hours
                return True
            
            # Same price, recent alert, don't spam
            return False
    
    def record_alert_sent(self, user_id: int, product_id: int, store_id: str,
                         alert_type: str, price: float):
        """Record that alert was sent"""
        with self._get_connection() as conn:
            # Record in history
            conn.execute(
                """INSERT INTO alert_history 
                   (user_id, product_id, store_id, alert_type, price)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, product_id, store_id, alert_type, price)
            )
            
            # Update alert state
            conn.execute(
                """INSERT OR REPLACE INTO alert_states 
                   (user_id, product_id, store_id, alert_type, last_alert_price, last_alert_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, product_id, store_id, alert_type, price)
            )
    
    def _reset_alert_state(self, user_id: int, product_id: int, store_id: str, alert_type: str):
        """Reset alert state when price goes above threshold"""
        with self._get_connection() as conn:
            conn.execute(
                """DELETE FROM alert_states 
                   WHERE user_id = ? AND product_id = ? 
                   AND store_id = ? AND alert_type = ?""",
                (user_id, product_id, store_id, alert_type)
            )
    
    # Statistics
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        with self._get_connection() as conn:
            stats = {}
            
            for table in ['users', 'products', 'tracked_products', 'user_stores', 
                         'price_history', 'alert_history']:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats[table] = count
            
            # Active tracking
            stats['active_tracking'] = conn.execute(
                "SELECT COUNT(*) FROM tracked_products WHERE is_active = 1"
            ).fetchone()[0]
            
            return stats
    
    # ZIP code management (NEW)
    def add_user_zip_code(self, user_id: int, zip_code: str, label: str = None, is_primary: bool = False) -> int:
        """Add ZIP code for user"""
        with self._get_connection() as conn:
            # If setting as primary, unset other primary flags
            if is_primary:
                conn.execute(
                    "UPDATE user_zip_codes SET is_primary = 0 WHERE user_id = ?",
                    (user_id,)
                )
                # Also update users table
                conn.execute(
                    "UPDATE users SET zip_code = ? WHERE id = ?",
                    (zip_code, user_id)
                )
            
            cursor = conn.execute(
                """INSERT OR REPLACE INTO user_zip_codes 
                   (user_id, zip_code, is_primary, label)
                   VALUES (?, ?, ?, ?)""",
                (user_id, zip_code, is_primary, label or f"ZIP {zip_code}")
            )
            return cursor.lastrowid or 0

    def get_user_zip_codes(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all ZIP codes for user"""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM user_zip_codes 
                   WHERE user_id = ? 
                   ORDER BY is_primary DESC, created_at""",
                (user_id,)
            ).fetchall()
            
            return [dict(row) for row in rows]

    def remove_user_zip_code(self, user_id: int, zip_code: str) -> bool:
        """Remove ZIP code from user"""
        with self._get_connection() as conn:
            # Check if it's primary
            row = conn.execute(
                "SELECT is_primary FROM user_zip_codes WHERE user_id = ? AND zip_code = ?",
                (user_id, zip_code)
            ).fetchone()
            
            if not row:
                return False
            
            if row['is_primary']:
                # Cannot remove primary ZIP
                return False
            
            cursor = conn.execute(
                "DELETE FROM user_zip_codes WHERE user_id = ? AND zip_code = ?",
                (user_id, zip_code)
            )
            return cursor.rowcount > 0

    def set_primary_zip_code(self, user_id: int, zip_code: str) -> bool:
        """Set primary ZIP code for user"""
        with self._get_connection() as conn:
            # Check if ZIP exists for user
            row = conn.execute(
                "SELECT id FROM user_zip_codes WHERE user_id = ? AND zip_code = ?",
                (user_id, zip_code)
            ).fetchone()
            
            if not row:
                return False
            
            # Unset all primary flags
            conn.execute(
                "UPDATE user_zip_codes SET is_primary = 0 WHERE user_id = ?",
                (user_id,)
            )
            
            # Set new primary
            conn.execute(
                "UPDATE user_zip_codes SET is_primary = 1 WHERE user_id = ? AND zip_code = ?",
                (user_id, zip_code)
            )
            
            # Update users table
            conn.execute(
                "UPDATE users SET zip_code = ? WHERE id = ?",
                (zip_code, user_id)
            )
            
            return True