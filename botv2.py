# botv2.py
# Jack the Ripper v2.0
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl

import os
import time
import random
import asyncio
import math

from dotenv import load_dotenv

from config import colores, ydl_opts
from classes import Track, LoopStatus, Server

# Uncomment when running on replit (1/3)
# from keep_alive import keep_alive

# change working directory to wherever this file is in
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# load bot token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Load admin and test server ID
admin_id = os.getenv('ADMIN_ID')
test_server_id = os.getenv('TEST_SERVER_ID')

# Uncomment when running on replit (2/3)
# discord.opus.load_opus("./libopus.so.0.8.0")

# define bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="+", intents=intents, activity=discord.Game(name="The Legend of Zelda: Link's Awakening"), help_command=None)

# Prepare profiles for servers
# Profiles are stored in a dictionary indexed by server ID
servers = {}

@bot.event
async def on_ready():
    """
    Display and initialize a profile for each connected server.
    """
    # Print server
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild(s):\n'
            f'{guild.name}(id: {guild.id})'
        )
        # Initialize profile for server
        if not servers.get(guild.id, None):  # Prevent on_ready() misfires from overwriting profiles
            servers[guild.id] = Server(guild.id)

@bot.event
async def on_guild_join(guild):
    """
    Print and initialize a profile for every new server the bot joins.
    """
    # Print server
    print(
        f'{bot.user} joined the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )
    # Initialize profile for server
    if not servers.get(guild.id, None):
        servers[guild.id] = Server(guild.id)

# Slash commands start

@bot.tree.command(description="Test test test")
async def test(interaction: discord.Interaction) -> None:
    """
    Test bot status.
    """
    test_messages = ["Yep, it's working!", "Jack the Ripper has started a break"]
    await interaction.response.send_message(random.choice(test_messages))

@bot.tree.command(description="Consume the last message in the channel!")
async def succ(interaction: discord.Interaction) -> None:
    """
    Resends the last message in a channel and deletes the original message.
    """
    # Get message to be copied and deleted
    messages = [message async for message in interaction.channel.history(limit=1)]

    # Consumption failed
    # Send error message if author is bot
    if messages[0].author.bot:
        embed_author = discord.Embed(
            title='Message is from bot!', 
            description='Jack can\'t consume bot messages.', color=colores["error"]
            )
        await interaction.response.send_message(embed=embed_author)
        return
    
    # Send error message if message is longer than 1024 characters
    if len(messages[0].clean_content) > 1024:
        embed_length = discord.Embed(
            title="Jack can't handle your length!",
            description="Message must be no longer than 1024 characters.",
            color=colores["error"]
        )
        await interaction.response.send_message(embed=embed_length)
        return
    
    # Consumption success
    # If message has attachments
    if messages[0].attachments:
        # Send confirmation message
        embed_attach = discord.Embed(
            title="Slurp!",
            description="Your message got consumed!",
            color=colores["play"]
        )
        embed_attach.add_field(name="Sender", value=f"<@{messages[0].author.id}>", inline=False)
        await interaction.response.send_message(embed=embed_attach)

        # Send attachment
        await interaction.channel.send(messages[0].content, files=[await f.to_file() for f in messages[0].attachments])
    
    # If message does not have attachments
    else:
        # Copy the 2nd last message
        content = ''
        if messages[0].content == '':
            content = 'Message content is empty!'
        else:
            content = messages[0].content

        # Send consumed message
        embed_succ = discord.Embed(
            title="Slurp!",
            description="Your message got [consumed](https://www.youtube.com/watch?v=OBAktzVvwxw)!",
            color=colores["play"]
        )
        embed_succ.add_field(name="Sender", value=f"<@{messages[0].author.id}>", inline=False)
        embed_succ.add_field(name="Message", value=content, inline=False)
        await interaction.response.send_message(embed=embed_succ)

    # Delete original message
    await messages[0].delete()

    return

@bot.tree.command(description="Make Jack join your voice channel!")
async def join(interaction: discord.Interaction) -> None:
    """
    Join/move to user's voice channel.
    """
    await interaction.response.defer(thinking=True)

    # Find profile of the user's server
    user_server: Server = servers[interaction.guild_id]

    # Status codes from voice channel connection attempt
    #   Success:
    #       0: The bot joins the user's voice channel
    #       1: The bot moves from another voice channel
    #   Failure:
    #       2: User is not in a voice channel
    #       3: Bot is already in the same voice channel
    #       4: Connection not attempted, unknown error
    join_status: int = 4

    # Embed color for join success/error message
    join_color: int = colores["error"]

    # Try to connect to the voice channel
    try:
        join_status = await user_server.join_vc(interaction.user)
        join_color = colores["play"]
    except AttributeError:  # User not in voice channel
        join_status = 2
    except ValueError:  # Bot already in the same voice channel
        join_status = 3
    
    # Send confirmation/error message
    # Message selection indexed with join_status
    msgs = [
        "🏃 Joined your voice channel!",
        "🏃 Moved to your voice channel!",
        "🤷 You're not in a voice channel!",
        "🤷 Jack is already in your voice channel!",
        "⚠️ Unknown error!"
    ]
    # Initialize embed
    embed_join = discord.Embed(
        title=msgs[join_status],
        color=join_color
    )
    # If successfully joined, display voice channel name
    if join_status in [0, 1]:
        embed_join.set_footer(text=f"🔊 {user_server.voice_client.channel.name}")
    # Send the message
    await interaction.edit_original_response(embed=embed_join)

# Slash commands end
    
# Text commands start

@bot.command()
async def sync(ctx):
    """
    Sync command tree with Discord, i.e. enable bot's slash commands.
    """
    if ctx.author.id == int(admin_id):  # Owner's ID
        # Sync global commands
        await bot.tree.sync()

        # Sync guild specific commands
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)

        await ctx.send("👍 Commands synced!")
    else:
        await ctx.send("🚫 This command can only be ran by the admin!")

# Text commands end

# Uncomment when running on replit (3/3)
# keep_alive()

@bot.event
async def on_command_error(ctx, error):
    """
    Do nothing when someone types a nonexistent text command containing the bot's command prefix.
    """
    if isinstance(error, discord.ext.commands.CommandNotFound):
        return
    raise error

# Launch bot
bot.run(TOKEN)