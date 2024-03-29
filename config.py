# Embed colors (v1)
color_success = 0xa6da95
color_failure = 0xed8796
color_warning = 0xeed49f
color_info = 0x91d7e3

# v2 embed colors: from https://github.com/sainnhe/everforest
colores = {
    "play": 0xa7c080,  # Operation related embeds (join/leave, track change, session settings change etc.)
    "status": 0xdbbc7f,  # Status related embeds (queue, np, etc.)
    "error": 0xe67e80  # Errors (link blocked, no playback permission, etc.)
}

# yt-dlp options
ydl_opts = {
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