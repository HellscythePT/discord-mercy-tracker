from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path('.') / '.env')

# Keep the bot alive using Flask
from keep_alive import keep_alive
keep_alive()

import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
import os
from datetime import datetime
from mercy_tracker import update_tracker, get_status, get_mercy_rules_info, validate_shard_type
from backup_manager import backup_data, restore_data
from utils import format_progress_bar, validate_amount, get_shard_emoji
from config import VALID_SHARD_TYPES, MAX_AMOUNT_PER_COMMAND

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DATA_FILE = "user_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            logger.info(f"Loaded data for {len(data)} users")
            return data
    except FileNotFoundError:
        logger.info("No existing data file found, starting with empty data")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON data: {e}")
        backup_data_restored = restore_data()
        if backup_data_restored:
            logger.info("Restored data from backup")
            return backup_data_restored
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}")
        return {}

def save_data(data):
    try:
        backup_data(data)
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved data for {len(data)} users")
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        raise

user_data = load_data()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    logger.info(f"Bot {bot.user} is ready")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands.")
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error(f"Command error in {interaction.command.name}: {error}")
    if interaction.response.is_done():
        await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)

# ----------- OPEN SHARD FLOW -----------

@tree.command(name="open_shard", description="Choose the shard type")
async def open_shard(interaction: discord.Interaction):
    view = ShardSelectFirstView(interaction.user.id)
    await interaction.response.send_message(
        content="Choose the shard type you opened:", view=view, ephemeral=True
    )

class ShardSelectFirstView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Ancient", style=discord.ButtonStyle.primary)
    async def ancient(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "ancient")

    @discord.ui.button(label="Void", style=discord.ButtonStyle.primary)
    async def void(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "void")

    @discord.ui.button(label="Sacred", style=discord.ButtonStyle.primary)
    async def sacred(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "sacred")

    @discord.ui.button(label="Primal", style=discord.ButtonStyle.danger)
    async def primal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        await interaction.response.edit_message(
            content="Choose an option for Primal shard:", view=PrimalRarityAmountView(self.user_id)
        )

    @discord.ui.button(label="Remnant", style=discord.ButtonStyle.secondary)
    async def remnant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "remnant")

    async def ask_amount(self, interaction: discord.Interaction, shard_type: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        await interaction.response.send_modal(OpenShardAmountModal(self.user_id, [shard_type]))

class PrimalRarityAmountView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Legendary", style=discord.ButtonStyle.primary)
    async def legendary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, ["primal_legendary"])

    @discord.ui.button(label="Mythical", style=discord.ButtonStyle.primary)
    async def mythical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, ["primal_mythical"])

    @discord.ui.button(label="Both", style=discord.ButtonStyle.success)
    async def both(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_modal(interaction, ["primal_legendary", "primal_mythical"])

    async def open_modal(self, interaction: discord.Interaction, keys: list):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        await interaction.response.send_modal(OpenShardAmountModal(self.user_id, keys))

class OpenShardAmountModal(discord.ui.Modal, title="Enter Amount"):
    def __init__(self, user_id: int, keys: list):
        super().__init__()
        self.user_id = user_id
        self.keys = keys

        self.amount_input = discord.ui.TextInput(
            label="How many shards did you open?",
            placeholder="e.g. 10",
            min_length=1,
            max_length=4
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You cannot submit this form.", ephemeral=True)
            return
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
            return
        if not validate_amount(amount):
            await interaction.response.send_message(
                f"❌ Invalid amount. Must be between 1 and {MAX_AMOUNT_PER_COMMAND}.",
                ephemeral=True
            )
            return

        user_id_str = str(self.user_id)
        if user_id_str not in user_data:
            user_data[user_id_str] = {}

        result_lines = []
        for key in self.keys:
            update_tracker(user_data[user_id_str], key, amount)
            new_total = user_data[user_id_str][key]
            label = key.replace("primal_", "").title() if "primal" in key else key.title()
            emoji = get_shard_emoji(key)
            result_lines.append(f"{emoji} {label}: +{amount} (Total: {new_total})")

        save_data(user_data)

        embed = discord.Embed(
            title="✅ Shard Update Complete",
            description="\n".join(result_lines),
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"User: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------- RESET SHARD FLOW -----------

@tree.command(name="reset_shard", description="Reset your mercy tracker using buttons")
async def reset_shard(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if user_id not in user_data or not user_data[user_id]:
        await interaction.response.send_message("❌ You have no data to reset.", ephemeral=True)
        return

    view = ResetShardTypeView(interaction.user.id)
    await interaction.response.send_message(
        content="What do you want to reset?", view=view, ephemeral=True
    )

class ResetShardTypeView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Ancient", style=discord.ButtonStyle.primary)
    async def ancient(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "ancient")

    @discord.ui.button(label="Void", style=discord.ButtonStyle.primary)
    async def void(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "void")

    @discord.ui.button(label="Sacred", style=discord.ButtonStyle.primary)
    async def sacred(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "sacred")

    @discord.ui.button(label="Primal", style=discord.ButtonStyle.danger)
    async def primal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your selection.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content="Choose which Primal mercy to reset:",
            view=ResetPrimalRarityView(self.user_id)
        )

    @discord.ui.button(label="Remnant", style=discord.ButtonStyle.secondary)
    async def remnant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "remnant")

    async def confirm(self, interaction: discord.Interaction, shard_key: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your selection.", ephemeral=True)
            return

        view = ResetConfirmView(user_id=str(self.user_id), user_data=user_data, shard_type=shard_key)
        current = user_data[str(self.user_id)].get(shard_key, 0)

        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description=f"Reset **{shard_key.title()}** data?\nCurrent: **{current}**",
            color=0xff6600
        )
        await interaction.response.edit_message(embed=embed, view=view)

class ResetPrimalRarityView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Legendary", style=discord.ButtonStyle.primary)
    async def legendary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "primal_legendary")

    @discord.ui.button(label="Mythical", style=discord.ButtonStyle.primary)
    async def mythical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "primal_mythical")

    @discord.ui.button(label="Ambos", style=discord.ButtonStyle.success)
    async def both(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, None)  # Reset both

    async def confirm(self, interaction: discord.Interaction, shard_key: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your selection.", ephemeral=True)
            return

        view = ResetConfirmView(user_id=str(self.user_id), user_data=user_data, shard_type=shard_key)

        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description="You're about to reset the following:",
            color=0xff6600
        )

    @discord.ui.button(label="Legendary", style=discord.ButtonStyle.primary)
    async def legendary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "primal_legendary")

    @discord.ui.button(label="Mythical", style=discord.ButtonStyle.primary)
    async def mythical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, "primal_mythical")

    @discord.ui.button(label="Both", style=discord.ButtonStyle.success)
    async def both(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirm(interaction, None)  # Reset both

    async def confirm(self, interaction: discord.Interaction, shard_key: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your selection.", ephemeral=True)
            return

        view = ResetConfirmView(user_id=str(self.user_id), user_data=user_data, shard_type=shard_key)

        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description="You're about to reset the following:",
            color=0xff6600
        )

        if shard_key is None:
            embed.add_field(name="Primal Legendary", value=f"🔸 {user_data[str(self.user_id)].get('primal_legendary', 0)}")
            embed.add_field(name="Primal Mythical", value=f"🔸 {user_data[str(self.user_id)].get('primal_mythical', 0)}")
        else:
            label = "Legendary" if "legendary" in shard_key else "Mythical"
            emoji = "🟡" if "legendary" in shard_key else "🔴"
            embed.add_field(name=f"{emoji} Primal {label}", value=f"Current: {user_data[str(self.user_id)].get(shard_key, 0)}")

        await interaction.response.edit_message(embed=embed, view=view)

class ResetConfirmView(discord.ui.View):
    def __init__(self, user_id: str, user_data: dict, shard_type: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_data = user_data
        self.shard_type = shard_type

    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your reset request.", ephemeral=True)
            return

        if self.shard_type is None:
            # Reset both Primal Legendary and Mythical
            self.user_data[self.user_id]["primal_legendary"] = 0
            self.user_data[self.user_id]["primal_mythical"] = 0
        else:
            self.user_data[self.user_id][self.shard_type] = 0

        save_data(self.user_data)

        embed = discord.Embed(
            title="✅ Data Reset",
            description="Selected mercy tracker data has been reset.",
            color=0x00ff00
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        logger.info(f"User {self.user_id} reset data for {self.shard_type}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your request.", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="Your data remains unchanged.",
            color=0x808080
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

# This ResetConfirmView you already have, it handles confirming or canceling the reset.

# ----------- RESET ALL SHARDS -----------

@tree.command(name="reset_all_shards", description="Reset all your shard tracking data")
async def reset_all_shards(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if user_id not in user_data or not user_data[user_id]:
        await interaction.response.send_message("❌ You have no data to reset.", ephemeral=True)
        return

    summary_lines = []
    for shard, count in user_data[user_id].items():
        emoji = get_shard_emoji(shard)
        summary_lines.append(f"{emoji} {shard.replace('_', ' ').title()}: {count}")

    embed = discord.Embed(
        title="⚠️ Confirm Reset of ALL Data",
        description="This will delete all your shard tracking data.\n**This cannot be undone.**",
        color=0xff0000
    )
    embed.add_field(name="Current Data", value="\n".join(summary_lines), inline=False)
    embed.set_footer(text=f"User: {interaction.user.display_name}")

    view = ResetAllConfirmView(user_id, user_data)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ResetAllConfirmView(discord.ui.View):
    def __init__(self, user_id: str, user_data: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_data = user_data

    @discord.ui.button(label="✅ Confirm Reset All", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your reset request.", ephemeral=True)
            return

        self.user_data[self.user_id] = {}
        save_data(self.user_data)

        embed = discord.Embed(
            title="✅ All Data Reset",
            description="Your mercy tracker has been fully cleared.",
            color=0x00ff00
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        logger.info(f"User {self.user_id} reset all data using /reset_all_shards")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your request.", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="Your data remains unchanged.",
            color=0x808080
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

# ----------- STATUS COMMAND -----------

@tree.command(name="status", description="Check your current mercy tracker status")
async def status(interaction: discord.Interaction):
    try:
        user_id = str(interaction.user.id)
        if user_id not in user_data or not user_data[user_id]:
            embed = discord.Embed(
                title="📊 Mercy Tracker Status",
                description="No data found. Use `/open_shard` to start tracking your summons!",
                color=0xffa500
            )
            await interaction.response.send_message(embed=embed)
            return

        status_report = get_status(user_data[user_id])

        embed = discord.Embed(
            title="📊 Mercy Tracker Status",
            description=status_report,
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"User: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
        logger.info(f"User {interaction.user.id} checked status")

    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await interaction.response.send_message("❌ An error occurred while retrieving your status.", ephemeral=True)

# ----------- HELP, MERCY_INFO and other commands -----------
@tree.command(name="mercy_info", description="View mercy system rules and thresholds")
async def mercy_info(interaction: discord.Interaction):
    """Display mercy system information"""
    try:
        info = get_mercy_rules_info()
        
        embed = discord.Embed(
            title="🎯 Mercy System Rules",
            description="Here are the mercy thresholds for each shard type:",
            color=0x9932cc
        )
        
        embed.add_field(
            name="How it works",
            value="• Mercy activates after a certain number of summons without getting the target rarity\n• Once activated, your chance increases with each additional summon\n• Mercy resets when you pull the target rarity",
            inline=False
        )
        
        embed.add_field(name="Mercy Rules", value=info, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in mercy_info command: {e}")
        await interaction.response.send_message("❌ An error occurred while retrieving mercy information.", ephemeral=True)

@tree.command(name="help", description="Show detailed help for all commands")
async def help_command(interaction: discord.Interaction):
    """Display comprehensive help information"""
    try:
        embed = discord.Embed(
            title="🤖 Mercy Tracker Bot Help",
            description="Track your Raid: Shadow Legends mercy progress with ease!",
            color=0x00ff99
        )
        
        # Commands section
        commands_info = [
            "**`/open <shard_type> <amount>`** - Log opened shards",
            "**`/status`** - View your mercy progress",
            "**`/reset [shard_type]`** - Reset data (all or specific shard type)",
            "**`/mercy_info`** - View mercy system rules",
            "**`/help`** - Show this help message"
        ]
        
        embed.add_field(
            name="📋 Commands",
            value="\n".join(commands_info),
            inline=False
        )
        
        # Shard types section
        shard_info = [
            "**Ancient** - Legendary mercy at 200 summons",
            "**Void** - Legendary mercy at 200 summons",
            "**Sacred** - Legendary mercy at 12 summons",
            "**Primal** - Legendary mercy at 75, Mythical at 200",
            "**Remnant** - Mythical mercy at 24 summons"
        ]
        
        embed.add_field(
            name="🔮 Supported Shard Types",
            value="\n".join(shard_info),
            inline=False
        )
        
        # Tips section
        tips = [
            "• Your data is automatically saved and backed up",
            "• Use `/mercy_info` to see detailed mercy rules",
            "• Maximum 1000 shards can be logged per command",
            "• Use `/reset ancient` to reset only Ancient shards",
            "• Use `/reset` (no shard type) to reset all data",
            "• All commands work only for you (your data is private)"
        ]
        
        embed.add_field(
            name="💡 Tips",
            value="\n".join(tips),
            inline=False
        )
        
        embed.set_footer(text="Happy summoning! 🌟")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await interaction.response.send_message("❌ An error occurred while displaying help.", ephemeral=True)

# Get bot token from environment variable
bot_token = os.getenv("DISCORD_BOT_TOKEN")

if not bot_token:
    logger.error("DISCORD_BOT_TOKEN environment variable not found!")
    print("ERROR: Please set the DISCORD_BOT_TOKEN environment variable")
    exit(1)

if __name__ == "__main__":
    try:
        bot.run(bot_token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Failed to start bot: {e}")
