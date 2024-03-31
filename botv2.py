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
import util

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

    Refer to :func:`util.compose_join` for usage of status codes.
    """
    await interaction.response.defer(thinking=True)

    # Find profile of the user's server
    user_server: Server = servers[interaction.guild_id]

    join_status: int = 5  # Status code from voice channel connection attempt
    # Try connecting to the voice channel
    try:
        join_status = await user_server.join_vc(interaction.user)
    except ValueError:  # User not in voice channel
        join_status = 2
    except AttributeError:  # Bot already in the same voice channel
        join_status = 3
    except discord.ClientException:  # Bot has just been externally disconnected, must wait for reconnection timeout
        join_status = 4
    
    # Send confirmation/error message
    # Compose embed
    embed_join = util.compose_join(join_status, interaction.user)
    # Send the message
    await interaction.edit_original_response(embed=embed_join)

@bot.tree.command(description="Clear the queue and make Jack leave your voice channel!")
async def leave(interaction: discord.Interaction) -> None:
    """
    Leave user's voice channel if user and bot are in the same voice channel.

    Also resets the corresponding server's profile.
    """
    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]  # Find profile of the user's server

    # Status code from voice channel disconnection attempt
    leave_status: int = 3
    # Attempt to disconnect
    try:
        # User is not in the same voice channel
        if user_server.check_same_vc(interaction.user) == False:
            leave_status = 1
        else:
            leave_status = await user_server.leave()
    # Bot is not in a voice channel
    except AttributeError:
        leave_status = 2
    
    # Send confirmation/error message
    # Compose the embed
    embed_leave = util.compose_leave(leave_status, interaction.user)
    # Send the message
    await interaction.edit_original_response(embed=embed_leave)

@bot.tree.command(description="Play audio from YouTube. Playlists are not supported!")
async def play(interaction: discord.Interaction, url: str) -> None:
    """
    Add a track to the server's queue. Play it immediately if it is the first track in queue.

    Parameters
    -----------
    url: :class:`str`
        The URL of the track.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

    # Check if URL is valid
    if not util.is_supported(url):
        await interaction.edit_original_response(embed=util.compose_link_invalid())
        return
    
    # Attempt to load the track
    try:
        track: Track = Track(interaction.user, url)
    # Link blocked by YouTube
    except Exception as e:
        await interaction.edit_original_response(embed=util.compose_link_blocked())
        return
    
    # Check if user is in a voice channel
    if interaction.user.voice is None:  # User is not in a voice channel
        await interaction.edit_original_response(embed=util.compose_join(2, interaction.user))
        return
    # Check if bot is in a voice channel and if user is in the same voice channel
    try:  # Not in same voice channel
        if user_server.check_same_vc(interaction.user) == False:
            await interaction.edit_original_response(embed=util.compose_not_same_vc())
            return
    except AttributeError:  # Bot is not in a voice channel
        pass

    # Make sure bot is in the same voice channel
    try:
        await user_server.join_vc(interaction.user)
    except ValueError:  # User left before bot could join the voice channel
        await interaction.edit_original_response(embed=util.compose_join(2, interaction.user))
        return
    except AttributeError:  # Bot is already in the same voice channel
        pass
    except discord.ClientException:  # Bot has just been externally disconnected, must wait for reconnection timeout
        await interaction.edit_original_response(embed=util.compose_join(4, interaction.user))
        return
    
    # Add track into queue
    user_server.add_track(track)

    # Start the queue if bot is not already playing
    if not (user_server.voice_client.is_playing()) or (user_server.voice_client.is_paused()):
        await user_server.play_next(interaction, loop=bot.loop)
    
    # Send confirmation message
    await interaction.edit_original_response(embed=user_server.queue_add_msg(track))

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
async def on_voice_state_update(member, before, after):
    """
    Ensures the server profile is reset properly if the bot is disconnected externally.

    The bot is externally disconnected when a disconnection event occurs and the `Server.voice_client` instance is still present afterwards.
    """
    # Find profile of the user's server
    user_server: Server = servers[member.guild.id]

    # Check for remaining voice_client instances after disconnection
    if after.channel is None and member.id == bot.user.id:
        if user_server.voice_client is not None:
            user_server.reset()

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