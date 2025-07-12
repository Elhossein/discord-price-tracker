# Stock Alert V2.0

A comprehensive Discord price tracking bot that monitors product prices from major retailers and sends alerts when prices drop below user-specified thresholds.

## 🚀 Project Structure

```
Stock-Alert-V2.0/
├── discord-price-tracker/    # Main Discord bot application
│   ├── bot.py                # Main bot entry point
│   ├── config.py             # Configuration management
│   ├── database.py           # Database models and operations
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Environment variables template
│   ├── README.md            # Detailed bot documentation
│   ├── cogs/                # Discord bot cogs
│   │   ├── admin_commands.py
│   │   ├── user_commands.py
│   │   └── price_checker.py
│   ├── scrapers/            # Web scraping modules
│   │   ├── base_scraper.py
│   │   ├── walmart_scraper.py
│   │   └── target_scraper.py
│   ├── utils/               # Utility functions
│   │   ├── dm_alerts.py
│   │   └── helpers.py
│   └── logs/                # Log files (auto-created)
├── venv/                    # Python virtual environment
└── README.md               # This file
```

## 🎯 Features

- **Multi-Retailer Support**: Walmart and Target price monitoring
- **Real-Time Alerts**: Discord DM notifications when prices drop
- **Background Monitoring**: Automated price checking every 5 minutes
- **User Management**: Registration and profile management system
- **Admin Controls**: Administrative commands for bot management
- **Location-Based**: Supports shipping and pickup price checking
- **Comprehensive Logging**: Detailed logs and error tracking

## 🛠️ Quick Start

1. **Navigate to the bot directory:**
   ```bash
   cd discord-price-tracker
   ```

2. **Follow the setup instructions in:**
   ```bash
   cat discord-price-tracker/README.md
   ```

## 📦 Supported Retailers

- **Walmart** (walmart.com) - Shipping and pickup availability
- **Target** (target.com) - Shipping availability

## 🔧 Development

This project uses:
- Python 3.8+
- Discord.py 2.3+
- SQLAlchemy for database management
- Playwright for web scraping
- SQLite for local data storage

## 🚀 Deployment

The bot is designed to run on:
- Local development machines
- Raspberry Pi (optimized for Pi 5)
- Cloud servers (AWS, GCP, etc.)
- Docker containers

## 📝 License

This project is open source. See the individual components for specific licensing information.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues and questions, please check the documentation in the `discord-price-tracker/README.md` file or create an issue in the repository. 