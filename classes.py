from typing import List
from enum import Enum
import asyncio
import random
import time
import functools
import math

import discord
from discord.ext import commands, tasks
import yt_dlp

from config import colores, ydl_opts, ffmpeg_opts, vc_timeout, queue_page_size
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
    def __init__(self, adder: discord.Member, url: str, track_dict: dict=None):
        """
        Inits Track.

        Parameters
        -----------
        adder: :class:`discord.Member`
            The user who added the track.
        url: :class:`str`
            The URL of the track.
        track_dict: :class:`dict`
            The dictionary containing the track's info. This will be used to initialize Track if available.

        Raises
        -------
        Exception
            Rethrows any exception during Track initialization.
        """
        # Get the adder
        self.adder: discord.Member = adder

        # Get track from URL or track_dict
        info = {}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if track_dict is not None:
                    info = ydl.sanitize_info(track_dict)
                else:
                    info = ydl.extract_info(url, download=False)
                    info = ydl.sanitize_info(info)  # Ensure info is a dict
        except Exception as e:
            raise

        try:
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
    def __init__(self, id: int):
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
        self.voteskip_list: List[discord.Member] = []  # List of user IDs who voted to skip current track
    
    def reset(self) -> None:
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
    
    def set_loop_status(self, new_value: LoopStatus) -> bool:
        """
        Set the loop mode playback setting for the server.

        Parameters
        -----------
        new_value: :class:`LoopStatus`
            The desired loop mode to set to.
        
        Returns
        --------
        :class:`bool`
            True if the setting is successful, False otherwise.
        
        Raises
        -------
        Exception
            Any exception raised during the setting.
        """
        try:
            self.loop_status = new_value

            # If loop queue is enabled after the current track started playing, add it back to the queue manually
            if (self.loop_status == LoopStatus.QUEUE) and (self.current_track not in self.queue):
                self.queue.append(self.current_track)

            return True
        except Exception as e:
            raise
    
    def compose_set_loop(self, interaction: discord.Interaction) -> discord.Embed:
        """
        Compose a message confirming the loop mode playback setting of the server has been set.

        Parameters
        -----------
        interaction: :class:`discord.Interaction`
            The interaction containing the user who performed the setting and the text channel where the setting took place.
        
        Returns
        --------
        :class:`discord.Embed`
            The embed containing the message to send.
        """

        # Set embed title based on loop mode setting
        title: str = [
            "▶️ Loop disabled!",
            "🔁 Loop queue enabled!",
            "🔂 Loop track enabled!"
        ][self.loop_status.value]

        # Initialize embed
        embed_loop: discord.Embed = discord.Embed(
            title=title,
            color=colores["play"]
        )

        # Display current playback settings
        embed_loop.add_field(
            name="⚙️ Current settings",
            value=self.playback_settings_to_str(),
            inline=False
        )

        # Set footer
        format_footer: str = f"🙋 Set by {interaction.user.display_name}\n"
        format_footer += f"🔊 {self.voice_client.channel.name}"
        embed_loop.set_footer(text=format_footer)

        # Return completed embed
        return embed_loop
    
    def set_shuffle_status(self, new_value: bool) -> bool:
        """
        Set the shuffle playback setting for the server.

        Parameters
        -----------
        new_value: :class:`bool`
            The desired shuffle setting to set to.
        
        Returns
        --------
        :class:`bool`
            True if the setting is successful, False otherwise.
        
        Raises
        -------
        Exception
            Any exception raised during the setting.
        """

        try:
            self.shuffle_status = new_value
            return True
        except Exception as e:
            raise

    def compose_set_shuffle(self, interaction: discord.Interaction) -> discord.Embed:
        """
        Compose a message confirming the shuffle playback setting of the server has been set.

        Parameters
        -----------
        interaction: :class:`discord.Interaction`
            The interaction containing the user who performed the setting and the text channel where the setting took place.
        
        Returns
        --------
        :class:`discord.Embed`
            The embed containing the message to send.
        """
        # Set embed title based on shuffle setting
        title: str = {
            False: "▶️ Shuffle play disabled!",
            True: "🔀 Shuffle play enabled!"
        }[self.shuffle_status]

        # Initialize embed
        embed_shuffle: discord.Embed = discord.Embed(
            title=title,
            color=colores["play"]
        )

        # Display current playback settings
        embed_shuffle.add_field(
            name="⚙️ Current settings",
            value=self.playback_settings_to_str(),
            inline=False
        )

        # Set footer
        format_footer: str = f"🙋 Set by {interaction.user.display_name}\n"
        format_footer += f"🔊 {self.voice_client.channel.name}"
        embed_shuffle.set_footer(text=format_footer)

        # Return completed embed
        return embed_shuffle

    def playback_settings_to_str(self) -> str:
        """
        Convert playback settings to a string for visualization.

        This includes loop and shuffle modes.

        Called by playback and status embeds, e.g. when a track starts playing and /queue.

        Returns
        --------
        :class:`str`
            The playback settings string.
        """

        settings_str = ""

        if self.loop_status == LoopStatus.TRACK:
            settings_str += "🔂 Loop track on\n"
        elif self.loop_status == LoopStatus.QUEUE:
            settings_str += "🔁 Loop queue on\n"
        if self.shuffle_status == True:
            settings_str += "🔀 Shuffle play on"
        
        return settings_str.rstrip("\n")

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
        
        # If loop track is on, keep playing current track
        if self.loop_status == LoopStatus.TRACK:
            return
        # Assign the chosen track to current_track
        self.current_track = self.queue[chosen_idx]
        # Remove chosen track from queue
        self.queue.pop(chosen_idx)
        # If looping queue, move chosen track (now current_track) to back of queue
        if (self.loop_status == LoopStatus.QUEUE):
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
        # Do nothing if bot is already disconnected
        if self.voice_client == None:
            return
        # Notify about disconnection
        await text_channel.send(embed=util.compose_idle_timeout(self.voice_client.channel))
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
        # Clear current track if not looping track
        if self.loop_status != LoopStatus.TRACK:
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
            # Extract stream URL without blocking the bot
            extract_func = functools.partial(ydl.extract_info, self.current_track.url, download=False)
            data = await loop.run_in_executor(None, extract_func)
            # data = ydl.extract_info(self.current_track.url, download=False)
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
        format_value = f"\n👤 {track.uploader} | ⏳ `{util.format_duration(track.duration)}`"  # Uploader and duration
        format_footer = f"🙋 Added by {track.adder.display_name}"  # Adder
        try:  # Current voice channel
            format_footer += f"\n🔊 {self.voice_client.channel.name}"
        except AttributeError:  # Race condition: user left voice channel before command is complete
            pass

        # Initialize embed
        embed_queue_add = discord.Embed(
            title=track.title,
            url=track.url,
            description=format_value,
            color=colores["play"]
        )
        embed_queue_add.set_author(name="👍 Added to queue!")
        embed_queue_add.set_footer(text=format_footer)

        # Add track thumbnail
        embed_queue_add.set_thumbnail(url=track.thumbnail)

        # Return the completed embed
        return embed_queue_add

    def play_msg(self, mode: int=0, track: Track=None) -> discord.Embed:
        """
        Compose playback confirmation message.

        This function is defined in :class:`Server` because it uses its attributes.

        Parameters
        -----------
        mode: :class:`int`
            The type of playback to confirm.
                0: Start
                1: Vote skip
                2: Skip
                3: Pause
                4: Resume
        track: :class:`Track`
            The track to compose the message with. Defaults to the current track.
        
        Returns
        --------
        :class:`discord.Embed`
            The embed containing the message to send.
        
        Raises
        -------
        ValueError
            The mode is invalid.
        """

        # Get current track if no track is given
        if track is None:
            track = self.current_track

        # Select playback type
        try:
            title = [
                "▶️ Started playing!",
                "🗳️ Voted to skip!",
                "⏩ Skipped!",
                "⏸️ Paused!",
                "▶️ Resumed!"
            ][mode]
        except IndexError:
            raise ValueError("Invalid mode.")
        
        # Format track info
        # Uploader and duration
        format_desc = f"\n👤 {track.uploader} | ⏳ `{util.format_duration(track.duration)}`"  
        # Adder and current voice channel
        format_footer = f"🙋 Added by {track.adder.display_name}\n🔊 {self.voice_client.channel.name}"

        # Initialize embed
        embed_play = discord.Embed(
            title=track.title,
            url=track.url,
            description=format_desc,
            color=colores["play"]
        )

        # Add title
        embed_play.set_author(name=title)

        # [1] Add vote counts
        num_skip = math.ceil((len(self.voice_client.channel.members) - 1) / 2)  # Calculate number of votes required to skip
        if mode == 1:
            embed_play.add_field(
                name="🗳️ Votes",
                value=f"{len(self.voteskip_list)} / {num_skip} required",
                inline=False
            )

        # Configure footer
        # Adder
        format_footer = f"🙋 Added by {track.adder.display_name}\n"
        # Playback settings
        if (self.shuffle_status == True) or (self.loop_status != LoopStatus.OFF):
            format_footer += f"{self.playback_settings_to_str()}\n"
        # Current voice channel
        format_footer += f"🔊 {self.voice_client.channel.name}"
        # Add footer to embed
        embed_play.set_footer(text=format_footer)

        # Add track thumbnail
        embed_play.set_thumbnail(url=track.thumbnail)

        # Add voice channel name
        embed_play.set_footer(text=format_footer)

        return embed_play
    
    def get_last_queue_page_idx(self) -> int:
        """
        Get the index of the last page of the queue. This does not include the current track.

        Page size is defined in `config.queue_page_size`.

        Returns
        --------
        :class:`int`
            The index of the last page.
        """

        idx = int(len(self.queue) / queue_page_size)
        # If queue length is non-zero multiple of the page size, adjust number of pages accordingly
        if (len(self.queue) != 0) and (len(self.queue) % queue_page_size == 0):
            idx -= 1
        return idx
    
    def get_one_queue_page(self, page: int) -> List[Track]:
        """
        Get one page of the queue.

        Page size is defined in `config.queue_page_size`.

        Parameters
        -----------
        page: :class:`int`
            The zero-based index of the page number.
        
        Returns
        --------
        :class:`List[Track]`
            The page of the queue.
        
        Raises
        -------
        ValueError
            Invalid page number, i.e. `page` is negative or above the index of the last page.
        """

        # Check if page number is invalid
        if (page < 0) or (page > self.get_last_queue_page_idx()):
            raise ValueError("Invalid page number.")
        
        # Get the page
        try:
            queue_page = self.queue[queue_page_size * page: queue_page_size * page + queue_page_size]
        except:  # Length of the last page may be smaller than page size
            queue_page = self.queue[queue_page_size * page: ]
        
        return queue_page
    
    async def vote_skip(self, interaction: discord.Interaction) -> bool:
        """
        Record a user's vote to skip the current track. If more than half of the users in the voice channel has voted, skip the track.

        Parameters
        -----------
        user: :class:`discord.Member`
            The interaction containing the user who voted to skip.
        
        Returns
        --------
        :class:`bool`
            True if there are enough votes to skip the track, False otherwise.
        
        Raises
        -------
        ValueError
            The user has already voted to skip.
        """

        # Check if user has already voted
        if interaction.user in self.voteskip_list:
            raise ValueError("User has already voted to skip.")
        
        # Add the vote
        self.voteskip_list.append(interaction.user)

        # Remove users who left the voice channel after voting
        self.voteskip_list = [u for u in self.voteskip_list if u in self.voice_client.channel.members]

        # Send vote confirm message
        await interaction.edit_original_response(embed=self.play_msg(1))

        # If there are enough votes, skip the track
        if len(self.voteskip_list) >= math.ceil((len(self.voice_client.channel.members) - 1) / 2):
            # Send skip message
            await interaction.channel.send(embed=self.play_msg(2))
            # Skip the track
            self.voice_client.stop()
            return True
        else:
            return False

    def compose_queue_page(self, page: int) -> discord.Embed:
        """
        Compose an embed from one page of the queue. Current track is added before the first page.

        Defined as a method of :class:`Server` because it uses its attributes.

        Parameters
        -----------
        page: :class:`int`
            The zero-based index of the page number. If this is 0, current track will be added to the embed.
        
        Returns
        --------
        class:`discord.Embed`
            The composed embed containing the page.
        
        Raises
        -------
        ValueError
            Invalid page number.
        AttributeError
            The queue is empty and no track is playing.
        """

        # Get the page
        try:
            queue_page = self.get_one_queue_page(page)
        except ValueError:
            raise ValueError("Invalid page number.")
        
        # Check if queue is empty
        if (len(self.queue) < 1) and (self.current_track is None):
            raise AttributeError("Queue is empty and no track is playing.")

        # Check if current track is playing or paused
        format_title = "▶️ Now playing"
        if self.voice_client.is_paused():
            format_title = "⏸️ Now paused"

        # Prepare embed
        embed_queue = discord.Embed(
            title="📃 Queue",
            description=self.playback_settings_to_str(),
            color=colores["status"]
        )

        # Add current track before first page
        if (page == 0) and (self.current_track is not None):
            track_info: str = f"[{self.current_track.title}]({self.current_track.url})\n{self.current_track.uploader} | ⏳ `{util.format_duration(self.current_track.duration)}`"
            embed_queue.add_field(
                name=format_title,
                value=track_info,
                inline=False
            )

        # Add the page
        for i in range(len(queue_page)):
            # Get track number
            track_no: int = queue_page_size * page + i + 1
            # Get track field name
            track_name: str = f"💿 {track_no}"
            # Get track info
            track_info: str = f"[{queue_page[i].title}]({queue_page[i].url})\n{queue_page[i].uploader} | ⏳ `{util.format_duration(queue_page[i].duration)}`"
            # Add track to embed
            embed_queue.add_field(
                name=track_name,
                value=track_info,
                inline=False
            )

        # Format the embed
        # Total number of pages
        footer = f"📄 Page {page + 1} of {self.get_last_queue_page_idx() + 1}\n"
        # Current tracks and total number of tracks
        page_start_idx: int = 0 if page == 0 else queue_page_size * page + 1
        footer += f"💿 Track {page_start_idx}-{queue_page_size * page + len(queue_page)} of {len(self.queue)}\n"
        # Total play time of the queue, including current track
        footer += f"⏳ {util.format_duration(sum(t.duration for t in self.queue + [self.current_track]))}\n"
        # Name of current voice channel
        footer += f"🔊 {self.voice_client.channel.name}"
        # Add it to the embed
        embed_queue.set_footer(text=footer)

        return embed_queue
    
    def compose_playlist_added(self, url: str, title: str, uploader: str, len: int, len_failed: int) -> discord.Embed:
        """
        Compose add playlist confirmation message.

        Defined as a method of :class:`Server` because it uses its attributes.

        Parameters
        -----------
        url: :class:`str`
            The URL of the playlist.
        title: :class:`str`
            The title of the playlist.
        uploader: :class:`str`
            The uploader of the playlist.
        len: :class:`int`
            The number of tracks in the playlist.
        len_failed: :class:`int`
            The number of tracks in the playlist that failed to load.

        Returns
        --------
        class:`discord.Embed`
            The composed embed containing the message.
        """

        # Format playlist info
        format_info = f"[{title}]({url})\n"  # Title and URL
        format_info += f"👤 {uploader} | 💿 {len} tracks\n"  # Uploader and number of tracks
        if len_failed > 0:  # Add missing tracks warning
            format_info += f"ℹ️ Only {len - len_failed}/{len} tracks loaded"

        # Initialize embed
        embed_playlist_added = discord.Embed(
            title="👍 Playlist added to queue!",
            description=format_info,
            color=colores["play"]
        )

        # Add footer
        embed_playlist_added.set_footer(text=f"🔊 {self.voice_client.channel.name}")

        # Return the completed embed
        return embed_playlist_added
    
    def compose_np(self) -> discord.Embed:
        """
        Compose embed about the current track.

        Defined as a method of :class:`Server` because it uses its attributes.

        Returns
        --------
        class:`discord.Embed`
            The composed embed containing the current track, or a message that no track is playing.
        """

        # Check if the bot is playing anything
        if self.current_track is None:
            return discord.Embed(
                title="🤷 Nothing is playing!",
                color=colores["status"]
            )
        
        # Format track info
        format_desc: str = f"👤 {self.current_track.uploader} | ⏳ `{util.format_duration(self.current_track.duration)}`\n"  # Uploader and duration

        # Get current track elapsed time
        time_elapsed: int = 0
        progress_bar_icon: str = "▶️"
        if self.voice_client.is_paused():
            progress_bar_icon = "⏸️"
            time_elapsed = int(self.pause_time - self.start_time)
        else:
            time_elapsed = int(time.time() - self.start_time)

        # Draw progress bar
        progress_bar: List[str] = []
        bar_length: int = 15
        for i in range(bar_length):
            progress_bar.append("▬")
        # Get position of cursor on progress bar
        bar_deg = int((time_elapsed / self.current_track.duration) * bar_length)
        if bar_deg > bar_length:
            bar_deg = bar_length - 1
        # Put the cursor on the progress bar
        progress_bar[bar_deg] = "🔘"
        progress_bar_str: str = "".join(progress_bar)

        # Format progress bar with elapsed time
        format_elapsed = util.format_duration(time_elapsed)
        format_duration = util.format_duration(self.current_track.duration)
        format_desc += f"{progress_bar_icon} `{format_elapsed}` {progress_bar_str} `{format_duration}` 🔊"

        # Format footer
        # Adder
        format_footer = f"🙋 Added by {self.current_track.adder.display_name}\n"
        # Playback settings
        if (self.shuffle_status == True) or (self.loop_status != LoopStatus.OFF):
            format_footer += f"{self.playback_settings_to_str()}\n"
        # Current voice channel
        format_footer += f"🔊 {self.voice_client.channel.name}"

        # Initialize embed
        embed_np = discord.Embed(
            title=self.current_track.title,
            url=self.current_track.url,
            description=format_desc,
            color=colores["status"]
        )

        # Add header
        embed_np.set_author(name="▶️ Now playing")

        # Add track thumbnail
        embed_np.set_thumbnail(url=self.current_track.thumbnail)

        # Add footer
        embed_np.set_footer(text=format_footer)

        # Return the composed embed
        return embed_np
    
    def pause_resume(self) -> bool:
        """
        Pause/resume the bot's playback.

        Returns
        --------
        :class:`bool`
            True if the playback is paused, False if the playback is resumed.
        
        Raises
        -------
        AttributeError
            Bot is not in a voice channel, or is not playing anything.
        """

        # If bot is not in a voice channel, or is not playing anything
        if (self.voice_client is None) or ((self.voice_client.is_playing() == False) and (self.voice_client.is_paused() == False)):
            raise AttributeError("Bot is not playing or paused.")
        
        # Pause/resume the bot.
        if self.voice_client.is_playing():  # Pause
            self.voice_client.pause()
            # Record pause time
            self.pause_time = time.time()
            return True
        else:  # Resume
            self.voice_client.resume()
            # Calculate pause duration and readjust start time
            pause_duration: int = time.time() - self.pause_time
            self.start_time = self.start_time + pause_duration
            return False