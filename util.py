# util.py
# Utility functions for commands and classes
import discord
from discord import app_commands
from discord.ext import commands

from config import colores, ydl_opts

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