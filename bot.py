import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path('.') / '.env')

# Keep the bot alive using Flask
from keep_alive import keep_alive
keep_alive()

import discord
from discord.ext import commands, tasks
from discord import app_commands

import json
import logging
from datetime import datetime, timedelta
from mercy_tracker import update_tracker, get_status, get_mercy_rules_info, validate_shard_type
from backup_manager import backup_data, restore_data
from utils import format_progress_bar, validate_amount, get_shard_emoji
from config import VALID_SHARD_TYPES, MAX_AMOUNT_PER_COMMAND

# ---------------------------- MERCY TRACKER BOT CODE ----------------------------
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
intents.message_content = True

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

@tree.command(name="open", description="Choose the shard type")
async def open_shard(interaction: discord.Interaction):
    view = ShardSelectFirstView(interaction.user.id)
    await interaction.response.send_message(
        content="Choose the shard type:", view=view, ephemeral=True
    )

class ShardSelectFirstView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Ancient", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("ancient"))
    async def ancient(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "ancient")

    @discord.ui.button(label="Void", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("void"))
    async def void(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "void")

    @discord.ui.button(label="Sacred", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("sacred"))
    async def sacred(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "sacred")

    @discord.ui.button(label="Primal", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("primal"))
    async def primal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        await interaction.response.edit_message(
            content="Choose an option for Primal shard:", view=PrimalRarityAmountView(self.user_id)
        )

    @discord.ui.button(label="Remnant", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("remnant"))
    async def remnant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "remnant")

    async def ask_amount(self, interaction: discord.Interaction, shard_type: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{interaction.user.mention}, please enter the amount of {shard_type.title()} shards you opened (1-{MAX_AMOUNT_PER_COMMAND}):"
        )

        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel == interaction.channel
                and m.content.isdigit()
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            amount = int(msg.content)
            if not validate_amount(amount):
                await interaction.followup.send(
                    f"❌ Invalid amount. Must be between 1 and {MAX_AMOUNT_PER_COMMAND}.", ephemeral=True
                )
                return

            user_id_str = str(self.user_id)
            if user_id_str not in user_data:
                user_data[user_id_str] = {}

            update_tracker(user_data[user_id_str], shard_type, amount)
            new_total = user_data[user_id_str][shard_type]
            save_data(user_data)

            emoji = get_shard_emoji(shard_type)
            embed = discord.Embed(
                title="✅ Shard Update Complete",
                description=f"{emoji} {shard_type.title()}: +{amount} (Total: {new_total})",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"User: {interaction.user.display_name}")

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ No valid amount received. Please try again.", ephemeral=True)

class PrimalRarityAmountView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Legendary", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("primal_legendary"))
    async def legendary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "primal_legendary")

    @discord.ui.button(label="Mythical", style=discord.ButtonStyle.secondary, emoji=get_shard_emoji("primal_mythical"))
    async def mythical(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "primal_mythical")

    @discord.ui.button(label="Both", style=discord.ButtonStyle.success)
    async def both(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_amount(interaction, "both")

    async def ask_amount(self, interaction: discord.Interaction, key: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your selection.", ephemeral=True)
            return
        if key == "both":
            keys = ["primal_legendary", "primal_mythical"]
            label = "Primal Legendary and Mythical"
        else:
            keys = [key]
            label = key.replace("primal_", "").title()

        await interaction.response.send_message(
            f"{interaction.user.mention}, please enter the amount of {label} shards you opened (1-{MAX_AMOUNT_PER_COMMAND}):"
        )

        def check(m):
            return (
                m.author.id == interaction.user.id
                and m.channel == interaction.channel
                and m.content.isdigit()
            )

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            amount = int(msg.content)
            if not validate_amount(amount):
                await interaction.followup.send(
                    f"❌ Invalid amount. Must be between 1 and {MAX_AMOUNT_PER_COMMAND}.", ephemeral=True
                )
                return

            user_id_str = str(self.user_id)
            if user_id_str not in user_data:
                user_data[user_id_str] = {}

            result_lines = []
            for k in keys:
                update_tracker(user_data[user_id_str], k, amount)
                new_total = user_data[user_id_str][k]
                label = k.replace("primal_", "").title()
                emoji = get_shard_emoji(k)
                result_lines.append(f"{emoji} {label}: +{amount} (Total: {new_total})")

            save_data(user_data)

            embed = discord.Embed(
                title="✅ Shard Update Complete",
                description="\n".join(result_lines),
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f"User: {interaction.user.display_name}")

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ No valid amount received. Please try again.", ephemeral=True)

# ----------- RESET SHARD FLOW -----------

def build_current_data_embed(title, desc, user_data, user_id, shard_type=None):
    embed = discord.Embed(title=title, description=desc, color=0xff6600)
    if shard_type == "primal":
        primal = user_data[user_id]
        embed.add_field(
            name="Current Data",
            value=f"Legendary: {primal.get('primal_legendary', 0)}\nMythical: {primal.get('primal_mythical', 0)}",
            inline=False
        )
    elif shard_type:
        emoji = get_shard_emoji(shard_type)
        count = user_data[user_id].get(shard_type, 0)
        embed.add_field(
            name="Current Data",
            value=f"{emoji} {shard_type.title()}: {count}",
            inline=False
        )
    else:
        current_data = [f"{shard.replace('_', ' ').title()}: {count}" for shard, count in user_data[user_id].items()]
        if current_data:
            embed.add_field(
                name="Current Data",
                value="\n".join(current_data),
                inline=False
            )
    return embed

class ResetConfirmView(discord.ui.View):
    def __init__(self, user_id, user_data, shard_type=None):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.user_data = user_data
        self.shard_type = shard_type

    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ You can only reset your own data.", ephemeral=True)
            return
        if self.shard_type == "primal":
            self.user_data[self.user_id]["primal_legendary"] = 0
            self.user_data[self.user_id]["primal_mythical"] = 0
            desc = "Both Primal Legendary and Mythical have been reset."
        elif self.shard_type:
            old_count = self.user_data[self.user_id].get(self.shard_type, 0)
            self.user_data[self.user_id][self.shard_type] = 0
            desc = f"Your **{self.shard_type.title()}** shard data has been reset.\nPrevious count: **{old_count}**"
        else:
            self.user_data[self.user_id] = {}
            desc = "All your mercy tracker data has been successfully reset."
        save_data(self.user_data)
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title="✅ Data Reset",
            description=desc,
            color=0x00ff00
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your reset request.", ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="Your data remains unchanged.",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=self)

class PrimalResetSelect(discord.ui.View):
    def __init__(self, user_id, user_data):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_data = user_data
        self.select = discord.ui.Select(
            placeholder="Select Primal counter to reset...",
            options=[
                discord.SelectOption(label="Legendary", value="primal_legendary", emoji=get_shard_emoji("primal_legendary")),
                discord.SelectOption(label="Mythical", value="primal_mythical", emoji=get_shard_emoji("primal_mythical")),
                discord.SelectOption(label="Both", value="primal", emoji="🔄"),
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return
        shard_type = self.select.values[0]
        embed = build_current_data_embed(
            "⚠️ Confirm Primal Reset",
            "Are you sure you want to reset the selected Primal counter(s)?",
            self.user_data, self.user_id, shard_type if shard_type != "primal" else "primal"
        )
        view = ResetConfirmView(self.user_id, self.user_data, shard_type)
        await interaction.response.edit_message(embed=embed, view=view)

class ShardResetSelect(discord.ui.View):
    def __init__(self, user_id, user_data):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_data = user_data
        self.select = discord.ui.Select(
            placeholder="Select what to reset...",
            options=[
                discord.SelectOption(label="Reset All", value="reset_all", emoji="🗑️"),
                discord.SelectOption(label="Ancient", value="ancient", emoji=get_shard_emoji("ancient")),
                discord.SelectOption(label="Void", value="void", emoji=get_shard_emoji("void")),
                discord.SelectOption(label="Sacred", value="sacred", emoji=get_shard_emoji("sacred")),
                discord.SelectOption(label="Primal", value="primal", emoji=get_shard_emoji("primal")),
                discord.SelectOption(label="Remnant", value="remnant", emoji=get_shard_emoji("remnant")),
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return
        shard_type = self.select.values[0]
        if shard_type == "reset_all":
            embed = build_current_data_embed(
                "⚠️ Confirm Complete Reset",
                "Are you sure you want to reset **ALL** your mercy tracker data? This action cannot be undone.",
                self.user_data, self.user_id
            )
            view = ResetConfirmView(self.user_id, self.user_data, None)
            await interaction.response.edit_message(embed=embed, view=view)
        elif shard_type == "primal":
            embed = build_current_data_embed(
                "Primal Reset",
                "Choose which Primal counter to reset:",
                self.user_data, self.user_id, "primal"
            )
            view = PrimalResetSelect(self.user_id, self.user_data)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            embed = build_current_data_embed(
                "⚠️ Confirm Individual Reset",
                f"Are you sure you want to reset your {get_shard_emoji(shard_type)} **{shard_type.title()}** shard data? This action cannot be undone.",
                self.user_data, self.user_id, shard_type
            )
            view = ResetConfirmView(self.user_id, self.user_data, shard_type)
            await interaction.response.edit_message(embed=embed, view=view)

@tree.command(name="reset", description="Reset your mercy tracker data")
async def reset(interaction: discord.Interaction):
    """Reset user's mercy tracker data with menu selection"""
    try:
        user_id = str(interaction.user.id)
        if user_id not in user_data or not user_data[user_id]:
            await interaction.response.send_message("❌ No data to reset.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Reset Mercy Tracker Data",
            description="Select what you want to reset.",
            color=0xff6600
        )
        view = ShardResetSelect(user_id, user_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        await interaction.response.send_message("❌ An error occurred while processing reset request.", ephemeral=True)

# ----------- STATUS COMMAND -----------

@tree.command(name="status", description="Check your current mercy tracker status")
async def status(interaction: discord.Interaction):
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
            "**`/open`** - Log opened shards",
            "**`/status`** - View your mercy progress",
            "**`/reset`** - Reset data (all or specific shard type)",
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
            "• Maximum 500 shards can be logged per command",
            "• Use `/reset` to prompt for a reset menu",
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
# ----------- END OF MERCY TRACKER BOT CODE ------------

# ----------- REMINDER BOT CODE -----------
RESET_DATA_FILE = "reset_data.json"
REMINDER_CHANNEL_NAME = "┣⏰reminder"
PING_ROLE_NAME = "ping"
PING_NOTE = "*Want to be notified?* https://discord.com/channels/955147647130431558/1124639072573456454/1128683162994741298"

REMINDER_TIMES = {
    "Doom Tower": timedelta(hours=48),
    "Cursed City": timedelta(hours=48),
    "Clan Quests": timedelta(hours=12),
    "Clan vs Clan": timedelta(hours=12),
    "Hydra": timedelta(hours=12),
    "Chimera": timedelta(hours=12),
    "Siege": timedelta(hours=24)
}

FIXED_WEEKLY = {
    "Clan Quests": {"weekday": 0, "hour": 8},
    "Hydra": {"weekday": 2, "hour": 10},
    "Chimera": {"weekday": 3, "hour": 11}
}

ROTATING_EVENTS = {
    "Doom Tower": 30,
    "Cursed City": 30,
    "Siege": 14,
    "Clan vs Clan": 14
}

sent_reminders = {}

def load_reset_data():
    if os.path.exists(RESET_DATA_FILE):
        with open(RESET_DATA_FILE, 'r') as f:
            return json.load(f)
    now = datetime.utcnow()
    data = {
        "Doom Tower": int((now + timedelta(days=11)).timestamp()),
        "Cursed City": int((now + timedelta(days=1, hours=2)).timestamp()),
        "Siege": int(datetime(2025, 8, 5, 12, 0).timestamp()),
        "Clan vs Clan": int(datetime(2025, 8, 12, 9, 0).timestamp())
    }
    save_reset_data(data)
    return data

def save_reset_data(data):
    with open(RESET_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

reset_data = load_reset_data()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@tasks.loop(minutes=1)
async def reminder_loop():
    now = datetime.utcnow()
    if not bot.guilds:
        return
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name=REMINDER_CHANNEL_NAME)
    role = discord.utils.get(guild.roles, name=PING_ROLE_NAME)
    if not channel or not role:
        return

    for event, advance_time in REMINDER_TIMES.items():
        if event in FIXED_WEEKLY:
            day = FIXED_WEEKLY[event]["weekday"]
            hour = FIXED_WEEKLY[event]["hour"]
            today = now.date()
            days_ahead = (day - today.weekday()) % 7
            reset_dt = datetime.combine(today + timedelta(days=days_ahead), datetime.min.time()) + timedelta(hours=hour)
            if now > reset_dt:
                reset_dt += timedelta(weeks=1)
        else:
            try:
                reset_ts = reset_data[event]
                reset_dt = datetime.utcfromtimestamp(reset_ts)
            except (KeyError, ValueError):
                continue

        reminder_time = reset_dt - advance_time
        key = f"{event}:{reset_dt.isoformat()}"

        if reminder_time <= now < reminder_time + timedelta(minutes=1):
            if key not in sent_reminders:
                await channel.send(f"<@&{role.id}> **{event}** reset is coming soon!\n{PING_NOTE}")
                sent_reminders[key] = now.timestamp()

        if event in ROTATING_EVENTS and now > reset_dt:
            next_dt = reset_dt + timedelta(days=ROTATING_EVENTS[event])
            reset_data[event] = int(next_dt.timestamp())
            save_reset_data(reset_data)

    # Cleanup old reminders older than 3 days
    expiration = now.timestamp() - 3 * 86400
    sent_reminders_keys = list(sent_reminders.keys())
    for key in sent_reminders_keys:
        if sent_reminders[key] < expiration:
            del sent_reminders[key]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    logger.info(f"Bot {bot.user} is ready")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
        logger.error(f"Failed to sync commands: {e}")
    if not reminder_loop.is_running():
        reminder_loop.start()

# ----------- END OF REMINDER BOT CODE

# ----------- HEALTH CHECK COMMAND -----------#
@tree.command(name="health", description="Check if the bot is running")
async def health(interaction: discord.Interaction):
    """Simple health check command for uptime monitoring"""
    await interaction.response.send_message("✅ Bot is running and healthy!", ephemeral=True)

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
