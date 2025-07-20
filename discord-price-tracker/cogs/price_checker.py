#!/usr/bin/env python3
"""Price checking cog with concurrent scraping support"""

import discord
from discord.ext import commands, tasks
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

from scrapers import WalmartScraper, PriceResult
from config import Config

logger = logging.getLogger(__name__)

class PriceChecker(commands.Cog):
    """Background price checking with concurrent scraping"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.dm_alerts = bot.dm_alerts
        
        # Initialize scrapers
        self.walmart_scraper = WalmartScraper()
        self.target_scraper = None  # Initialize when needed
        
        # Concurrent scraping configuration
        self.max_concurrent_walmart = Config.MAX_CONCURRENT_WALMART  # ScrapeOps limit
        self.max_concurrent_target = Config.MAX_CONCURRENT_TARGET   # Browser-based, be conservative
        
        # Semaphores for rate limiting
        self.walmart_semaphore = asyncio.Semaphore(self.max_concurrent_walmart)
        self.target_semaphore = asyncio.Semaphore(self.max_concurrent_target)
        
        # Statistics
        self.checks_completed = 0
        self.checks_failed = 0
        self.alerts_sent = 0
        self.last_check = None
        self.is_running = False
        
        # Performance tracking
        self.concurrent_active = 0
        self.max_concurrent_used = 0
        
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
        """Run price checks for all active tracking with concurrency"""
        start_time = datetime.now()
        
        # Reset performance counters
        self.concurrent_active = 0
        self.max_concurrent_used = 0
        
        # Get all active tracking
        tracking_data = self.db.get_all_active_tracking()
        
        if not tracking_data:
            logger.info("No active tracking requests")
            return
        
        logger.info(f"Checking prices for {len(tracking_data)} tracking requests")
        
        # Build check tasks
        walmart_tasks = []
        target_tasks = []
        
        # Group checks by site and prepare tasks
        for data in tracking_data:
            if data['product'].site == 'walmart':
                walmart_tasks.extend(self._prepare_walmart_tasks(data))
            else:
                target_tasks.extend(self._prepare_target_tasks(data))
        
        logger.info(f"📊 Prepared {len(walmart_tasks)} Walmart checks, {len(target_tasks)} Target checks")
        
        # Run all tasks concurrently
        all_tasks = []
        
        # Add Walmart tasks with semaphore
        for task_data in walmart_tasks:
            task = asyncio.create_task(self._run_walmart_check_with_semaphore(task_data))
            all_tasks.append(task)
        
        # Add Target tasks with semaphore
        for task_data in target_tasks:
            task = asyncio.create_task(self._run_target_check_with_semaphore(task_data))
            all_tasks.append(task)
        
        # Wait for all tasks to complete
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
        
        # Update statistics
        duration = (datetime.now() - start_time).total_seconds()
        self.last_check = datetime.now()
        
        total_attempts = self.checks_completed + self.checks_failed
        success_rate = (self.checks_completed / total_attempts * 100) if total_attempts > 0 else 0
        
        logger.info(f"✅ Price check completed in {duration:.1f}s - "
                   f"{self.checks_completed} successful, {self.checks_failed} failed "
                   f"({success_rate:.1f}% success rate), {self.alerts_sent} alerts sent")
        logger.info(f"🚀 Max concurrent checks: {self.max_concurrent_used}")
    
    def _prepare_walmart_tasks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare Walmart check tasks"""
        tasks = []
        user = data['user']
        product = data['product']
        tracked = data['tracked']
        
        # Get all ZIP codes for this user
        user_zips = self.db.get_user_zip_codes(user.id)
        if not user_zips:
            user_zips = [{'zip_code': user.zip_code, 'is_primary': True, 'label': 'Primary'}]
        
        # Create task for each ZIP code (shipping)
        for zip_info in user_zips:
            task_data = {
                'type': 'walmart_shipping',
                'data': data.copy(),
                'zip_info': zip_info,
                'store_id': user.primary_store_id,
                'zip_code': zip_info['zip_code']
            }
            tasks.append(task_data)
        
        # Create tasks for pickup stores
        for store in data['pickup_stores']:
            task_data = {
                'type': 'walmart_pickup',
                'data': data.copy(),
                'store': store,
                'store_id': store.store_id,
                'zip_code': store.zip_code
            }
            tasks.append(task_data)
        
        return tasks
    
    def _prepare_target_tasks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare Target check tasks"""
        tasks = []
        user = data['user']
        product = data['product']
        
        # Get all ZIP codes for this user
        user_zips = self.db.get_user_zip_codes(user.id)
        if not user_zips:
            user_zips = [{'zip_code': user.zip_code, 'is_primary': True, 'label': 'Primary'}]
        
        # Create task for each ZIP code
        for zip_info in user_zips:
            task_data = {
                'type': 'target_shipping',
                'data': data.copy(),
                'zip_info': zip_info,
                'zip_code': zip_info['zip_code']
            }
            tasks.append(task_data)
        
        return tasks
    
    async def _run_walmart_check_with_semaphore(self, task_data: Dict[str, Any]):
        """Run Walmart check with semaphore for rate limiting"""
        async with self.walmart_semaphore:
            # Track concurrent usage
            self.concurrent_active += 1
            self.max_concurrent_used = max(self.max_concurrent_used, self.concurrent_active)
            
            try:
                user = task_data['data']['user']
                product = task_data['data']['product']
                
                logger.debug(f"🔄 Walmart check: {product.url} from {task_data['zip_code']} "
                           f"(active: {self.concurrent_active})")
                
                # Perform the actual check
                result = await self.walmart_scraper.check_price(
                    product.url,
                    task_data['store_id'],
                    task_data['zip_code']
                )
                
                # Process based on type
                if task_data['type'] == 'walmart_shipping':
                    # Fix store_id for non-primary ZIPs
                    if result.store_id and task_data['zip_code'] != user.zip_code:
                        result.store_id = f"{result.store_id}-{task_data['zip_code']}"
                    
                    # Add ZIP info to tracking data
                    task_data['data']['current_zip'] = task_data['zip_info']
                    
                    await self._process_result(task_data['data'], result, 'shipping')
                else:
                    # Pickup
                    await self._process_result(task_data['data'], result, 'pickup')
                    
            except Exception as e:
                logger.error(f"Error in Walmart check: {e}")
                self.checks_failed += 1
            finally:
                self.concurrent_active -= 1
    
    async def _run_target_check_with_semaphore(self, task_data: Dict[str, Any]):
        """Run Target check with semaphore for rate limiting"""
        # Initialize Target scraper if needed
        if not self.target_scraper:
            from scrapers.target_scraper import TargetLocationScraper
            self.target_scraper = TargetLocationScraper()
            await self.target_scraper.initialize()
        
        async with self.target_semaphore:
            # Track concurrent usage
            self.concurrent_active += 1
            self.max_concurrent_used = max(self.max_concurrent_used, self.concurrent_active)
            
            try:
                product = task_data['data']['product']
                zip_code = task_data['zip_code']
                
                logger.debug(f"🔄 Target check: {product.url} from {zip_code} "
                           f"(active: {self.concurrent_active})")
                
                # Perform the actual check
                result = await self.target_scraper.check_price(
                    product.url,
                    zip_code=zip_code
                )
                
                # Fix store_id
                result.store_id = f"target-{zip_code}"
                
                # Add ZIP info to tracking data
                task_data['data']['current_zip'] = task_data['zip_info']
                
                await self._process_result(task_data['data'], result, 'shipping')
                
            except Exception as e:
                logger.error(f"Error in Target check: {e}")
                self.checks_failed += 1
            finally:
                self.concurrent_active -= 1
    
    async def _process_result(self, tracking_data: Dict[str, Any], 
                            result: PriceResult, alert_type: str):
        """Process a single price check result"""
        user = tracking_data['user']
        product = tracking_data['product']
        tracked = tracking_data['tracked']
        
        # Check for scraper errors first
        if result.error is not None:
            self.checks_failed += 1
            logger.warning(f"❌ Scraper error for {product.url} (user: {user.name}): {result.error}")
            return
        
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
        
        # Check alert logic
        if result.price is not None:
            # Determine availability based on alert type
            availability = result.shipping_available if alert_type == 'shipping' else result.pickup_available
            
            should_alert = self.db.should_send_alert(
                user.id,
                product.id,
                result.store_id,
                alert_type,
                result.price,
                tracked.threshold,
                availability
            )
            
            if should_alert and result.price <= tracked.threshold:
                # Get ZIP info if available
                zip_info = tracking_data.get('current_zip')
                await self._send_alert(
                    user, product, tracked,
                    result, alert_type, zip_info
                )
                
                logger.info(f"💰 Price alert triggered: {product.url} at ${result.price} " +
                           f"(threshold ${tracked.threshold}) for {user.name} " +
                           f"from {zip_info.get('label', 'Unknown location') if zip_info else 'Unknown location'}")
    
    async def _send_alert(self, user, product, tracked, result: PriceResult, alert_type: str, zip_info: Optional[Dict] = None):
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
                product.site,
                zip_info
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
            
            # Determine availability for recording
            availability = result.shipping_available if alert_type == 'shipping' else result.pickup_available
            
            self.db.record_alert_sent(
                user.id,
                product.id,
                result.store_id,
                alert_type,
                result.price,
                availability
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
        total_attempts = self.checks_completed + self.checks_failed
        success_rate = (self.checks_completed / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            'checks_completed': self.checks_completed,
            'checks_failed': self.checks_failed,
            'total_attempts': total_attempts,
            'success_rate': success_rate,
            'alerts_sent': self.alerts_sent,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'is_running': self.is_running,
            'walmart_scraper': f'active (max {self.max_concurrent_walmart} concurrent)',
            'target_scraper': f'active (max {self.max_concurrent_target} concurrent)' if self.target_scraper else 'inactive',
            'max_concurrent_used': self.max_concurrent_used
        }

async def setup(bot):
    """Setup function for Discord.py 2.0+"""
    await bot.add_cog(PriceChecker(bot))