#!/usr/bin/env python3
"""Admin commands cog"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging

from config import Config
from utils import validate_store_id, validate_zip_code

logger = logging.getLogger(__name__)

class AdminCommands(commands.Cog):
    """Admin-only commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return Config.is_admin(user_id)
    
    admin_group = app_commands.Group(name="admin", description="Admin commands")
    
    @admin_group.command(name="createuser", description="Create a new user")
    @app_commands.describe(
        discord_id="User's Discord ID",
        name="User's display name",
        store_id="Walmart primary store ID",
        zip_code="ZIP code for shipping checks (both Walmart & Target)"
    )
    async def create_user(self, interaction: discord.Interaction,
                         discord_id: str, name: str, store_id: str, zip_code: str):
        """Create a new user"""
        
        # Check admin
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        # Validate inputs
        if not discord_id.isdigit() or len(discord_id) < 17:
            await interaction.response.send_message(
                "❌ Invalid Discord ID. Must be 17-19 digits.", 
                ephemeral=True
            )
            return
        
        valid, store_id = validate_store_id(store_id)
        if not valid:
            await interaction.response.send_message(f"❌ {store_id}", ephemeral=True)
            return
        
        valid, zip_code = validate_zip_code(zip_code)
        if not valid:
            await interaction.response.send_message(f"❌ {zip_code}", ephemeral=True)
            return
        
        # Check if user exists
        if self.db.get_user(discord_id):
            await interaction.response.send_message(
                "❌ User already exists!", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create user
            user_id = self.db.create_user(discord_id, name, store_id, zip_code)
            
            # Get Discord user info
            try:
                discord_user = await self.bot.fetch_user(int(discord_id))
                avatar_url = discord_user.display_avatar.url
            except:
                discord_user = None
                avatar_url = None
            
            # Success embed
            embed = discord.Embed(
                title="✅ User Created",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="👤 Name", value=name, inline=True)
            embed.add_field(name="🆔 Discord ID", value=discord_id, inline=True)
            embed.add_field(name="💾 Database ID", value=str(user_id), inline=True)
            embed.add_field(name="🏪 Primary Store", value=f"#{store_id}", inline=True)
            embed.add_field(name="📍 ZIP Code", value=zip_code, inline=True)
            
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send welcome DM
            await self.bot.dm_alerts.send_notification(
                discord_id,
                "🎉 Welcome to Price Tracker!",
                f"Hi **{name}**!\n\n"
                f"Your account has been created.\n\n"
                f"**Your Settings:**\n"
                f"🏪 Primary Store: #{store_id}\n"
                f"📍 ZIP Code: {zip_code}\n\n"
                f"Use `/add` to start tracking products!"
            )
            
            logger.info(f"Admin {interaction.user.id} created user {name} ({discord_id})")
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @admin_group.command(name="listusers", description="List all users")
    @app_commands.describe(page="Page number")
    async def list_users(self, interaction: discord.Interaction, page: int = 1):
        """List all users"""
        
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        users = self.db.get_all_users()
        
        if not users:
            await interaction.response.send_message("No users found.", ephemeral=True)
            return
        
        # Pagination
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        
        start = (page - 1) * per_page
        end = start + per_page
        
        embed = discord.Embed(
            title="👥 User List",
            description=f"Page {page}/{total_pages} ({len(users)} total)",
            color=0x0099ff
        )
        
        for user in users[start:end]:
            # Get user stats
            products = self.db.get_user_products(user.id)
            stores = self.db.get_user_stores(user.id)
            
            embed.add_field(
                name=f"{user.name}",
                value=f"🆔 `{user.discord_id}`\n"
                      f"🏪 Store #{user.primary_store_id}\n"
                      f"📦 {len(products)} products, {len(stores)} stores",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @admin_group.command(name="deleteuser", description="Delete a user")
    @app_commands.describe(discord_id="User's Discord ID")
    async def delete_user(self, interaction: discord.Interaction, discord_id: str):
        """Delete a user"""
        
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        user = self.db.get_user(discord_id)
        if not user:
            await interaction.response.send_message("❌ User not found!", ephemeral=True)
            return
        
        # Confirmation
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Delete user **{user.name}**?\n\n"
                       f"This will remove:\n"
                       f"• User profile\n"
                       f"• All tracked products\n"
                       f"• All stores\n"
                       f"• All alert history\n\n"
                       f"**This cannot be undone!**",
            color=0xff0000
        )
        
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.value = None
            
            @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("Not for you!", ephemeral=True)
                    return
                
                self.value = True
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("Not for you!", ephemeral=True)
                    return
                
                self.value = False
                self.stop()
        
        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if view.value:
            # Delete user
            if self.db.delete_user(discord_id):
                await interaction.edit_original_response(
                    content=f"✅ User **{user.name}** deleted.",
                    embed=None,
                    view=None
                )
                logger.info(f"Admin {interaction.user.id} deleted user {user.name}")
            else:
                await interaction.edit_original_response(
                    content="❌ Failed to delete user.",
                    embed=None,
                    view=None
                )
        else:
            await interaction.edit_original_response(
                content="❌ Deletion cancelled.",
                embed=None,
                view=None
            )
    
    @admin_group.command(name="stats", description="Show bot statistics")
    async def admin_stats(self, interaction: discord.Interaction):
        """Show detailed statistics"""
        
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Admin only!", ephemeral=True)
            return
        
        # Get stats
        db_stats = self.db.get_stats()
        dm_stats = self.bot.dm_alerts.get_stats()
        
        # Price checker stats
        price_checker = self.bot.get_cog('PriceChecker')
        pc_stats = price_checker.get_stats() if price_checker else {}
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        
        # Database stats
        embed.add_field(
            name="💾 Database",
            value=f"👥 Users: {db_stats['users']}\n"
                  f"📦 Products: {db_stats['products']}\n"
                  f"🎯 Active Tracking: {db_stats['active_tracking']}\n"
                  f"📊 Price History: {db_stats['price_history']}",
            inline=True
        )
        
        # Alert stats
        embed.add_field(
            name="📨 Alerts",
            value=f"✅ Sent: {dm_stats['sent']}\n"
                  f"❌ Failed: {dm_stats['failed']}\n"
                  f"📈 Success Rate: {dm_stats['success_rate']:.1f}%\n"
                  f"🚨 Alert History: {db_stats['alert_history']}",
            inline=True
        )
        
        # Price checker stats
        if pc_stats:
            embed.add_field(
                name="🔄 Price Checker",
                value=f"✅ Success: {pc_stats['checks_completed']}\n"
                      f"❌ Failed: {pc_stats['checks_failed']}\n"
                      f"📊 Rate: {pc_stats['success_rate']:.1f}%\n"
                      f"📨 Alerts: {pc_stats['alerts_sent']}\n"
                      f"⏰ Last: {pc_stats['last_check'] or 'Never'}\n"
                      f"🏃 Running: {'Yes' if pc_stats['is_running'] else 'No'}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Setup function for Discord.py 2.0+"""
    await bot.add_cog(AdminCommands(bot))