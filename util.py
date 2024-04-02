# util.py
# Utility functions for commands and classes
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

from config import colores, ydl_opts

import time
import typing
import functools

async def run_blocking(bot: discord.Client, blocking_func: typing.Callable, *args, **kwargs) -> typing.Any:
    """
    Runs a blocking function without blocking the bot's heartbeat.
    https://stackoverflow.com/questions/65881761/discord-gateway-warning-shard-id-none-heartbeat-blocked-for-more-than-10-second
    """

    func = functools.partial(blocking_func, *args, **kwargs) # `run_in_executor` doesn't support kwargs, `functools.partial` does
    return await bot.loop.run_in_executor(None, func)

def format_duration(seconds: int) -> str:
    """
    Formats a time duration in seconds into hh:mm:ss format.

    Parameters
    -----------
    seconds: :class:`int`
        The time duration to be converted.
    
    Returns
    --------
    :class:`str`
        The formatted time.
    """

    if seconds < 60:
        time_string = time.strftime('0:%S', time.gmtime(seconds))
    elif seconds < 3600:
        time_string = time.strftime('%M:%S', time.gmtime(seconds)).lstrip('0')
    else:
        time_string = time.strftime('%H:%M:%S', time.gmtime(seconds)).lstrip('0')
    return time_string

def is_supported(url: str) -> int:
    """
    Checks if a URL is a valid YouTube link.

    Parameters
    -----------
    url: :class:`str`
        The URL to be checked.
    
    Returns
    --------
    :class:`int`
        Valid:
            1: The URL is a video link.
            2: The URL is a playlist link.
        Invalid:
            -1: The URL is not a valid YouTube link.
    """

    # Do not accept playlist links
    if "/playlist" in url:
        return 2

    extractors = yt_dlp.extractor.gen_extractors()
    for e in extractors:
        if e.suitable(url) and e.IE_NAME != 'generic':
            return 1
    return -1

def yt_search(query: str) -> str:
    """
    Search for a track on YouTube.

    Parameters
    -----------
    query: :class:`str`
        The search term/keyword.
    
    Returns
    --------
    :class:`str`
        The URL of the search result, or an empty string if search returns no results.
    """
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch: {query}", download=False)['entries'][0]['webpage_url']
    except:  # No results
        return ""

def compose_join(join_status: int, user: discord.Member) -> discord.Embed:
    """
    Compose a confirmation/error message for the bot joining a voice channel.

    Parameters
    -----------
    join_status: :class:`int`
        The status code returned by the voice channel connection attempt.
            Success:
                0: The bot joins the user's voice channel.
                1: The bot moves from another voice channel.
            Failure:
                2: User is not in a voice channel.
                3: Bot is already in the same voice channel.
                4: Bot has just been externally disconnected, must wait for reconnection timeout.
                5: Connection not attempted, unknown error.
    user: :class:`discord.Member`
        The user requesting the bot to join their voice channel.
    
    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    
    Raises
    -------
    ValueError
        Invalid status code.
    """
    # Select message from join_status
    try:
        msg = [
            "🙋 Joined your voice channel!",
            "🏃‍♂️ Moved to your voice channel!",
            "🤷 You're not in a voice channel!",
            "🤷 Already in your voice channel!",
            "⏳ Wait before reconnecting!",
            "⚠️ Unknown error!"
        ][join_status]
    except IndexError:
        raise ValueError("Invalid status code.")
    
    # Select embed color
    color_join = colores["play"] if join_status <= 1 else colores["error"]
    
    # Initialize embed
    embed_join = discord.Embed(
        title=msg,
        color=color_join
    )

    # Configure embed
    try:
        if join_status in [0, 1]:  # Success
            embed_join.set_footer(text=f"🔊 {user.voice.channel.name}")
    except AttributeError:  # Race condition: user left voice channel before command is complete
        pass

    # Return the completed embed
    return embed_join

def compose_not_same_vc():
    """
    Compose error message that the user is not in the same voice channel as the bot.

    Called by commands that require the user to be in the same voice channel.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_not_same_vc = discord.Embed(
        title="🚫 You must be in the same voice channel as Jack to perform this action!",
        color=colores["error"]
    )
    return embed_not_same_vc

def compose_bot_not_in_vc() -> discord.Embed:
    """
    Compose error message that the bot is not in a voice channel.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_bot_not_in_vc = discord.Embed(
        title="🤷 Jack is not in a voice channel!",
        color=colores["error"]
    )
    return embed_bot_not_in_vc

def compose_leave(leave_status: int, user: discord.Member) -> discord.Embed:
    """
    Compose a confirmation/error message for the bot leaving a voice channel.

    Parameters
    -----------
    leave_status: :class:`int`
        The status code returned by the voice channel disconnection attempt.
            Success:
                0: The bot is disconnected from the user's voice channel.
            Failure:
                1: User is not in the same voice channel.
                2: Bot is not in a voice channel.
                3: Disconnection not attempted, unknown error.
    user: :class:`discord.Member`
        The user requesting the bot to leave their voice channel.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    
    Raises
    -------
    ValueError
        Invalid status code.
    """
    # Select message from leave_status
    try:
        msg = [
            "🙋 Left your voice channel!",
            "🚫 You must be in the same voice channel as Jack to perform this action!",
            "🤷 Jack is not in a voice channel!",
            "⚠️ Unknown error!"
        ][leave_status]
    except IndexError:
        raise ValueError("Invalid status code.")
    
    # Select embed color
    color_leave = colores["play"] if leave_status == 0 else colores["error"]

    # Initialize embed
    embed_leave = discord.Embed(
        title=msg,
        color=color_leave
    )

    # Configure embed
    try:
        if leave_status == 0:  # Success
            embed_leave.set_footer(text=f"🔊 {user.voice.channel.name}")
    except AttributeError:  # Race condition: user left voice channel before command is complete
        pass

    # Return the completed embed
    return embed_leave

def compose_idle_timeout(voice_channel: discord.VoiceChannel) -> discord.Embed:
    """
    Compose a message for the bot leaving a voice channel due to inactivity.

    Parameters
    -----------
    voice_channel: :class:`discord.VoiceChannel`
        The voice channel that the bot was in.
    
    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    # Initialize embed
    embed_idle = discord.Embed(
        title="🛌 Left voice channel due to inactivity!",
        color=colores["play"]
    )
    try:
        embed_idle.set_footer(text=f"🔊 {voice_channel.name}")
    except AttributeError:
        pass

    # Return the completed embed
    return embed_idle

def compose_queue_end(voice_channel: discord.VoiceChannel) -> discord.Embed:
    """
    Compose a message to notify that all tracks in the queue have finished playing.

    Parameters
    -----------
    voice_channel: :class:`discord.VoiceChannel`
        The voice channel that the bot is in.
    
    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    # Initialize embed
    embed_queue_end = discord.Embed(
        title="🏁 No more tracks in queue!",
        color=colores["play"]
    )
    try:
        embed_queue_end.set_footer(text=f"🔊 {voice_channel.name}")
    except AttributeError:
        pass

    # Return the completed embed
    return embed_queue_end

def compose_link_invalid() -> discord.Embed:
    """
    Compose a message that the given link is not a valid YouTube video link.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_link_invalid = discord.Embed(
        title="⚠️ Invalid YouTube link!",
        description="Please double check your link.\n• Is it a playlist link? Use `/playlist` instead.\n• Is it a link to another website?",
        color=colores["error"]
    )
    return embed_link_invalid

def compose_link_blocked() -> discord.Embed:
    """
    Compose a message that the given link is blocked by YouTube.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_link_blocked = discord.Embed(
        title="⚠️ Error loading from link!",
        description="Please double check your link.\n• Is it a link to another website?\n• Is the video age-restricted?\n• Is the video copyright claimed?",
        color=colores["error"]
    )
    return embed_link_blocked

def compose_queue_invalid_page_no(no_of_pages: int) -> discord.Embed:
    """
    Compose a message that the given page number is invalid.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_invalid_page = discord.Embed(
        title="⚠️ Check your page number!",
        description=f"There are {no_of_pages} page(s) in the queue.",
        color=colores["error"]
    )
    return embed_invalid_page

def compose_queue_empty() -> discord.Embed:
    """
    Compose a message that the queue is empty.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_queue_empty = discord.Embed(
        title="🤷 Queue is empty!",
        color=colores["status"]
    )
    return embed_queue_empty

def compose_search_no_results() -> discord.Embed:
    """
    Compose a message that the search returned no results.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_search_no_results = discord.Embed(
        title="🤷 Couldn't find anything with the URL/keyword!",
        color=colores["error"]
    )
    return embed_search_no_results

def compose_playlist_link_invalid() -> discord.Embed:
    """
    Compose a message that the playlist link is invalid.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_playlist_link_invalid = discord.Embed(
        title="⚠️ Invalid YouTube playlist link!",
        description="Please double check your link.\n• Is it a video link/search query? Use `/play` instead.\n• Is it a link to another website?",
        color=colores["error"]
    )
    return embed_playlist_link_invalid

def compose_playlist_downloading() -> discord.Embed:
    """
    Compose a message that the bot is downloading the given playlist.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_playlist_downloading = discord.Embed(
        title="⏳ Downloading playlist...",
        color=colores["status"]
    )
    return embed_playlist_downloading

def compose_playlist_download_failed() -> discord.Embed:
    """
    Compose a message that the playlist download failed.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_playlist_download_failed = discord.Embed(
        title="⚠️ Failed to download playlist!",
        color=colores["error"]
    )
    return embed_playlist_download_failed

def compose_playlist_adding() -> discord.Embed:
    """
    Compose a message that the bot is adding the playlist to the queue.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_playlist_adding = discord.Embed(
        title="⏳ Adding playlist to queue...",
        color=colores["status"]
    )
    return embed_playlist_adding

def compose_move_invalid_index() -> discord.Embed:
    """
    Compose a message that the given track or position index, or both, are out of range.

    Returns
    --------
    :class:`discord.Embed`
        The embed containing the message to send.
    """

    embed_move_invalid_index: discord.Embed = discord.Embed(
        title="⚠️ Invalid track/position number!",
        color=colores["error"]
    )
    return embed_move_invalid_index