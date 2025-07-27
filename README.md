# Mercy Tracker Bot

A Discord bot for tracking the Mercy system in Raid: Shadow Legends using slash commands. Enhanced with improved error handling, data backup, and user-friendly features.

## Features

- 🔮 Track summons for Legendary and Mythical champions
- 📊 Support for Ancient, Void, Sacred, Primal, and Remnant shards
- 💾 Automatic data backup and recovery
- 🎯 Visual progress bars and detailed mercy information
- ⚡ Slash command interface with validation
- 🛡️ Comprehensive error handling and logging
- 🔄 Data persistence with automatic backups
- 📋 Detailed help and mercy rule information

## Supported Shard Types

- **Ancient Shards**: Legendary mercy at 200 summons (+5% per summon after)
- **Void Shards**: Legendary mercy at 200 summons (+5% per summon after)
- **Sacred Shards**: Legendary mercy at 12 summons (+2% per summon after)
- **Primal Shards**: Legendary mercy at 75 summons (+1% per summon after), Mythical mercy at 200 summons (+10% per summon after)
- **Remnant Shards**: Mythical mercy at 24 summons (+1% per summon after)

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- Discord Bot Token

### 2. Installation

1. Clone or download the bot files
2. Install dependencies:
   ```bash
   pip install discord.py
   ```

### 3. Configuration

1. Create your Discord bot:
   - Go to https://discord.com/developers/applications
   - Create a new application and bot
   - Enable necessary intents (Message Content Intent may be required)
   - Copy the bot token

2. Set up the bot token:
   - **Option 1 (Recommended)**: Set environment variable:
     ```bash
     export DISCORD_BOT_TOKEN="your_bot_token_here"
     