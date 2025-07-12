# Discord Price Tracker Bot

A Discord bot that tracks product prices from major retailers and sends alerts when prices drop to user-specified targets.

## Features

- **Multi-retailer Support**: Currently supports Walmart and Target
- **Price Tracking**: Automatically monitors product prices
- **Price Alerts**: Sends Discord DMs when prices drop to target levels
- **User Registration**: Simple user registration system
- **Background Monitoring**: Continuous price checking in the background
- **Admin Commands**: Administrative tools for bot management

## Supported Retailers

- **Walmart** (walmart.com)
- **Target** (target.com)

## Commands

### User Commands
- `!register` - Register yourself in the database
- `!track <url> [target_price]` - Track a product for price changes
- `!alert <url> <target_price>` - Set a price alert for a product
- `!myalerts` - View your active price alerts
- `!ping` - Check bot latency

### Admin Commands
- `!initdb` - Initialize database tables (Admin only)
- `!stats` - Show bot statistics (Admin only)
- `!checknow` - Manually trigger price check (Admin only)

## Installation

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discord-price-tracker
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**
   ```bash
   cp env_example.txt .env
   ```

4. **Configure environment variables**
   Edit `.env` file and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

5. **Initialize the database**
   Run the bot once and use the `!initdb` command (requires admin permissions)

6. **Start the bot**
   ```bash
   python bot.py
   ```

## Configuration

The bot can be configured through environment variables in the `.env` file:

- `DISCORD_TOKEN` - Your Discord bot token (required)
- `DATABASE_URL` - Database connection string (defaults to SQLite)
- `SCRAPING_DELAY` - Delay between scraping requests (default: 60 seconds)
- `REQUEST_TIMEOUT` - HTTP request timeout (default: 30 seconds)
- `MAX_RETRIES` - Maximum retry attempts for failed requests (default: 3)
- `PRICE_CHECK_INTERVAL` - Background price check interval (default: 3600 seconds)
- `PRICE_CHANGE_THRESHOLD` - Minimum price change percentage for alerts (default: 0.05)
- `LOG_LEVEL` - Logging level (default: INFO)

## Usage

1. **Register**: Users must register first using `!register`
2. **Track Products**: Use `!track <product_url> [target_price]` to start tracking
3. **Set Alerts**: Use `!alert <product_url> <target_price>` to set price alerts
4. **Monitor**: The bot will automatically check prices and send alerts via DM

## Project Structure

```
discord-price-tracker/
├── bot.py                 # Main bot file
├── config.py              # Configuration settings
├── database.py            # Database models and operations
├── requirements.txt       # Python dependencies
├── env_example.txt        # Environment variables template
├── README.md             # This file
├── scrapers/             # Web scraping modules
│   ├── __init__.py
│   ├── base_scraper.py   # Base scraper class
│   ├── walmart_scraper.py
│   └── target_scraper.py
├── cogs/                 # Discord bot cogs
│   ├── __init__.py
│   ├── admin_commands.py
│   ├── user_commands.py
│   └── price_checker.py
├── utils/                # Utility functions
│   ├── __init__.py
│   ├── dm_alerts.py      # DM alert functions
│   └── helpers.py        # Helper functions
└── logs/                 # Log files directory
```

## Database Schema

The bot uses SQLAlchemy with the following models:

- **User**: Discord user information
- **Product**: Product information and current prices
- **PriceAlert**: User price alerts
- **PriceHistory**: Historical price data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot is for educational purposes. Please respect website terms of service and rate limits when scraping. The developers are not responsible for any misuse of this software.

## Support

For support, please open an issue on the GitHub repository or contact the development team. 