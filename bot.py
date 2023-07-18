# bot.py
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl

import os
import time
import random
import asyncio
from dotenv import load_dotenv

import config

# Uncomment when running on replit (1/3)
# from keep_alive import keep_alive

# change working directory to wherever bot.py is in
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# load bot token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Uncomment when running on replit (2/3)
# discord.opus.load_opus("./libopus.so.0.8.0")

# define bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="+", intents=intents, activity=discord.Game(name="The Legend of Zelda: Link's Awakening"), help_command=None)

# Prepare song queues
song_queues = []

# Find the queue for a guild
def find_queue(id):
    queue = next((guild for guild in song_queues if guild['id'] == id), None)['queue']
    return queue

# Find loop status for a guild
def find_loop(id):
    loop = next((guild for guild in song_queues if guild['id'] == id), None)['loop']
    return loop

# Find entry of guild in queues
def find_guild(id):
    guild = next((guild for guild in song_queues if guild['id'] == id), None)
    return guild

# Record track start/pause time
start_time = time.time()
pause_time = time.time()

# Convert seconds into hh:mm:ss
def convert_time(seconds):
    if seconds < 60:
        time_string = time.strftime('0:%S', time.gmtime(seconds))
    elif seconds < 3600:
        time_string = time.strftime('%M:%S', time.gmtime(seconds)).lstrip('0')
    else:
        time_string = time.strftime('%H:%M:%S', time.gmtime(seconds)).lstrip('0')
    return time_string

# Shamelessly copied from official example on discord.py github
# Maybe i'll implement it myself in the future? 🤷
# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'match_filter': 'original_url!*=/shorts/'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Function for on ready and on guild join events
# Prepare a queue for a guild
def add_queue(guild):
    queue_guild = {
            'id': guild.id,
            'loop': 0,
            'voteskip': [],
            'queue': []
        }
    song_queues.append(queue_guild)

# On ready event
# Display bot guilds
# Prepare a queue for each guild the bot is in
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild(s):\n'
            f'{guild.name}(id: {guild.id})'
        )
        add_queue(guild)

@bot.event
async def on_guild_join(guild):
    print(
        f'{bot.user} joined the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )
    add_queue(guild)

# Slash commands start
# testing commands
@bot.tree.command(description="Test test test", guilds=bot.guilds)
async def test(interaction: discord.Interaction) -> None:
    test_messages = ["Yep, it's working!", "Jack the Ripper has started a break"]
    await interaction.response.send_message(random.choice(test_messages))

# "succ" command
@bot.tree.command(description="Consume the last message in the channel!", guilds=bot.guilds)
async def succ(interaction: discord.Interaction) -> None:
    # Get message to be copied and deleted
    messages = [message async for message in interaction.channel.history(limit=1)]

    # Consumption failed
    # Send error message if author is bot
    if messages[0].author.bot:
        embed_author = discord.Embed(
            title='Message is from bot!', 
            description='Jack can\'t consume bot messages.', color=config.color_failure
            )
        await interaction.response.send_message(embed=embed_author)
        return
    
    # Send error message if message is longer than 1024 characters
    if len(messages[0].clean_content) > 1024:
        embed_length = discord.Embed(
            title="Jack can't handle your length!",
            description="Message must be no longer than 1024 characters.",
            color=config.color_failure
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
            color=config.color_success
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
            color=config.color_success
        )
        embed_succ.add_field(name="Sender", value=f"<@{messages[0].author.id}>", inline=False)
        embed_succ.add_field(name="Message", value=content, inline=False)
        await interaction.response.send_message(embed=embed_succ)

    # Delete original message
    await messages[0].delete()

    return

# "headpat" command
# Give bot a headpat
@bot.tree.command(description="Give Jack a headpat!", guilds=bot.guilds)
async def headpat(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("You give Jack a headpat. Jack seems happy.")
    await interaction.channel.send("https://tenor.com/view/link-zelda-games-gif-5585640")

# Functions for voice channel commands
# Check if user is in a voice channel
def check_voice_channel(interaction):
    voice_state = interaction.user.voice
    if voice_state is not None:
        return interaction.user.voice.channel
    else:
        return None

# Check if bot is in a voice channel
def check_bot_in_voice(interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    return voice_client  # Returns None if bot is not connected to voice

# Join/move bot to user's voice channel
async def join_voice(interaction):
    voice_client = check_bot_in_voice(interaction)
    voice_channel = check_voice_channel(interaction)

    if voice_channel is not None:
        if voice_client is not None:
            if voice_client.channel is voice_channel:  # Bot is already in user's voice channel
                return 0
            else:  # Bot is in another voice channel: move to user's voice channel
                await voice_client.move_to(voice_channel)
                return 2
        else:  # Bot is not in any voice channels: join user's voice channel
            await voice_channel.connect()
            return 1
    else:
        return -1

# Compose playback method confirmation message
# url: URL of the track
# song_title: title of the track
# vc_name: name of the current voice channel
# play_type: type of message to send
# num_skip: number of votes required to skip, play type 5 only
def play_msg(interaction, url="", song_title="", vc_name="", play_type=0, num_skip=0):
    loop_status = find_loop(interaction.guild_id)
    guild_entry = find_guild(interaction.guild_id)

    titles = ["▶️ Started playing!", 
        "⏸️ Paused!", 
        "⏯️ Resumed!",
        "⏹️ Stopped!",
        "⏭️ Skipped!",
        "✋ Voted to skip!"]
    
    colors = [config.color_success, config.color_warning, config.color_success, config.color_failure, config.color_success, config.color_warning]

    embed_play = discord.Embed(title=titles[play_type],
        color=colors[play_type])
    
    if play_type in [0, 1, 2, 4, 5]:
        if play_type == 0:
            if loop_status == 1:
                embed_play.description = "🔂 Loop track enabled"
            elif loop_status == 2:
                embed_play.description = "🔁 Loop queue enabled"
            elif loop_status == 3:
                embed_play.description = "🔀 Shuffle play enabled"

        embed_play.add_field(name="💿 Track", value=f"[{song_title}]({url})", inline=False)

        if play_type == 5:
            embed_play.add_field(
                name="🗳️ Votes", 
                value=f"{len(guild_entry['voteskip'])} / {num_skip}",
                inline=False
            )

    else:  # Clear queue confirmation
        embed_play.add_field(name="🚽 Queue cleared!", value="\u200b", inline=False)
    
    embed_play.set_footer(text=f"🔊 {vc_name}")

    return embed_play

# Compose queue add confirmation message
def queue_msg(url="", song_title=""):
    embed_queue = discord.Embed(title="👍 Added to queue!", 
        color=config.color_success)
    embed_queue.add_field(name="💿 Track", value=f"[{song_title}]({url})", inline=False)
    return embed_queue

# Check if YouTube link is valid
def is_supported(url):
    # Do not accept playlist links
    if "/playlist" in url:
        return False

    extractors = youtube_dl.extractor.gen_extractors()
    for e in extractors:
        if e.suitable(url) and e.IE_NAME != 'generic':
            return True
    return False

# Get info from YouTube link
def get_title(url, info='title'):
    info_dict = ytdl.extract_info(url, download=False)
    video_title = info_dict.get(info, None)
    return video_title

# Play next track in queue
async def play_next(interaction, start_queue=True):
    global start_time
    song_queue = find_queue(interaction.guild_id)
    loop_status = find_loop(interaction.guild_id)
    guild_entry = find_guild(interaction.guild_id)

    # Reset skip votes
    guild_entry['voteskip'] = []

    # Move queue before playing next track
    if start_queue == False and len(song_queue) >= 1:
        if loop_status == 0:
            song_queue.pop(0)
        elif loop_status == 1:  # Repeat track
            pass
        elif loop_status == 2:  # Move track to end of queue
            song_queue.append(song_queue[0])
            song_queue.pop(0)
        elif loop_status == 3:  # Move random track to front, play it
            track_chosen = random.randrange(len(song_queue))
            song_queue[0] = song_queue[track_chosen]
            song_queue.pop(track_chosen)

    # Play track
    voice_client = check_bot_in_voice(interaction)
    if len(song_queue) >= 1:
        player = await YTDLSource.from_url(song_queue[0]['url'], loop=bot.loop, stream=True)
        voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction, False), bot.loop))
        start_time = time.time()
        await interaction.channel.send(embed=play_msg(interaction, song_queue[0]['url'], player.title, voice_client.channel.name, 0))
    else:
        voice_client.stop()
        await interaction.channel.send("🏁 No more tracks in queue!")
        # If no track is added to queue in 3 minutes, disconnect the bot
        end_time = 0
        while True:
            await asyncio.sleep(1)
            end_time += 1
            if voice_client.is_playing() or voice_client.is_paused():
                return
            if end_time == 180:  # 3 minutes
                await voice_client.disconnect()
                await interaction.channel.send(f"🛌 Left voice channel `{voice_client.channel.name}` due to inactivity!")
                return

# Voice channel commands: "join"
# Join/move to user's voice channel if they are in one
@bot.tree.command(description="Make Jack join your voice channel!", guilds=bot.guilds)
async def join(interaction: discord.Interaction) -> None:
    vc_status = await join_voice(interaction)
    voice_client = check_bot_in_voice(interaction)

    if voice_client is not None:
        vc_name = voice_client.channel.name
    else:
        vc_name = ""
    
    # Confirmation/error messages
    messages = ["🤷 Jack is already in your voice channel!", 
        f"🔊 Joined voice channel `{vc_name}`!", 
        f"🏃 Moved to voice channel `{vc_name}`!",
        "🤷 You're not in a voice channel!"]
    
    await interaction.response.send_message(messages[vc_status])

# Voice channel commands: "leave"
# Leave user's voice channel if they are in one, and clear queue
@bot.tree.command(description="Clear the queue and make Jack leave your voice channel!", guilds=bot.guilds)
async def leave(interaction: discord.Interaction) -> None:
    song_queue = find_queue(interaction.guild_id) 
    voice_client = check_bot_in_voice(interaction)
    user_vc = check_voice_channel(interaction)

    # Check if user is in the same voice channel as Jack
    if user_vc is not voice_client.channel:
        await interaction.response.send_message("🚫 You must be in the same voice channel as Jack to control playback!")
        return

    # Clear queue
    song_queue.clear()

    voice_client = check_bot_in_voice(interaction)

    if voice_client is not None:
        await voice_client.disconnect()
        await interaction.response.send_message(f"🙋 Left voice channel `{voice_client.channel.name}`!")
    else:
        await interaction.response.send_message("🤷 Jack is not in a voice channel!")

# Voice channel commands: "play"
# Play (stream) audio from YouTube
@bot.tree.command(description="Play audio from YouTube. Playlists are not supported!", guilds=bot.guilds)
async def play(interaction: discord.Interaction, url: str) -> None:
    await interaction.response.defer(thinking=True)
    song_queue = find_queue(interaction.guild_id)

    # Add url to queue
    if is_supported(url):
        try:
            new_song = {
                "url": url,
                "title": get_title(url),
                "duration": get_title(url, 'duration')
            }
            song_queue.append(new_song)
        except:
            embed_blocked = discord.Embed(title="🚫 Link blocked by YouTube!",
                description="Age restricted/copyright claimed videos are not supported.",
                color=config.color_failure)
            await interaction.edit_original_response(embed=embed_blocked)
            return
    else:
        await interaction.edit_original_response(content="🚫 Invalid YouTube link!")
        return

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)

    if user_vc is None:
        await interaction.edit_original_response(content="🤷 You're not in a voice channel!")
        return
    elif (voice_client is None) or not (voice_client.is_playing() or voice_client.is_paused()):  # Start queue
        await join_voice(interaction)
        await play_next(interaction)
    
    # Confirm add to queue
    await interaction.edit_original_response(embed=queue_msg(url, new_song['title']))

# Voice channel commands: "search"
# Search on YouTube
@bot.tree.command(description="Search a track and play it!", guilds=bot.guilds)
async def search(interaction: discord.Interaction, keyword: str) -> None:
    await interaction.response.defer(thinking=True)
    song_queue = find_queue(interaction.guild_id) 

    result = ytdl.extract_info(f"ytsearch: {keyword}", download=False)['entries']  
    if len(result) > 0:
        result = result[0]  # YouTube search only returns 1 result anyway

        new_song = {
            "url": result['webpage_url'],
            "title": result['title'],
            "duration": result['duration']
        }
        song_queue.append(new_song)

        user_vc = check_voice_channel(interaction)
        voice_client = check_bot_in_voice(interaction)

        if user_vc is None:
            await interaction.edit_original_response(content="🤷 You're not in a voice channel!")
            return
        elif (voice_client is None) or not (voice_client.is_playing() or voice_client.is_paused()):  # Start queue
            await join_voice(interaction)
            await play_next(interaction)
        
        # Confirm add to queue
        await interaction.edit_original_response(embed=queue_msg(new_song['url'], new_song['title']))
    else:
        await interaction.edit_original_response(content="🤷 No results!")

# Voice channel commands: "pause"
# Pause bot
@bot.tree.command(description="Pause playback!", guilds=bot.guilds)
async def pause(interaction: discord.Interaction) -> None:
    global pause_time
    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id) 

    if voice_client is not None:
        if voice_client.is_playing():
            if user_vc is voice_client.channel:
                voice_client.pause()
                pause_time = time.time()
                await interaction.response.send_message(embed=play_msg(interaction, song_queue[0]['url'], song_queue[0]['title'], voice_client.channel.name, 1))
            else:
                await interaction.response.send_message("🚫 You must be in the same voice channel as Jack to control playback!")
        else:
            await interaction.response.send_message("🤷 Nothing to pause!")
    else:
        await interaction.response.send_message("🤷 Jack is not in a voice channel!")

# Voice channel commands: "resume"
# Resume playback
@bot.tree.command(description="Resume playback!", guilds=bot.guilds)
async def resume(interaction: discord.Interaction) -> None:
    global pause_time
    global start_time
    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id) 

    if voice_client is not None:
        if voice_client.is_paused():
            if user_vc is voice_client.channel:
                voice_client.resume()
                pause_duration = time.time() - pause_time
                start_time = start_time + pause_duration
                await interaction.response.send_message(embed=play_msg(interaction, song_queue[0]['url'], song_queue[0]['title'], voice_client.channel.name, 2))
            else:
                await interaction.response.send_message("🚫 You must be in the same voice channel as Jack to control playback!")
        else:
            await interaction.response.send_message("🤷 Nothing to resume!")
    else:
        await interaction.response.send_message("🤷 Jack is not in a voice channel!")

# Voice channel commands: "stop"
# Stop playback
@bot.tree.command(description="Stop playback and clear the queue!", guilds=bot.guilds)
async def stop(interaction: discord.Interaction) -> None:
    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id) 

    if voice_client is not None:
        if voice_client.is_playing() or voice_client.is_paused():
            if user_vc is voice_client.channel:
                # Clear queue
                song_queue.clear()

                voice_client.stop()
                await interaction.response.send_message(embed=play_msg(interaction, "", "Coming soon!", voice_client.channel.name, 3))
            else:
                await interaction.response.send_message("🚫 You must be in the same voice channel as Jack to control playback!")
        else:
            await interaction.response.send_message("🤷 Nothing to stop!")
    else:
        await interaction.response.send_message("🤷 Jack is not in a voice channel!")

# Voice channel commands: "skip"
# Skip to next track in queue
@bot.tree.command(description="Skip to next track in queue!", guilds=bot.guilds)
async def skip(interaction: discord.Interaction) -> None:
    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)

    guild_entry = find_guild(interaction.guild_id)
    song_queue = find_queue(interaction.guild_id) 
    loop_status = find_loop(interaction.guild_id)

    if voice_client is not None:
        if voice_client.is_playing() or voice_client.is_paused():
            if user_vc is voice_client.channel:
                # Remove disconnected users from voteskip list
                vc_user_list = [x.id for x in user_vc.members]
                guild_entry['voteskip'] = [x for x in guild_entry['voteskip'] if x in vc_user_list]

                # If already voted: do not add vote
                if interaction.user.id in guild_entry['voteskip']:
                    await interaction.response.send_message("🚫 You already voted to skip!")
                    return

                # Add vote to guild's voteskip list
                guild_entry['voteskip'].append(interaction.user.id)

                # Send vote confirm message
                await interaction.response.send_message(
                    embed=play_msg(
                        interaction, 
                        song_queue[0]['url'],
                        song_queue[0]['title'],
                        voice_client.channel.name,
                        5,
                        int(((len(user_vc.members) - 1) / 2)) + 1
                    )
                )

                # If vote count reached half: skip
                if len(guild_entry['voteskip']) >= int(((len(user_vc.members) - 1) / 2)) + 1:
                    # Confirm skip
                    await interaction.channel.send(embed=play_msg(interaction, song_queue[0]['url'], song_queue[0]['title'], voice_client.channel.name, 4))
                    # Skip to next track
                    voice_client.pause()
                    if loop_status == 1:
                        song_queue.pop(0)
                    await play_next(interaction, False)
                
            else:
                await interaction.response.send_message("🚫 You must be in the same voice channel as Jack to control playback!")
        else:
            await interaction.response.send_message("🤷 Nothing to skip!")
    else:
        await interaction.response.send_message("🤷 Jack is not in a voice channel!")

# Voice channel commands: "queue"
# Displays queue
# Variable for page number
page = 0

# Calculate max page index
def max_page(song_queue):
    idx = int(len(song_queue) / 5)
    # Edge case: if queue length is 0
    if len(song_queue) == 0:
        pass
    # Edge case: if queue length is non-zero multiple of 5
    elif len(song_queue) % 5 == 0:
        idx -= 1
    return idx

# # Compose page up/down buttons
# class Buttons(discord.ui.View):
#     def __init__(self, *, timeout=180):
#         super().__init__(timeout=timeout)
#     @discord.ui.button(label="Previous page",style=discord.ButtonStyle.gray,emoji="⬅️")
#     async def previous_button(self,button:discord.ui.Button,interaction:discord.Interaction):
#         # Do not change page if at first page
#         global page
#         if page == 0:
#             await interaction.response.send_message("🚫 You are already at the first page!", ephemeral=True)
#         else:
#             page -= 1
#             await interaction.response.edit_message(embed=compose_queue(page), view=self)
#     @discord.ui.button(label="Next page",style=discord.ButtonStyle.gray,emoji="➡️")
#     async def next_button(self,button:discord.ui.Button,interaction:discord.Interaction):
#         # Do not change page if at last page
#         global page
#         if page == max_page():
#             await interaction.response.send_message("🚫 You are already at the last page!", ephemeral=True)
#         else:
#             page += 1
#             await interaction.response.edit_message(embed=compose_queue(page), view=self)

# Compose page flip buttons
class Page(discord.ui.View):
    def __init__(self, *, timeout=180, song_queue=[], page=0, guild_id=0):
        super().__init__(timeout=timeout)
        self.song_queue = song_queue
        self.page = page
        self.guild_id = guild_id
    @discord.ui.button(label="⬅️ Previous page", style=discord.ButtonStyle.gray)
    async def previous_button(self,interaction:discord.Interaction, button:discord.ui.Button):
        if self.page <= 0:
            await interaction.response.send_message("🚫 You're already at the first page!", ephemeral=True)
        else:
            self.page -= 1
            await interaction.response.edit_message(embed=compose_queue(self.page, self.guild_id), view=self)
    @discord.ui.button(label="➡️ Next page", style=discord.ButtonStyle.gray)
    async def next_button(self,interaction:discord.Interaction, button:discord.ui.Button):
        if self.page >= max_page(self.song_queue):
            await interaction.response.send_message("🚫 You're already at the last page!", ephemeral=True)
        else:
            self.page += 1
            await interaction.response.edit_message(embed=compose_queue(self.page, self.guild_id), view=self)

# Compose queue display embed
def compose_queue(page, guild_id, vc_name=""):
    song_queue = find_queue(guild_id)
    
    try:
        song_slice = song_queue[5 * page: 5 * page + 5]
    except IndexError:
        song_slice = song_queue[5 * page: -1]
    
    url_slice = [song['url'] for song in song_slice]
    title_slice = [song['title'] for song in song_slice]
    duration_slice = [song['duration'] for song in song_slice]
    duration_slice = [convert_time(d) for d in duration_slice]
    duration_queue = [song['duration'] for song in song_queue]  # For calculating total queue duration

    # title_slice = [get_title(t) for t in song_slice]
    # duration_slice = [convert_time(get_title(d, 'duration')) for d in song_slice]

    embed_queue = discord.Embed(title="📃 Queue",
        color=config.color_info)
    
    loop_status = find_loop(guild_id)
    if loop_status == 1:
        embed_queue.description = "🔂 Loop track enabled"
    elif loop_status == 2:
        embed_queue.description = "🔁 Loop queue enabled"
    elif loop_status == 3:
        embed_queue.description = "🔀 Shuffle play enabled"

    for i in range(len(song_slice)):
        # title_duration_field = f"{title_slice[i]}" + " (" + str(duration_slice[i]) + ")"
        title_duration_field = f"[{title_slice[i]}]({url_slice[i]}) ({str(duration_slice[i])})"
        track_number = 5 * page + i + 1
        if i == 0 and page == 0:
            embed_queue.add_field(name="🎵 Now playing", value=title_duration_field, inline=False)
        else:
            embed_queue.add_field(name=f"💿 {track_number}", value=title_duration_field, inline=False)
    
    embed_queue.set_footer(text=f"📄 Page {page + 1} of {max_page(song_queue) + 1}\n💿 Track {5 * page + 1}-{5 * page + len(song_slice)} of {len(song_queue)}\n⌛ {convert_time(sum(duration_queue))}")
    embed_queue.set_author(name=f"🔊 {vc_name}")
    return embed_queue

# Actual command
@bot.tree.command(description="Show queue!", guilds=bot.guilds)
async def queue(interaction: discord.Interaction, page: int) -> None:
    await interaction.response.defer(thinking=True)
    song_queue = find_queue(interaction.guild_id) 
    voice_client = check_bot_in_voice(interaction)
    # Do nothing if page number is invalid
    if page - 1 < 0 or page - 1 > max_page(song_queue):
        await interaction.edit_original_response(content=f"🚫 Invalid page number!\nTotal {max_page(song_queue) + 1} page(s).")
    # Do nothing if queue is empty
    elif len(song_queue) < 1:
        await interaction.edit_original_response(content="🤷 Queue is empty!")
    else:
        await interaction.edit_original_response(
            embed=compose_queue(
                page - 1, 
                interaction.guild_id,
                voice_client.channel.name
            ), 
            view=Page(song_queue=song_queue, 
                page=page - 1, 
                guild_id=interaction.guild_id
            )
        )

# Voice channel commands: "np"
# Show current track and progress
@bot.tree.command(description="Show current track!", guilds=bot.guilds)
async def np(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id) 

    if voice_client is not None and len(song_queue) >= 1:
        # Calculate time elapsed
        if voice_client.is_paused():
            progress_int = int(pause_time - start_time)
        else:
            progress_int = int(time.time() - start_time)
        progress = convert_time(progress_int)
        track_length_int = song_queue[0]['duration']
        track_length = convert_time(track_length_int)

        # Draw progress bar
        bar = []
        for i in range(15):
            bar.append("=")
        bar_degree = int((progress_int / track_length_int) * 15)
        if bar_degree > 15:
            bar_degree = 15
        bar[bar_degree] = "🔘"
        bar = "".join(bar)

        # Compose embed
        embed_np = discord.Embed(title="🎵 Now playing", 
            color=config.color_info)
        embed_np.add_field(name="💿 Track", value=f"[{song_queue[0]['title']}]({song_queue[0]['url']})", inline=False)
        embed_np.add_field(name="\u200b", value=f"{progress} {bar} {track_length}", inline=False)
        embed_np.set_footer(text=f"🔊 {voice_client.channel.name}")
        await interaction.edit_original_response(embed=embed_np)
    else:
        await interaction.edit_original_response(content="🤷 Nothing is playing!")
        
# Voice channel commands: "loop"
# Loop current track/queue
@bot.tree.command(description="Make Jack loop current track/queue!", guilds=bot.guilds)
@app_commands.choices(mode=[
    app_commands.Choice(name='track', value=1),
    app_commands.Choice(name='queue', value=2),
    app_commands.Choice(name='off', value=0)
])
async def loop(interaction: discord.Interaction, mode: app_commands.Choice[int]) -> None:
    await interaction.response.defer(thinking=True)

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id) 

    # Do nothing if Jack is not in a voice channel
    if voice_client is None:
        await interaction.edit_original_response(content="🤷 Jack is not in a voice channel!")
        return
    
    # Do nothing if user is not in current voice channel
    if user_vc is not voice_client.channel:
        await interaction.edit_original_response(content="🚫 You must be in the same voice channel as Jack to control queue!")
        return

    guild_entry = find_guild(interaction.guild_id)
    guild_entry['loop'] = mode.value

    response_titles = ["▶️ Loop disabled!", "🔂 Loop track enabled!", "🔁 Loop queue enabled!"]
    embed_loop = discord.Embed(title=response_titles[mode.value], color=config.color_success)

    if mode.value == 1 and len(song_queue) >= 1:
        embed_loop.add_field(name="💿 Track", value=f"[{song_queue[0]['title']}]({song_queue[0]['url']})", inline=False)

    if voice_client is not None:
        embed_loop.set_footer(text=f"🔊 {voice_client.channel.name}")
    await interaction.edit_original_response(embed=embed_loop)

# Voice channel commands: "shuffle"
# Shuffle queue in true pseudorandom order
@bot.tree.command(description="Shuffle queue in actual random order!", guilds=bot.guilds)
async def shuffle(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id)

    # Do nothing if Jack is not in a voice channel
    if voice_client is None:
        await interaction.edit_original_response(content="🤷 Jack is not in a voice channel!")
        return
    
    # Do nothing if user is not in current voice channel
    if user_vc is not voice_client.channel:
        await interaction.edit_original_response(content="🚫 You must be in the same voice channel as Jack to control queue!")
        return

    guild_entry = find_guild(interaction.guild_id)
    # Toggle shuffle
    # Loop status set to 3 when shuffle mode is on
    if guild_entry['loop'] != 3:
        guild_entry['loop'] = 3
        confirmation_msg = "ena"
    else:
        guild_entry['loop'] = 0
        confirmation_msg = "disa"
    
    # Compose confirmation message
    embed_shuffle = discord.Embed(title=f"🔀 Shuffle play {confirmation_msg}bled!",
                                  color=config.color_success)
    
    # Display bot's current voice channel
    if voice_client is not None:
        embed_shuffle.set_footer(text=f"🔊 {voice_client.channel.name}")
    
    await interaction.edit_original_response(embed=embed_shuffle)

# Voice channel commands: "remove"
# Remove a track from the queue
@bot.tree.command(description="Remove a track from the queue!", guilds=bot.guilds)
async def remove(interaction: discord.Interaction, track_number: int) -> None:
    await interaction.response.defer(thinking=True)

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id)

    # Do nothing if Jack is not in a voice channel
    if voice_client is None:
        await interaction.edit_original_response(content="🤷 Jack is not in a voice channel!")
        return
    
    # Do nothing if user is not in current voice channel
    if user_vc is not voice_client.channel:
        await interaction.edit_original_response(content="🚫 You must be in the same voice channel as Jack to control queue!")
        return

    # Do nothing if queue is empty
    if len(song_queue) < 1:
        await interaction.edit_original_response(content="🤷 Queue is empty!")

    # Do nothing if track number is invalid
    # Currently playing track (track 1 to user) is not removable
    elif (track_number < 2) or (track_number > len(song_queue)):
        await interaction.edit_original_response(content=f"🚫 Invalid track number!")
    
    else:
        # Get info for confirmation message
        removed_url = song_queue[track_number - 1]['url']
        removed_title = song_queue[track_number - 1]['title']

        # Remove the track from queue
        song_queue.pop(track_number - 1)

        # Compose confirmation message
        embed_remove = discord.Embed(
            title="🚮 Removed from queue!",
            color=config.color_success
        )
        embed_remove.add_field(
            name=f"💿 {track_number}",
            value=f"[{removed_title}]({removed_url})",
            inline=False
        )

        # Add bot's current voice channel to confirmation message
        if voice_client is not None:
            embed_remove.set_footer(text=f"🔊 {voice_client.channel.name}")
        
        # Send the confirmation message
        await interaction.edit_original_response(embed=embed_remove)

# Voice channel commands: "swap"
# Swap two tracks in queue
@bot.tree.command(description="Swap two tracks in the queue!", guilds=bot.guilds)
async def swap(interaction: discord.Interaction, track_one: int, track_two: int) -> None:
    await interaction.response.defer(thinking=True)

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id)

    # Do nothing if Jack is not in a voice channel
    if voice_client is None:
        await interaction.edit_original_response(content="🤷 Jack is not in a voice channel!")
        return
    
    # Do nothing if user is not in current voice channel
    if user_vc is not voice_client.channel:
        await interaction.edit_original_response(content="🚫 You must be in the same voice channel as Jack to control queue!")
        return
    
    # Do nothing if queue is empty
    if len(song_queue) < 1:
        await interaction.edit_original_response(content="🤷 Queue is empty!")

    # Do nothing if track number is invalid
    # Currently playing track (track 1 to user) is not swappable
    elif track_one not in range(2, len(song_queue) + 1) or track_two not in range(1, len(song_queue) + 1):
        await interaction.edit_original_response(content=f"🚫 Invalid track number!")
    
    else:
        # Compose confirmation message
        embed_swap = discord.Embed(
            title="🔃 Swapped tracks!",
            color=config.color_success
        )
        embed_swap.add_field(
            name="Swapped",
            value=f"{track_one} -> **{track_two}**: [{song_queue[track_one - 1]['title']}]({song_queue[track_one - 1]['url']})",
            inline=False
        )
        embed_swap.add_field(
            name="With",
            value=f"{track_two} -> **{track_one}**: [{song_queue[track_two - 1]['title']}]({song_queue[track_two - 1]['url']})",
            inline=False
        )
        
        # Store track one in temp variable
        temp = song_queue[track_one - 1]
        # Move track two to track one's index
        song_queue[track_one - 1] = song_queue[track_two - 1]
        # Restore track one to track two's index
        song_queue[track_two - 1] = temp

        # Add bot's current voice channel to confirmation message
        if voice_client is not None:
            embed_swap.set_footer(text=f"🔊 {voice_client.channel.name}")
        
        # Send the confirmation message
        await interaction.edit_original_response(embed=embed_swap)

# Voice channel commands: "move"
# Move a track in queue
@bot.tree.command(description="Move a track to another position!", guilds=bot.guilds)
async def move(interaction: discord.Interaction, track_number: int, position: int) -> None:
    await interaction.response.defer(thinking=True)

    user_vc = check_voice_channel(interaction)
    voice_client = check_bot_in_voice(interaction)
    song_queue = find_queue(interaction.guild_id)

    # Do nothing if Jack is not in a voice channel
    if voice_client is None:
        await interaction.edit_original_response(content="🤷 Jack is not in a voice channel!")
        return
    
    # Do nothing if user is not in current voice channel
    if user_vc is not voice_client.channel:
        await interaction.edit_original_response(content="🚫 You must be in the same voice channel as Jack to control queue!")
        return

    # Do nothing if queue is empty
    if len(song_queue) < 1:
        await interaction.edit_original_response(content="🤷 Queue is empty!")
    
    # Do nothing if track number is invalid
    # Currently playing track (track 1 to user) is not movable
    elif track_number not in range(2, len(song_queue) + 1) or position not in range(2, len(song_queue) + 1):
        await interaction.edit_original_response(content=f"🚫 Invalid track number!")
    
    else:
        # Compose confirmation message
        embed_move = discord.Embed(
            title="🫴 Moved track!",
            color=config.color_success
        )
        embed_move.add_field(
            name="💿 Moved",
            value=f"{track_number}: [{song_queue[track_number - 1]['title']}]({song_queue[track_number - 1]['url']})",
            inline=False
        )
        embed_move.add_field(
            name="To position",
            value=f"{position}",
            inline=False
        )

        # Insert track to specified position
        song_queue.insert(position - 1, song_queue[track_number - 1])
        # Remove track from original position
        # All tracks after specified position are moved backward by 1!
        song_queue.pop(track_number)

        # Add bot's current voice channel to confirmation message
        if voice_client is not None:
            embed_move.set_footer(text=f"🔊 {voice_client.channel.name}")
        
        # Send the confirmation message
        await interaction.edit_original_response(embed=embed_move)

# Slash commands end

# Text commands start
# "sync" command
# Syncs command tree with Discord
@commands.guild_only()
@bot.command()
async def sync(ctx):
    if ctx.author.id == 740098404688068641:
        await bot.tree.sync()
        await ctx.send("Commands synced!")
    else:
        await ctx.send("Impostor! You are not the chosen one!")
# Text commands end

# Uncomment when running on replit (3/3)
# keep_alive()

# (text) command not found error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.CommandNotFound):
        return
    raise error

# Launch bot
bot.run(TOKEN)