import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
import os
from datetime import datetime
from mercy_tracker import update_tracker, get_status, get_mercy_rules_info, validate_shard_type
from backup_manager import backup_data, restore_data
from utils import format_progress_bar, validate_amount
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
    """Load user data from JSON file with error handling"""
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
        # Try to restore from backup
        backup_data = restore_data()
        if backup_data:
            logger.info("Restored data from backup")
            return backup_data
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading data: {e}")
        return {}

def save_data(data):
    """Save user data to JSON file with backup"""
    try:
        # Create backup before saving
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
    """Bot startup event"""
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
    """Global error handler for slash commands"""
    logger.error(f"Command error in {interaction.command.name}: {error}")
    
    if interaction.response.is_done():
        await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
    else:
        await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)

@tree.command(name="open", description="Register how many shards you opened")
@app_commands.describe(
    shard_type="Type of shard (ancient, void, sacred, primal, remnant)",
    amount="How many did you open? (1-1000)"
)
async def open_shards(interaction: discord.Interaction, shard_type: str, amount: int):
    """Handle shard opening registration"""
    try:
        # Validate inputs
        if not validate_shard_type(shard_type.lower()):
            valid_types = ", ".join(VALID_SHARD_TYPES)
            await interaction.response.send_message(
                f"❌ Invalid shard type '{shard_type}'. Valid types are: {valid_types}", 
                ephemeral=True
            )
            return
        
        if not validate_amount(amount):
            await interaction.response.send_message(
                f"❌ Invalid amount. Please enter a number between 1 and {MAX_AMOUNT_PER_COMMAND}.", 
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        if user_id not in user_data:
            user_data[user_id] = {}
        
        # Update tracker
        old_count = user_data[user_id].get(shard_type.lower(), 0)
        update_tracker(user_data[user_id], shard_type.lower(), amount)
        new_count = user_data[user_id][shard_type.lower()]
        
        # Save data
        save_data(user_data)
        
        # Create response embed
        embed = discord.Embed(
            title="✅ Summons Updated",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name=f"{shard_type.title()} Shards",
            value=f"Added: **{amount}**\nPrevious: **{old_count}**\nTotal: **{new_count}**",
            inline=False
        )
        embed.set_footer(text=f"User: {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"User {interaction.user.id} updated {shard_type} by {amount}")
        
    except Exception as e:
        logger.error(f"Error in open command: {e}")
        await interaction.response.send_message("❌ An error occurred while updating your summons.", ephemeral=True)

@tree.command(name="status", description="Check your current mercy tracker status")
async def status(interaction: discord.Interaction):
    """Display user's mercy tracker status"""
    try:
        user_id = str(interaction.user.id)
        if user_id not in user_data or not user_data[user_id]:
            embed = discord.Embed(
                title="📊 Mercy Tracker Status",
                description="No data found. Use `/open` to start tracking your summons!",
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

@tree.command(name="reset", description="Reset your mercy tracker data")
@app_commands.describe(shard_type="Type of shard to reset (leave empty to reset all)")
async def reset(interaction: discord.Interaction, shard_type: str = None):
    """Reset user's mercy tracker data with confirmation"""
    try:
        user_id = str(interaction.user.id)
        
        if user_id not in user_data or not user_data[user_id]:
            await interaction.response.send_message("❌ No data to reset.", ephemeral=True)
            return
        
        # If specific shard type is provided, validate it
        if shard_type:
            shard_type_lower = shard_type.lower()
            if not validate_shard_type(shard_type_lower):
                valid_types = ", ".join(VALID_SHARD_TYPES)
                await interaction.response.send_message(
                    f"❌ Invalid shard type '{shard_type}'. Valid types are: {valid_types}", 
                    ephemeral=True
                )
                return
            
            # Check if user has data for this shard type
            if shard_type_lower not in user_data[user_id]:
                await interaction.response.send_message(
                    f"❌ No {shard_type.title()} shard data to reset.", 
                    ephemeral=True
                )
                return
        
        # Create confirmation embed
        if shard_type:
            embed = discord.Embed(
                title="⚠️ Confirm Individual Reset",
                description=f"Are you sure you want to reset your **{shard_type.title()}** shard data? This action cannot be undone.",
                color=0xff6600
            )
            current_count = user_data[user_id].get(shard_type.lower(), 0)
            embed.add_field(
                name="Current Data",
                value=f"{shard_type.title()}: {current_count}",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="⚠️ Confirm Complete Reset",
                description="Are you sure you want to reset **ALL** your mercy tracker data? This action cannot be undone.",
                color=0xff6600
            )
            # Add current data summary
            current_data = []
            for shard, count in user_data[user_id].items():
                current_data.append(f"{shard.title()}: {count}")
            
            if current_data:
                embed.add_field(
                    name="Current Data",
                    value="\n".join(current_data),
                    inline=False
                )
        
        # Create view with buttons
        view = ResetConfirmView(user_id, user_data, shard_type)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        await interaction.response.send_message("❌ An error occurred while processing reset request.", ephemeral=True)

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

class ResetConfirmView(discord.ui.View):
    """View for reset confirmation with buttons"""
    
    def __init__(self, user_id: str, user_data: dict, shard_type: str = None):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.user_data = user_data
        self.shard_type = shard_type
    
    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ You can only reset your own data.", ephemeral=True)
                return
            
            # Perform reset
            if self.shard_type:
                # Individual shard reset
                shard_type_lower = self.shard_type.lower()
                old_count = self.user_data[self.user_id].get(shard_type_lower, 0)
                if shard_type_lower in self.user_data[self.user_id]:
                    del self.user_data[self.user_id][shard_type_lower]
                
                embed = discord.Embed(
                    title="✅ Individual Reset Complete",
                    description=f"Your **{self.shard_type.title()}** shard data has been reset.\n\nPrevious count: **{old_count}**",
                    color=0x00ff00
                )
                logger.info(f"User {interaction.user.id} reset {self.shard_type} data (was {old_count})")
            else:
                # Complete reset
                self.user_data[self.user_id] = {}
                embed = discord.Embed(
                    title="✅ Complete Reset",
                    description="All your mercy tracker data has been successfully reset.",
                    color=0x00ff00
                )
                logger.info(f"User {interaction.user.id} reset all their data")
            
            save_data(self.user_data)
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error confirming reset: {e}")
            await interaction.response.send_message("❌ An error occurred during reset.", ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ This is not your reset request.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="❌ Reset Cancelled",
                description="Your data remains unchanged.",
                color=0x808080
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error cancelling reset: {e}")
            await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
    
    async def on_timeout(self):
        """Handle timeout for reset confirmation"""
        for item in self.children:
            item.disabled = True

# Get bot token from environment variable for security
bot_token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")

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
