#!/usr/bin/env python3
"""Discord Price Tracker Bot"""

import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime
import sys

from config import Config
from database import Database
from utils import DMAlerts
from cogs import COGS

# Setup logging
def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'{Config.LOG_DIR}/bot_{datetime.now():%Y%m%d}.log')
        ]
    )
    
    # Reduce noise from Discord and other libraries
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

class PriceTrackerBot(commands.Bot):
    """Main bot class"""
    
    def __init__(self):
        # Setup intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        
        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None
        )
        
        self.logger = setup_logging()
        self.db = Database(Config.DATABASE_PATH)
        self.dm_alerts = DMAlerts(self)
        
    async def setup_hook(self):
        """Initialize bot"""
        self.logger.info("🔧 Setting up bot...")
        
        # Load cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                self.logger.info(f"✅ Loaded {cog}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load {cog}: {e}")
        
        # Sync commands
        try:
            if Config.GUILD_ID:
                guild = discord.Object(id=Config.GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                self.logger.info(f"✅ Synced commands to guild {Config.GUILD_ID}")
            else:
                await self.tree.sync()
                self.logger.info("✅ Synced commands globally")
        except Exception as e:
            self.logger.error(f"❌ Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Bot is ready"""
        self.logger.info(f"🚀 {self.user} is online!")
        self.logger.info(f"🔗 Connected to {len(self.guilds)} guilds")
        self.logger.info(f"👑 Admins: {', '.join(Config.ADMIN_USER_IDS)}")
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for price drops 📉"
            )
        )
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        self.logger.error(f"Command error: {error}")

# Slash commands
@discord.app_commands.command(name="help", description="Show help information")
async def help_command(interaction: discord.Interaction):
    """Show help"""
    embed = discord.Embed(
        title="🤖 Price Tracker Bot",
        description="Track product prices with automatic alerts!",
        color=0x0099ff
    )
    
    # User commands
    embed.add_field(
        name="📦 Product Commands",
        value="`/add` - Track a product\n"
              "`/list` - Show your products\n"
              "`/remove` - Stop tracking\n"
              "`/profile` - Your profile",
        inline=False
    )
    
    embed.add_field(
        name="🏪 Store Commands",
        value="`/store add` - Add pickup store\n"
              "`/store list` - Show stores\n"
              "`/store remove` - Remove store",
        inline=False
    )
    
    # Admin commands
    if Config.is_admin(interaction.user.id):
        embed.add_field(
            name="👑 Admin Commands",
            value="`/admin createuser` - Create user\n"
                  "`/admin listusers` - List users\n"
                  "`/admin deleteuser` - Delete user\n"
                  "`/admin stats` - Bot statistics",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ Info",
        value="`/help` - This message\n"
              "`/ping` - Check bot status\n"
              "`/stats` - Basic statistics",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@discord.app_commands.command(name="ping", description="Check bot status")
async def ping(interaction: discord.Interaction):
    """Ping command"""
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {round(interaction.client.latency * 1000)}ms",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@discord.app_commands.command(name="stats", description="Show bot statistics")
async def stats(interaction: discord.Interaction):
    """Show stats"""
    db_stats = interaction.client.db.get_stats()
    
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=0x0099ff,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="👥 Users", value=db_stats['users'], inline=True)
    embed.add_field(name="📦 Products", value=db_stats['products'], inline=True)
    embed.add_field(name="🎯 Active", value=db_stats['active_tracking'], inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def main():
    """Main entry point"""
    # Validate configuration
    if not Config.validate():
        print("❌ Configuration validation failed!")
        return 1
    
    # Create bot
    bot = PriceTrackerBot()
    
    # Add slash commands
    bot.tree.add_command(help_command)
    bot.tree.add_command(ping)
    bot.tree.add_command(stats)
    
    try:
        print("🚀 Starting bot...")
        await bot.start(Config.BOT_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        return 1
    finally:
        await bot.close()
    
    return 0

if __name__ == "__main__":
    # Run bot
    exit_code = asyncio.run(main())
    sys.exit(exit_code)