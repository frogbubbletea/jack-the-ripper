# botv2.py
# Jack the Ripper v2.0
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

import os
import time
import random
import asyncio
import math
import typing
from typing import List

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

@bot.tree.command(description="Play audio from YouTube from URL or search keyword!")
@app_commands.rename(url="query")
async def play(interaction: discord.Interaction, url: str) -> None:
    """
    Add a track to the server's queue. Play it immediately if it is the first track in queue.

    Parameters
    -----------
    url: :class:`str`
        The URL of the track, or the keyword to search for.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

    # Check if URL is valid, playlists aren't valid in this command
    if (util.is_supported(url) < 0) or (util.is_supported(url) == 2):
        # Perform search for keywords
        url = await util.run_blocking(bot, util.yt_search, url)
        # Return if no results
        if url == "":
            await interaction.edit_original_response(embed=util.compose_search_no_results())
            return
    
    # Attempt to load the track
    try:
        track: Track = await util.run_blocking(bot, Track, interaction.user, url)
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

@bot.tree.command(description="Play a YouTube playlist!")
async def playlist(interaction: discord.Interaction, url: str) -> None:
    """
    Add a playlist to the server's queue.

    Parameters
    -----------
    url: :class:`str`
        The URL of the playlist.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

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

    # Check if URL is valid
    if util.is_supported(url) != 2:
        await interaction.edit_original_response(embed=util.compose_playlist_link_invalid())
        return
    
    # Load the playlist from YouTube
    # Show loading message
    await interaction.edit_original_response(embed=util.compose_playlist_downloading())
    # Download the playlist
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Don't block the bot
            playlist_dict = await util.run_blocking(bot, ydl.extract_info, url, download=False)
            # playlist_dict = ydl.extract_info(url, download=False)
            playlist_dict = ydl.sanitize_info(playlist_dict)
            # Get info about the playlist
            playlist_title: str = playlist_dict["title"]  # Title
            playlist_uploader: str = playlist_dict["uploader"]  # Uploader
            playlist_len: int = playlist_dict["playlist_count"]  # No. of tracks
            playlist_entries: List[str] = playlist_dict["entries"]  # List of tracks
        except:
            await interaction.edit_original_response(embed=util.compose_playlist_download_failed())
            return
    
    # Update progress to the user
    await interaction.edit_original_response(embed=util.compose_playlist_adding())

    # Record no. of tracks that cannot be loaded
    num_failed_tracks: int = 0

    # Attempt to load the tracks
    for entry in playlist_entries: 
        try:   
            new_track: Track = Track(interaction.user, entry["webpage_url"], entry)
            # Add track into queue
            user_server.add_track(new_track)
        except Exception as e:
            num_failed_tracks += 1
    
    # Start the queue if bot is not already playing
    if not (user_server.voice_client.is_playing()) or (user_server.voice_client.is_paused()):
        await user_server.play_next(interaction, loop=bot.loop)
    
    # Send confirmation message
    await interaction.edit_original_response(embed=user_server.compose_playlist_added(url=url, title=playlist_title, uploader=playlist_uploader, len=playlist_len, len_failed=num_failed_tracks))

class QueuePage(discord.ui.View):
    """
    A view containing buttons for the user to flip through pages of a paginated content.

    Called by the /queue command.

    Attributes
    -----------
    server: :class:`Server`
        The server containing the paginated content.
    """

    def __init__(self, *, timeout: int=180, page: int=0, server: Server):
        """
        Inits the view.

        Parameters
        -----------
        timeout: :class:`int`
            The duration the user can use the buttons for. After that, the buttons will be disabled.
        page: :class:`int`
            The current displaying page.
        server: :class:`Server`
            The server containing the paginated content.
        """

        super().__init__(timeout=timeout)
        self.page: int = page
        self.server: Server = server  # Server containing the paginated content

    @discord.ui.button(label="Previous page", style=discord.ButtonStyle.gray, emoji="⬅️")
    async def previous_button(self,interaction:discord.Interaction, button:discord.ui.Button) -> None:
        """
        Button to go to the previous page of the paginated content.
        """
        # Get the embed of the previous page
        try:
            embed_queue_page: discord.Embed = self.server.compose_queue_page(self.page - 1)
        except ValueError:
            await interaction.response.send_message("⚠️ You're already at the first page!", ephemeral=True)
            return
        
        # Go to the page
        self.page -= 1
        await interaction.response.edit_message(embed=embed_queue_page, view=self)
    
    @discord.ui.button(label="Next page", style=discord.ButtonStyle.gray, emoji="➡️")
    async def next_button(self,interaction:discord.Interaction, button:discord.ui.Button):
        """
        Button to go to the next page of the paginated content.
        """
        # Get the embed of the next page
        try:
            embed_queue_page: discord.Embed = self.server.compose_queue_page(self.page + 1)
        except ValueError:
            await interaction.response.send_message("⚠️ You're already at the last page!", ephemeral=True)
            return

        # Go to the page
        self.page += 1
        await interaction.response.edit_message(embed=embed_queue_page, view=self)

@bot.tree.command(description="Get the queue!")
async def queue(interaction: discord.Interaction, page: typing.Optional[int]) -> None:
    """
    Get the queue of the user's server.

    Parameters
    -----------
    page: :class:`Optional[int]`
        The page number of the page to get, defaults to first page.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

    # Set default page number
    if page is None:
        page = 1
    
    # Convert page number to 0-based
    page -= 1

    # Check page number and get the embed
    try:
        embed_queue_page: discord.Embed = user_server.compose_queue_page(page)
    except ValueError:  # Invalid page number
        no_of_pages: int = user_server.get_last_queue_page_idx() + 1
        await interaction.edit_original_response(embed=util.compose_queue_invalid_page_no(no_of_pages))
        return
    except AttributeError:  # No track is playing
        await interaction.edit_original_response(embed=util.compose_queue_empty())
        return
    
    # Send the embed
    await interaction.edit_original_response(
        embed=embed_queue_page,
        view=QueuePage(page=page, server=user_server)
    )

@bot.tree.command(description="Skip to next track in queue!")
async def skip(interaction: discord.Interaction) -> None:
    """
    Stop the current track and play the next.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

    # Check if user is in the same voice channel
    try:
        if user_server.check_same_vc(interaction.user) == False:
            await interaction.edit_original_response(embed=util.compose_not_same_vc())
            return
    except AttributeError:  # Bot is not in a voice channel
        await interaction.edit_original_response(embed=util.compose_bot_not_in_vc())
        return
    
    # Vote to skip
    await user_server.vote_skip(interaction)

@bot.tree.command(description="Show now playing track!")
async def np(interaction: discord.Interaction) -> None:
    """
    Show the current track.
    """

    await interaction.response.defer(thinking=True)
    user_server: Server = servers[interaction.guild_id]

    # Get the embed and send it
    await interaction.edit_original_response(embed=user_server.compose_np())

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