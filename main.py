from pyrogram import Client, idle
from pyrogram.filters import command
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream as AudioPiped
import os

# Assuming config.py is correctly set up
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_NAME

# Initialize clients
userbot = Client("userbot_py", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_NAME)
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(userbot)

queue = []
current_track = None
CHAT_ID = None  # Store CHAT_ID globally

async def is_in_vc(chat_id):
    try:
        call = await pytgcalls.get_group_call(chat_id)
        return call is not None and call.is_running
    except Exception:
        return False

@bot.on_message(command("start"))
async def start_command(client, message):
    await message.reply("Music Bot started! Use /play to play a song, /skip to skip, /stop to stop, or /ping to check status.")

@bot.on_message(command("ping"))
async def ping_command(client, message):
    await message.reply("Pong! Bot is alive.")

@bot.on_message(command("play"))
async def play_song(client, message):
    global current_track, CHAT_ID
    CHAT_ID = message.chat.id
    query = " ".join(message.command[1:]) or (message.reply_to_message.text if message.reply_to_message else None)
    if not query:
        await message.reply("Please provide a song name or YouTube URL!")
        return

    try:
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            file_path = f"downloads/{info['title']}.mp3"
            queue.append(file_path)
            await message.reply(f"Added to queue: {info['title']}")
            if not current_track:
                await play_next()
    except yt_dlp.utils.DownloadError as e:
        await message.reply(f"Error downloading song: {str(e)}")
        return
    except Exception as e:
        await message.reply(f"Unexpected error: {str(e)}")
        return

    if not await is_in_vc(CHAT_ID):
        try:
            await pytgcalls.join_group_call(
                CHAT_ID,
                AudioPiped(queue[0])
            )
            await message.reply("Joined voice chat and started playback!")
        except Exception as e:
            await message.reply(f"Error joining VC: {str(e)}")

async def play_next():
    global current_track, CHAT_ID
    if not queue:
        current_track = None
        return
    current_track = queue.pop(0)
    try:
        await pytgcalls.change_stream(
            CHAT_ID,
            AudioPiped(current_track)
        )
        await bot.send_message(CHAT_ID, f"Now playing: {os.path.basename(current_track)}")
    except Exception as e:
        await bot.send_message(CHAT_ID, f"Error playing track: {str(e)}")
        await play_next()

@bot.on_message(command("skip"))
async def skip_song(client, message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    if not current_track:
        await message.reply("No song is playing!")
        return
    await message.reply("Skipping current song...")
    await play_next()

@bot.on_message(command("stop"))
async def stop_vc(client, message):
    global current_track, CHAT_ID
    CHAT_ID = message.chat.id
    try:
        await pytgcalls.leave_group_call(CHAT_ID)
        queue.clear()
        current_track = None
        await message.reply("Stopped and left voice chat!")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Create downloads directory
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# Start the bot
try:
    userbot.start()
    bot.start()
    pytgcalls.start()
    print(">>> MUSIC BOT STARTED")
    idle()  # Keep the bot running
except Exception as e:
    print(f"Error during bot execution: {e}")
finally:
    try:
        pytgcalls.stop()
    except Exception as e:
        print(f"Error stopping pytgcalls: {e}")
    try:
        bot.stop()
    except Exception as e:
        print(f"Error stopping bot: {e}")
    try:
        userbot.stop()
    except Exception as e:
        print(f"Error stopping userbot: {e}")
    print(">>> MUSIC BOT STOPPED")
