# Jack the Ripper

A simple music bot that streams from YouTube and supports slash commands! 🐈‍⬛

Try the bot on our [Discord server](https://discord.gg/RNmMMF6xHY)!

![Playing something with Jack](https://cdn.discordapp.com/attachments/958651015064854551/1059756759310417940/image.png)
![Searching for a track with Jack](https://cdn.discordapp.com/attachments/1029326036149751828/1059846731434557471/image.png)

## 💠 Table of contents
- [🗡️ Features](#🗡️-features)
- [🖥️ Usage](#🖥️-usage)
- [🤨 Issues](#🤨-issues)
- 👩‍💻 [Contributing](#👩‍💻-contributing)

## 🗡️ Features
📺 Supports playing from YouTube!

- 🔗 Using [video URL](https://youtu.be/FXsGCieXm1E)

- 🔍 Searching by keyword

💻 Uses slash commands!

▶️ Playback controls 

📃 Powerful queue controls (remove, swap, move, etc)

## 🖥️ Usage

### 📦 Dependencies

You need the following packages:

- [discord.py](https://github.com/Rapptz/discord.py)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [PyNaCl](https://pypi.org/project/PyNaCl/)
- [python-dotenv](https://pypi.org/project/python-dotenv/) (NOT `dotenv`)

You can install them using `pip`.

You also need to have [ffmpeg](https://ffmpeg.org/) installed.

### 🌐 Download the bot

1. Clone this repository:

```
git clone https://github.com/succsuccsucc/jack-the-ripper.git
```

### 🪪 Get an account for the bot

1. Create a bot user in the [Discord Developer Portal](https://discord.com/developers/applications) and copy its token.

    > [Here](https://realpython.com/how-to-make-a-discord-bot-python/#how-to-make-a-discord-bot-in-the-developer-portal) is a tutorial on how to create a bot on Discord.

2. Create a file named `.env` in the bot's directory with the following contents:

```
# .env
DISCORD_TOKEN=<your-bot-token>
```

### 🏃‍♀️ Run the bot

1. Run `bot.py`

```
python3 bot.py
```

### 🏁 And you're all set!

## 🤨 Issues

### 📑 Known issues

- Playlists and Shorts are unsupported due to a YouTube limitation! The bot will refuse links to playlists and Shorts.

### 📮 Report a problem

If you encounter any issue with Jack the Ripper, open an issue on this repository or report it on our [Discord server](https://discord.gg/RNmMMF6xHY)!

## 👩‍💻 Contributing

Contributions are welcome! Open a pull request on this repository.