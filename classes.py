from typing import List
from enum import Enum
import asyncio
import random
import time

import discord
from discord.ext import commands, tasks
import yt_dlp

from config import colores, ydl_opts, ffmpeg_opts, vc_timeout
import util

class Track:
    """
    Represents a track from a YouTube video.

    Attributes
    -----------
    adder: :class:`discord.Member`
        The user who added the track.
    url: :class:`str`
        The URL of the track.
    title: :class:`str`
        The title of the track.
    duration: :class:`int`
        The duration of the track.
    uploader: :class:`str`
        Name of the uploader of the track.
    thumbnail: :class:`str`
        URL of the thumbnail of the track.
    """
    def __init__(self, adder: discord.Member, url: str):
        """
        Inits Track.

        Parameters
        -----------
        adder: :class:`discord.Member`
            The user who added the track.
        url: :class:`str`
            The URL of the track.

        Raises
        -------
        Exception
            Rethrows any exception during Track initialization.
        """
        # Get the adder
        self.adder: discord.Member = adder

        # Get track from URL
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                info = ydl.sanitize_info(info)  # Ensure info is a dict

                # Initialize attributes after track is found
                self.url: str = url
                self.title: str = info["title"]
                self.duration: int = info["duration"]
                self.uploader: str = info["uploader"]
                self.thumbnail: str = info["thumbnail"]
        except Exception as e:  # Rethrow class initialization exception
            raise

class LoopStatus(Enum):
    """
    Used to indicate the loop mode setting of a Server.
    """
    OFF = 0
    """
    Loop is off.
    """
    QUEUE = 1
    """
    Looping over the queue.
    """
    TRACK = 2
    """
    Looping over the current track.
    """

class Server:
    """
    Represents a profile for a discord server containing playback status and settings.

    Attributes
    -----------
    id: :class:`int`
        The ID of the server.
    voice_client: :class:`discord.VoiceClient`
        The bot's voice connection to the server.
    queue: :class:`List[Track]`
        Queue of tracks to be played in the server.
    current_track: :class:`Track`
        Current playing track in the server.
    start_time: :class:`int`
        Timestamp when the current track in the server started playing. If the track was paused and resumed, this attribute does not represent the actual start time of the track.
    pause_time: :class:`int`
        Timestamp when the current track in the server is last paused.
    idle_time: :class:`int`
        Time in seconds that the bot has been idling in the server for.
    loop_status: :class:`LoopStatus`
        Loop mode setting of the server.
    shuffle_status: :class:`bool`
        Shuffle play setting of the server.
    voteskip_list: :class:`List[int]`
        List of users in IDs who voted to skip the current track.
    """
    def __init__(self, id):
        """
        Inits Server.

        Parameters
        -----------
        id: :class:`int`
            The ID of the server.
        """
        # ID and voice channel
        self.id: int = id  # ID of the server
        self.voice_client: discord.VoiceClient = None  # Voice channel the bot is connected to
        # Queue
        self.queue: List[Track] = []
        self.current_track: Track = None  # Current track is outside the queue
        # Playback status
        self.start_time: int = 0  # Current track start time
        self.pause_time: int = 0  # Current track pause time
        self.idle_timer: tasks.Loop = None  # Idle timeout loop
        # Session settings
        self.loop_status: LoopStatus = LoopStatus.OFF  # Loop mode
        self.shuffle_status: bool = False  # Shuffle play
        self.voteskip_list: List[int] = []  # List of user IDs who voted to skip current track
    
    def reset(self):
        """
        Resets all attributes of a Server instance.
        """
        # Cancel the idle timer if any
        if self.idle_timer is not None:
            self.idle_timer.cancel()

        self.voice_client = None
        self.queue = []
        self.current_track = None
        self.start_time = 0
        self.pause_time = 0
        self.idle_timer = None
        self.loop_status = LoopStatus.OFF
        self.shuffle_status = False
        self.voteskip_list = []
    
    def check_same_vc(self, user: discord.Member) -> bool:
        """
        Check if user is in the same voice channel as the bot.

        Called when a playback control requires the user to be in the same voice channel, e.g. pause, skip.

        Parameters
        -----------
        user: :class:`discord.Member`
            The user using the playback control.
        
        Returns
        --------
        :class:`bool`
            True if the user is in the same voice channel,
            False if user is not in a voice channel, or is in a different voice channel.
        
        Raises
        -------
        AttributeError
            The bot is not in a voice channel.
        """
        # Check if bot is in a voice channel
        if self.voice_client is None:
            raise AttributeError("Bot is not in a voice channel.")

        # Check if bot and user are in the same voice channel
        if user.voice is None or user.voice.channel is not self.voice_client.channel:
            return False
        else:
            return True

    async def join_vc(self, user: discord.Member) -> int:
        """
        Join/move to user's voice channel.

        Parameters
        -----------
        user: :class:`discord.Member`
            The user requesting the bot to join their voice channel.
        
        Returns
        --------
        :class:`int`
            0 if the bot joins the user's voice channel,
            1 if the bot moves from another voice channel.
        
        Raises
        -------
        ValueError
            User is not in a voice channel.
        AttributeError
            The bot and the user are already in the same voice channel.
        """
        # Check if user and bot is in a VC
        if (user.voice is not None) and (self.voice_client is not None):
            # Bot is already in user's VC
            if user.voice.channel is self.voice_client.channel:
                raise AttributeError("Bot and user are already in the same voice channel.")
            # Bot is in another VC
            else:
                await self.voice_client.move_to(user.voice.channel)
                return 1
        # Bot is not in any VC
        elif user.voice is not None:
            self.voice_client = await user.voice.channel.connect(self_deaf=True)
            return 0
        # User is not in a VC
        else:
            raise ValueError("User is not in a voice channel.")

    async def leave(self) -> int:
        """
        Leave the user's voice channel and reset the server the user is in, including statuses and settings.
        
        Returns
        --------
        :class:`int`
            0 if the bot successfully leaves the user's channel.
        """
        await self.voice_client.disconnect()
        self.reset()
        return 0
    
    def add_track(self, track: Track) -> bool:
        """
        Add a track to the server's queue.

        Parameters
        -----------
        track: :class:`Track`
            The track to be added.
        
        Returns
        --------
        :class:`bool`
            True if the track is successfully added.
        """
        self.queue.append(track)
        return True

    def move_queue(self) -> None:
        """
        Move one track from the queue to the current track based on server's settings.

        Normal: Assign first track in queue to current_track, remove it from queue
        Loop track: Do not remove first track from queue
        Loop queue: Move first track to back of queue
        Shuffle: Assign random track to current_track

        Enabling both shuffle and loop track is equivalent to enabling shuffle and loop queue.
        """
        # Index of the track chosen
        # This is the first track if shuffle is off, random track if shuffle is on
        chosen_idx: int = 0
        if self.shuffle_status == True:
            chosen_idx = random.randrange(len(self.queue))
        
        # Assign the chosen track to current_track
        self.current_track = self.queue[chosen_idx]
        # Remove chosen track from queue if not looping track
        if self.loop_status != LoopStatus.TRACK:
            self.queue.pop(chosen_idx)
        # If looping queue and not shuffling, move chosen track (now current_track) to back of queue
        if (self.loop_status == LoopStatus.QUEUE) and (self.shuffle_status == False):
            self.queue.append(self.current_track)

    async def idle_timer_loop(self, text_channel: discord.TextChannel) -> None:
        """
        Disconnect the bot from the voice channel after idling for some time.

        Not meant to be called directly.

        Parameters
        -----------
        text_channel: :class:`discord.TextChannel`
            The text channel where the last track is requested.
        """
        # Idle for the specified interval
        await asyncio.sleep(vc_timeout)
        # Notify about disconnection
        await text_channel.send(embed=util.compose_idle_timeout(text_channel))
        # Disconnect
        await self.leave()
    
    def idle_timer_init(self, text_channel: discord.TextChannel) -> None:
        """
        Start an idle timer and stores it in the server profile.

        Called after the last track in queue has finished playing.

        Parameters
        -----------
        text_channel: :class:`discord.TextChannel`
            The text channel where the last track is requested.
        """

        idle_timer = tasks.loop(count=1)(self.idle_timer_loop)
        self.idle_timer = idle_timer
        self.idle_timer.start(text_channel)
    
    async def play_next(self, interaction: discord.Interaction, loop) -> None:
        """
        Plays the next song in queue. If queue is empty, start idle timer.

        Parameters
        -----------
        interaction: :class:`discord.Interaction`
            The interaction that starts the playback session, usually from a `/play` command.
        loop:
            The event loop to repeat this function in when a track ends. Usually the bot's event loop.
        """
        # Reset voteskip status
        self.voteskip_list = []
        # Clear current track
        self.current_track = None

        # Cancel the idle timer if any
        if (self.idle_timer is not None) and (len(self.queue) > 0):
            self.idle_timer.cancel()
            self.idle_timer = None

        # If queue is empty, start idle timer
        if len(self.queue) == 0:
            self.idle_timer_init(interaction.channel)
            # Send notification that queue is empty
            await interaction.channel.send(embed=util.compose_queue_end(self.voice_client.channel))
            return

        # Move queue
        self.move_queue()

        # Play next track
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(self.current_track.url, download=False)
            stream_url = data['url']

            self.voice_client.play(
                discord.FFmpegPCMAudio(
                    stream_url,
                    **ffmpeg_opts  # Pass before_options and options
                ),
                after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction, loop), loop)
            )

        # Record start time
        self.start_time = time.time()

        # Send confirmation message
        await interaction.channel.send(embed=self.play_msg(mode=0))
    
    def queue_add_msg(self, track: Track) -> discord.Embed:
        """
        Compose add track confirmation message.

        This function is defined in :class:`Server` because it uses its attributes.

        Parameters
        -----------
        track: :class:`Track`
            The track that is added.
        
        Returns
        --------
        :class:`discord.Embed`
            The embed containing the message to send.
        """
        # Format track info
        format_value = f"[{track.title}]({track.url})"  # Title and URL
        format_value += f"\n👤 `{track.uploader}` | ⏳ `{util.format_duration(track.duration)}`"  # Uploader and duration
        format_footer = f"🙋 Added by {track.adder.display_name}"  # Adder
        try:  # Current voice channel
            format_footer += f"\n🔊 {self.voice_client.channel.name}"
        except AttributeError:  # Race condition: user left voice channel before command is complete
            pass

        # Initialize embed
        embed_queue_add = discord.Embed(
            title="👍 Added to queue!",
            description=format_value,
            color=colores["play"]
        )
        embed_queue_add.set_footer(text=format_footer)

        # Add track thumbnail
        embed_queue_add.set_thumbnail(url=track.thumbnail)

        # Return the completed embed
        return embed_queue_add

    def play_msg(self, mode: int=0) -> discord.Embed:
        """
        Compose playback confirmation message.

        This function is defined in :class:`Server` because it uses its attributes.

        Parameters
        -----------
        mode: :class:`int`
            The type of playback to confirm.
                0: Start
        
        Returns
        --------
        :class:`discord.Embed`
            The embed containing the message to send.
        
        Raises
        -------
        ValueError
            The mode is invalid.
        """

        # Select playback type
        try:
            title = [
                "▶️ Started playing!"
            ][mode]
        except IndexError:
            raise ValueError("Invalid mode.")
        
        # Format track info
        # Title and URL
        format_desc = f"[{self.current_track.title}]({self.current_track.url})" 
        # Uploader and duration
        format_desc += f"\n👤 `{self.current_track.uploader}` | ⏳ `{util.format_duration(self.current_track.duration)}`"  
        # Adder and current voice channel
        format_footer = f"🙋 Added by {self.current_track.adder.display_name}\n🔊 {self.voice_client.channel.name}"

        # Initialize embed
        embed_play = discord.Embed(
            title=title,
            description=format_desc,
            color=colores["play"]
        )

        # Add playback settings
        # Detect playback settings
        embed_play_settings = ""
        if self.loop_status == LoopStatus.TRACK:
            embed_play_settings += "🔂 Loop track on"
        elif self.loop_status == LoopStatus.QUEUE:
            embed_play_settings += "🔁 Loop queue on"
        if self.shuffle_status == True:
            embed_play_settings += "\n🔀 Shuffle on"
        # Insert settings to embed
        if embed_play_settings != "":
            embed_play.add_field(
                name="🎛️ Settings",
                value=embed_play_settings,
                inline=False
            )

        # Add track thumbnail
        embed_play.set_thumbnail(url=self.current_track.thumbnail)

        # Add voice channel name
        embed_play.set_footer(text=format_footer)

        return embed_play