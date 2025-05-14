from pyrofork import Client, idle
from pyrofork.filters import command, user
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import InputAudioStream
import asyncio
import os
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_NAME, CHAT_ID

userbot = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
bot = Client("musc_app", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(userbot)

queue = []
current_track = None

async def main():
    await userbot.start()
    await bot.start()
    await pytgcalls.start()
    print(">>> MUSIC BOT STARTED")
    await idle()
    await userbot.stop()
    await bot.stop()
    print(">>> MUSIC BOT STOPPED")

# Command to join voice chat
@bot.on_message(command("join") & user(ADMIN_IDS))
async def join_vc(client, message):
    try:
        await pytgcalls.join_group_call(
            CHAT_ID,
            InputAudioStream("input.raw"),  # Placeholder; will be updated in play
            stream_type=StreamType().local_stream
        )
        await message.reply("Joined voice chat!")
    except Exception as e:
        await message.reply(f"Error joining VC: {str(e)}")

# Command to play a song (YouTube URL or search)
@bot.on_message(command("play"))
async def play_song(client, message):
    query = " ".join(message.command[1:]) or message.reply_to_message.text
    if not query:
        await message.reply("Please provide a song name or YouTube URL!")
        return

    # Use yt-dlp to download audio
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            file_path = f"downloads/{info['title']}.m4a"
            queue.append(file_path)
            await message.reply(f"Added to queue: {info['title']}")
            if not current_track:
                await play_next()
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Play next song in queue
async def play_next():
    global current_track
    if not queue:
        current_track = None
        return
    current_track = queue.pop(0)
    try:
        # Convert to raw audio for streaming
        os.system(f"ffmpeg -i {current_track} -f s16le -ac 2 -ar 48000 -acodec pcm_s16le input.raw")
        await pytgcalls.change_stream(
            CHAT_ID,
            InputAudioStream("input.raw")
        )
        await bot.send_message(CHAT_ID, f"Now playing: {os.path.basename(current_track)}")
    except Exception as e:
        await bot.send_message(CHAT_ID, f"Error playing track: {str(e)}")
        await play_next()

# Command to skip current song
@bot.on_message(command("skip") & user(ADMIN_IDS))
async def skip_song(client, message):
    if not current_track:
        await message.reply("No song is playing!")
        return
    await message.reply("Skipping current song...")
    await play_next()

# Command to
@bot.on_message(command("stop") & user(ADMIN_IDS))
async def stop_vc(client, message):
    try:
        await pytgcalls.leave_group_call(CHAT_ID)
        queue.clear()
        global current_track
        current_track = None
        await message.reply("Stopped and left voice chat!")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Run the bot
if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    asyncio.run(main())
