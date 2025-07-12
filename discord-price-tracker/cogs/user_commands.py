#!/usr/bin/env python3
"""User commands cog"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging

from utils import (
    validate_url, validate_threshold, validate_store_id, 
    validate_zip_code, extract_product_name, format_price,
    format_store_info, truncate_text
)

logger = logging.getLogger(__name__)

class UserCommands(commands.Cog):
    """User commands for tracking products"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    def check_user(self, interaction: discord.Interaction):
        """Check if user exists"""
        user = self.db.get_user(str(interaction.user.id))
        if not user:
            embed = discord.Embed(
                title="❌ No Account",
                description="You don't have an account yet.\n\n"
                           "Ask an admin to create one with:\n"
                           "`/admin createuser`",
                color=0xff0000
            )
            return None, embed
        return user, None
    
    @app_commands.command(name="add", description="Track a product")
    @app_commands.describe(
        url="Product URL (Walmart or Target)",
        threshold="Alert when price drops below this amount"
    )
    async def add_product(self, interaction: discord.Interaction, url: str, threshold: float):
        """Add product to tracking"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Validate URL
        valid, message, product_id, site = validate_url(url)
        if not valid:
            embed = discord.Embed(
                title="❌ Invalid URL",
                description=message,
                color=0xff0000
            )
            embed.add_field(
                name="✅ Valid Examples",
                value="**Walmart:** `https://walmart.com/ip/product-name/12345`\n"
                      "**Target:** `https://target.com/p/product-name/-/A-12345678`",
                inline=False
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Validate threshold
        valid, message = validate_threshold(threshold)
        if not valid:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create/get product
            product_db_id = self.db.create_product(url, None, site)
            
            # Check if already tracking
            user_products = self.db.get_user_products(user.id)
            for tracked, product in user_products:
                if product.url == url:
                    await interaction.followup.send(
                        f"⚠️ Already tracking this product at ${tracked.threshold:.2f}",
                        ephemeral=True
                    )
                    return
            
            # Add tracking
            tracking_id = self.db.add_tracked_product(user.id, product_db_id, threshold)
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Product Added",
                description=f"Now tracking: **{extract_product_name(url, site)}**",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="🎯 Threshold", value=format_price(threshold), inline=True)
            embed.add_field(name="🛍️ Site", value=site.title(), inline=True)
            embed.add_field(name="📦 ID", value=f"#{tracking_id}", inline=True)
            
            # Location info
            if site == "walmart":
                stores_count = 1 + len(self.db.get_user_stores(user.id))
                embed.add_field(
                    name="🏪 Checking at",
                    value=f"Shipping: Store #{user.primary_store_id} (ZIP: {user.zip_code})\n"
                          f"Pickup: {stores_count - 1} additional store(s)",
                    inline=False
                )
            else:  # Target
                embed.add_field(
                    name="📍 Shipping Location",
                    value=f"Checking from ZIP: {user.zip_code}",
                    inline=False
                )
            
            embed.set_footer(text="Use /list to see all your products")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"User {user.name} added {site} product: {product_id}")
            
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="list", description="Show your tracked products")
    @app_commands.describe(page="Page number")
    async def list_products(self, interaction: discord.Interaction, page: int = 1):
        """List tracked products"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Get products
        user_products = self.db.get_user_products(user.id)
        
        if not user_products:
            embed = discord.Embed(
                title="📦 Your Products",
                description="You're not tracking any products yet.\n\n"
                           "Use `/add` to start tracking!",
                color=0x0099ff
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Pagination
        per_page = 5
        total_pages = (len(user_products) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        
        start = (page - 1) * per_page
        end = start + per_page
        
        embed = discord.Embed(
            title="📦 Your Tracked Products",
            description=f"Page {page}/{total_pages} ({len(user_products)} total)",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        
        for tracked, product in user_products[start:end]:
            name = product.name or extract_product_name(product.url, product.site)
            name = truncate_text(name, 50)
            
            embed.add_field(
                name=f"#{tracked.id} • {name}",
                value=f"💰 Threshold: **{format_price(tracked.threshold)}**\n"
                      f"🛍️ Site: {product.site.title()}\n"
                      f"📅 Added: {tracked.created_at[:10]}\n"
                      f"[View Product]({product.url})",
                inline=False
            )
        
        # Add location info
        pickup_stores = self.db.get_user_stores(user.id)
        location_info = f"🚛 **Shipping:** ZIP {user.zip_code}"
        if pickup_stores:
            location_info += f"\n🏪 **Walmart Pickup:** {len(pickup_stores)} store(s)"
        
        embed.add_field(
            name="📍 Your Locations",
            value=location_info,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="remove", description="Stop tracking a product")
    @app_commands.describe(product_id="Product ID from /list")
    async def remove_product(self, interaction: discord.Interaction, product_id: int):
        """Remove tracked product"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Find product
        user_products = self.db.get_user_products(user.id)
        found = None
        
        for tracked, product in user_products:
            if tracked.id == product_id:
                found = (tracked, product)
                break
        
        if not found:
            await interaction.response.send_message(
                f"❌ Product #{product_id} not found",
                ephemeral=True
            )
            return
        
        tracked, product = found
        
        # Remove
        if self.db.remove_tracked_product(user.id, product_id):
            name = product.name or extract_product_name(product.url, product.site)
            
            embed = discord.Embed(
                title="✅ Product Removed",
                description=f"Stopped tracking: **{name}**",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"User {user.name} removed product #{product_id}")
        else:
            await interaction.response.send_message("❌ Failed to remove", ephemeral=True)
    
    @app_commands.command(name="profile", description="Show your profile")
    async def profile(self, interaction: discord.Interaction):
        """Show user profile"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Get stats
        products = self.db.get_user_products(user.id)
        stores = self.db.get_user_stores(user.id)
        
        embed = discord.Embed(
            title=f"👤 {user.name}",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🏪 Walmart Primary Store",
            value=format_store_info(user.primary_store_id, user.zip_code),
            inline=True
        )
        
        embed.add_field(
            name="📍 Shipping ZIP",
            value=user.zip_code,
            inline=True
        )
        
        embed.add_field(name="📦 Products", value=str(len(products)), inline=True)
        embed.add_field(name="🏪 Pickup Stores", value=str(len(stores)), inline=True)
        
        embed.add_field(
            name="🔔 Notifications",
            value="✅ Enabled" if user.notifications_enabled else "❌ Disabled",
            inline=True
        )
        
        embed.set_footer(text=f"Member since {user.created_at[:10]}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Store management group (Walmart pickup only)
    store_group = app_commands.Group(name="store", description="Manage Walmart pickup stores")
    
    @store_group.command(name="add", description="Add a Walmart pickup store")
    @app_commands.describe(
        store_id="Walmart store ID",
        zip_code="Store ZIP code"
    )
    async def add_store(self, interaction: discord.Interaction, store_id: str, zip_code: str):
        """Add Walmart pickup store"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Validate
        valid, store_id = validate_store_id(store_id)
        if not valid:
            await interaction.response.send_message(f"❌ {store_id}", ephemeral=True)
            return
        
        valid, zip_code = validate_zip_code(zip_code)
        if not valid:
            await interaction.response.send_message(f"❌ {zip_code}", ephemeral=True)
            return
        
        # Check if already added
        stores = self.db.get_user_stores(user.id)
        for store in stores:
            if store.store_id == store_id:
                await interaction.response.send_message(
                    f"⚠️ Store #{store_id} already added",
                    ephemeral=True
                )
                return
        
        # Add store
        try:
            self.db.add_user_store(user.id, store_id, zip_code)
            
            embed = discord.Embed(
                title="✅ Store Added",
                description=f"Added Walmart pickup location: **Store #{store_id}**",
                color=0x00ff00
            )
            
            embed.add_field(name="📍 ZIP", value=zip_code, inline=True)
            embed.add_field(name="🏪 Total Stores", value=str(len(stores) + 1), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"User {user.name} added store #{store_id}")
            
        except Exception as e:
            logger.error(f"Error adding store: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
    
    @store_group.command(name="list", description="Show your Walmart stores")
    async def list_stores(self, interaction: discord.Interaction):
        """List Walmart pickup stores"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        stores = self.db.get_user_stores(user.id)
        
        embed = discord.Embed(
            title="🏪 Your Walmart Store Locations",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        
        # Primary store
        embed.add_field(
            name="🚛 Primary Store (Shipping)",
            value=format_store_info(user.primary_store_id, user.zip_code),
            inline=False
        )
        
        # Pickup stores
        if stores:
            value = "\n".join([
                format_store_info(store.store_id, store.zip_code)
                for store in stores
            ])
            embed.add_field(
                name=f"🏪 Pickup Stores ({len(stores)})",
                value=value,
                inline=False
            )
        else:
            embed.add_field(
                name="🏪 Pickup Stores",
                value="No pickup stores added.\nUse `/store add` to add one!",
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ Note",
            value="Target products use your primary ZIP code for shipping checks",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @store_group.command(name="remove", description="Remove a Walmart pickup store")
    @app_commands.describe(store_id="Store ID to remove")
    async def remove_store(self, interaction: discord.Interaction, store_id: str):
        """Remove Walmart pickup store"""
        
        # Check user
        user, error_embed = self.check_user(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Clean store ID
        store_id = ''.join(filter(str.isdigit, store_id))
        
        # Check if primary
        if store_id == user.primary_store_id:
            await interaction.response.send_message(
                "❌ Cannot remove primary store",
                ephemeral=True
            )
            return
        
        # Remove
        if self.db.remove_user_store(user.id, store_id):
            await interaction.response.send_message(
                f"✅ Removed store #{store_id}",
                ephemeral=True
            )
            logger.info(f"User {user.name} removed store #{store_id}")
        else:
            await interaction.response.send_message(
                f"❌ Store #{store_id} not found",
                ephemeral=True
            )

async def setup(bot):
    """Setup function for Discord.py 2.0+"""
    await bot.add_cog(UserCommands(bot))