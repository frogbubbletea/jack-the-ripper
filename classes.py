from typing import List
from enum import Enum

import discord
import yt_dlp

from config import colores, ydl_opts

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
            with yt_dlp.YouTubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                info = ydl.sanitize_info(info)  # Ensure info is a dict

                # Initialize attributes after track is found
                self.url: str = url
                self.title: str = info["title"]
                self.duration: int = info.get["duration"]
                self.uploader: str = info.get["uploader"]
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
        self.idle_time: int = 0  # Idle time
        # Session settings
        self.loop_status: LoopStatus = LoopStatus.OFF  # Loop mode
        self.shuffle_status: bool = False  # Shuffle play
        self.voteskip_list: List[int] = []  # List of user IDs who voted to skip current track
    
    def reset(self):
        """
        Resets all attributes of a Server instance.
        """
        self.voice_client = None
        self.queue = []
        self.current_track = None
        self.start_time = 0
        self.pause_time = 0
        self.idle_time = 0
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

    async def leave(self, user: discord.Member) -> int:
        """
        Leave the user's voice channel and reset the server the user is in, including statuses and settings.

        Parameters
        -----------
        user: :class:`discord.Member`
            The user requesting the bot to leave their voice channel.
        
        Returns
        --------
        :class:`int`
            0 if the bot successfully leaves the user's channel.
        
        Raises
        -------
        ValueError
            User is not in the voice channel as the bot.
        AttributeError
            The bot is not in a voice channel.
        """
        # Check if bot and user are in the same voice channel
        try:
            # User is not in the same voice channel
            if self.check_same_vc(user) == False:
                raise ValueError("User is not in the same voice channel as the bot.")
            # User is in the same voice channel: disconnect and reset
            else:
                await self.voice_client.disconnect()
                self.reset()
                return 0
        # Bot is not in a voice channel
        except AttributeError:
            raise AttributeError("The bot is not in a voice channel.")