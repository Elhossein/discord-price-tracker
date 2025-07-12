#!/usr/bin/env python3
"""Price checking cog for background tasks"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
from typing import Dict, List, Any

from scrapers import WalmartScraper, PriceResult
from config import Config

logger = logging.getLogger(__name__)

class PriceChecker(commands.Cog):
    """Background price checking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.dm_alerts = bot.dm_alerts
        
        # Initialize scrapers
        self.walmart_scraper = WalmartScraper()
        self.target_scraper = None  # Initialize when needed
        
        # Statistics
        self.checks_completed = 0
        self.alerts_sent = 0
        self.last_check = None
        self.is_running = False
        
        # Start background task
        self.check_prices.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_prices.cancel()
    
    @tasks.loop(minutes=Config.CHECK_INTERVAL_MINUTES)
    async def check_prices(self):
        """Background price checking task"""
        if self.is_running:
            logger.warning("Price check already running, skipping...")
            return
        
        self.is_running = True
        logger.info("🔄 Starting scheduled price check")
        
        try:
            await self._run_price_checks()
        except Exception as e:
            logger.error(f"❌ Price check failed: {e}")
        finally:
            self.is_running = False
    
    @check_prices.before_loop
    async def before_check_prices(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
        logger.info("✅ Price checker ready")
    
    async def _run_price_checks(self):
        """Run price checks for all active tracking"""
        start_time = datetime.now()
        
        # Get all active tracking
        tracking_data = self.db.get_all_active_tracking()
        
        if not tracking_data:
            logger.info("No active tracking requests")
            return
        
        logger.info(f"Checking prices for {len(tracking_data)} tracking requests")
        
        # Group by site
        walmart_checks = []
        target_checks = []
        
        for data in tracking_data:
            if data['product'].site == 'walmart':
                walmart_checks.append(data)
            else:
                target_checks.append(data)
        
        # Process Walmart checks
        if walmart_checks:
            await self._process_walmart_checks(walmart_checks)
        
        # Process Target checks
        if target_checks:
            await self._process_target_checks(target_checks)
        
        # Update statistics
        duration = (datetime.now() - start_time).total_seconds()
        self.last_check = datetime.now()
        
        logger.info(f"✅ Price check completed in {duration:.1f}s - "
                   f"{self.checks_completed} checks, {self.alerts_sent} alerts")
    
    async def _process_walmart_checks(self, checks: List[Dict[str, Any]]):
        """Process Walmart price checks"""
        for data in checks:
            user = data['user']
            product = data['product']
            tracked = data['tracked']
            
            # Check shipping at primary store with user's ZIP
            result = await self.walmart_scraper.check_price(
                product.url,
                user.primary_store_id,
                user.zip_code
            )
            
            await self._process_result(data, result, 'shipping')
            
            # Check pickup at additional stores
            for store in data['pickup_stores']:
                result = await self.walmart_scraper.check_price(
                    product.url,
                    store.store_id,
                    store.zip_code
                )
                
                await self._process_result(data, result, 'pickup')
    
    async def _process_target_checks(self, checks: List[Dict[str, Any]]):
        """Process Target price checks with user's ZIP code"""
        
        # Initialize Target scraper if needed
        if not self.target_scraper:
            from scrapers.target_scraper import TargetLocationScraper
            self.target_scraper = TargetLocationScraper()
            await self.target_scraper.initialize()
        
        for data in checks:
            user = data['user']
            product = data['product']
            
            # Check shipping using user's ZIP code
            result = await self.target_scraper.check_price(
                product.url, 
                zip_code=user.zip_code
            )
            
            # Set store_id to include site for clarity
            result.store_id = "target.com"
            
            await self._process_result(data, result, 'shipping')
    
    async def _process_result(self, tracking_data: Dict[str, Any], 
                            result: PriceResult, alert_type: str):
        """Process a single price check result"""
        user = tracking_data['user']
        product = tracking_data['product']
        tracked = tracking_data['tracked']
        
        self.checks_completed += 1
        
        # Log price if found
        if result.price is not None:
            self.db.log_price(
                product.id,
                result.store_id,
                result.price,
                result.shipping_available,
                result.pickup_available
            )
            
            # Update product name if needed
            if result.product_name and not product.name:
                self.db.update_product_name(product.id, result.product_name)
        
        # Check if alert should be sent
        if result.price and result.price <= tracked.threshold:
            should_alert = self.db.should_send_alert(
                user.id,
                product.id,
                result.store_id,
                alert_type,
                result.price,
                tracked.threshold
            )
            
            if should_alert:
                await self._send_alert(
                    user, product, tracked,
                    result, alert_type
                )
    
    async def _send_alert(self, user, product, tracked, result: PriceResult, alert_type: str):
        """Send price alert"""
        
        product_name = product.name or result.product_name or "Product"
        
        success = False
        
        if alert_type == 'shipping':
            if not result.shipping_available:
                return
            
            success = await self.dm_alerts.send_shipping_alert(
                user.discord_id,
                product_name,
                result.price,
                tracked.threshold,
                product.url,
                result.store_id,
                product.site
            )
        
        elif alert_type == 'pickup' and product.site == 'walmart':
            if not result.pickup_available:
                return
            
            # Get store ZIP for pickup alerts
            store_zip = user.zip_code
            for store in self.db.get_user_stores(user.id):
                if store.store_id == result.store_id:
                    store_zip = store.zip_code
                    break
            
            success = await self.dm_alerts.send_pickup_alert(
                user.discord_id,
                product_name,
                result.price,
                tracked.threshold,
                product.url,
                result.store_id,
                store_zip
            )
        
        if success:
            self.alerts_sent += 1
            self.db.record_alert_sent(
                user.id,
                product.id,
                result.store_id,
                alert_type,
                result.price
            )
            
            logger.info(f"✅ {alert_type} alert sent to {user.name} for {product_name}")
    
    @commands.command(name='forceprice')
    @commands.is_owner()
    async def force_price_check(self, ctx):
        """Force a price check (owner only)"""
        if self.is_running:
            await ctx.send("❌ Price check already running")
            return
        
        await ctx.send("🔄 Starting manual price check...")
        await self._run_price_checks()
        await ctx.send("✅ Manual price check completed!")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get price checker statistics"""
        return {
            'checks_completed': self.checks_completed,
            'alerts_sent': self.alerts_sent,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'is_running': self.is_running,
            'walmart_scraper': 'active',
            'target_scraper': 'active' if self.target_scraper else 'inactive'
        }

async def setup(bot):
    """Setup function for Discord.py 2.0+"""
    await bot.add_cog(PriceChecker(bot))