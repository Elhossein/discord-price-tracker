#!/usr/bin/env python3
"""Discord DM alert system"""

import discord
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class DMAlerts:
    """Handle Discord DM alerts"""
    
    def __init__(self, bot):
        self.bot = bot
        self.sent_count = 0
        self.failed_count = 0
        self.fallback_channel_id = None  # Can be set via config
    
    def set_fallback_channel(self, channel_id: int):
        """Set fallback channel for failed DMs"""
        self.fallback_channel_id = channel_id
    
    async def send_shipping_alert(self, user_discord_id: str, product_name: str,
                                price: float, threshold: float, product_url: str,
                                store_id: str, site: str = "walmart", zip_info: dict = None) -> bool:
        """Send shipping availability alert"""
        
        embed = discord.Embed(
            title=f"🚛 {site.upper()} SHIPPING ALERT",
            description=f"**{product_name}** is available for shipping!",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        # Price info
        embed.add_field(
            name="💰 Current Price",
            value=f"**${price:.2f}**",
            inline=True
        )
        embed.add_field(
            name="🎯 Your Threshold",
            value=f"${threshold:.2f}",
            inline=True
        )
        
        savings = threshold - price
        savings_pct = (savings / threshold) * 100
        embed.add_field(
            name="💵 You Save",
            value=f"**${savings:.2f}** ({savings_pct:.1f}%)",
            inline=True
        )
        
        # Store info
        if site == "walmart":
            embed.add_field(
                name="📍 Store",
                value=f"Store #{store_id}",
                inline=False
            )
        else:  # Target
            embed.add_field(
                name="📍 Shipping",
                value="Target.com",
                inline=False
            )
        
        # Link
        site_name = "Walmart" if site == "walmart" else "Target"
        embed.add_field(
            name="🔗 Product Link",
            value=f"[View on {site_name}]({product_url})",
            inline=False
        )
        
        embed.set_footer(text="Price Tracker Bot • Prices may change!")
        
        return await self._send_dm_with_fallback(user_discord_id, embed)
    
    async def send_pickup_alert(self, user_discord_id: str, product_name: str,
                              price: float, threshold: float, product_url: str,
                              store_id: str, zip_code: str) -> bool:
        """Send pickup availability alert (Walmart only)"""
        
        embed = discord.Embed(
            title="🏪 WALMART PICKUP ALERT",
            description=f"**{product_name}** is available for pickup!",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        
        # Price info
        embed.add_field(
            name="💰 Current Price",
            value=f"**${price:.2f}**",
            inline=True
        )
        embed.add_field(
            name="🎯 Your Threshold",
            value=f"${threshold:.2f}",
            inline=True
        )
        
        savings = threshold - price
        savings_pct = (savings / threshold) * 100
        embed.add_field(
            name="💵 You Save",
            value=f"**${savings:.2f}** ({savings_pct:.1f}%)",
            inline=True
        )
        
        # Store info
        embed.add_field(
            name="📍 Pickup Location",
            value=f"Store #{store_id}\nZIP: {zip_code}",
            inline=False
        )
        
        # Link
        embed.add_field(
            name="🔗 Product Link",
            value=f"[View on Walmart]({product_url})",
            inline=False
        )
        
        embed.set_footer(text="Price Tracker Bot • Pickup today!")
        
        return await self._send_dm_with_fallback(user_discord_id, embed)
    
    async def send_notification(self, user_discord_id: str, title: str, 
                              message: str, color: int = 0x0099ff) -> bool:
        """Send general notification"""
        
        embed = discord.Embed(
            title=title,
            description=message,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Price Tracker Bot")
        
        return await self._send_dm_with_fallback(user_discord_id, embed)
    
    async def _send_dm_with_fallback(self, user_discord_id: str, embed: discord.Embed) -> bool:
        """Send DM to user with channel fallback"""
        # Try DM first
        dm_success = await self._send_dm(user_discord_id, embed)
        
        if not dm_success and self.fallback_channel_id:
            # Try fallback channel
            return await self._send_channel_alert(user_discord_id, embed)
        
        return dm_success
    
    async def _send_dm(self, user_discord_id: str, embed: discord.Embed) -> bool:
        """Send DM to user"""
        try:
            user = await self.bot.fetch_user(int(user_discord_id))
            await user.send(embed=embed)
            
            self.sent_count += 1
            logger.info(f"✅ DM sent to {user.name} ({user_discord_id})")
            return True
            
        except discord.Forbidden:
            self.failed_count += 1
            logger.warning(f"❌ Cannot DM {user_discord_id} - DMs disabled")
            return False
            
        except discord.NotFound:
            self.failed_count += 1
            logger.error(f"❌ User {user_discord_id} not found")
            return False
            
        except Exception as e:
            self.failed_count += 1
            logger.error(f"❌ DM failed for {user_discord_id}: {e}")
            return False
    
    async def _send_channel_alert(self, user_discord_id: str, embed: discord.Embed) -> bool:
        """Send alert to fallback channel"""
        try:
            channel = self.bot.get_channel(self.fallback_channel_id)
            if not channel:
                logger.error(f"❌ Fallback channel {self.fallback_channel_id} not found")
                return False
            
            # Add mention to embed
            try:
                user = await self.bot.fetch_user(int(user_discord_id))
                embed.description = f"🔔 <@{user_discord_id}> {embed.description}"
            except:
                embed.description = f"🔔 Alert for user {user_discord_id}: {embed.description}"
            
            await channel.send(embed=embed)
            
            self.sent_count += 1
            logger.info(f"✅ Channel alert sent for {user_discord_id} in #{channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Channel alert failed for {user_discord_id}: {e}")
            return False
    
    def get_stats(self):
        """Get alert statistics"""
        total = self.sent_count + self.failed_count
        success_rate = (self.sent_count / total * 100) if total > 0 else 0
        
        return {
            'sent': self.sent_count,
            'failed': self.failed_count,
            'success_rate': success_rate,
            'fallback_channel': self.fallback_channel_id
        }