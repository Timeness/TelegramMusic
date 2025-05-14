from pyrogram import Client, idle
from pyrogram.filters import command, user
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
import asyncio
import os
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_NAME

userbot = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
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

async def is_in_vc(CHAT_ID):
    try:
        call = await pytgcalls.get_group_call(CHAT_ID)
        return call is not None and call.is_running
    except Exception:
        return False

@bot.on_message(command("play"))
async def play_song(client, message):
    global current_track
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
    except Exception as e:
        await message.reply(f"Error downloading song: {str(e)}")
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
    global current_track
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
    if not current_track:
        await message.reply("No song is playing!")
        return
    await message.reply("Skipping current song...")
    await play_next()

@bot.on_message(command("stop"))
async def stop_vc(client, message):
    try:
        await pytgcalls.leave_group_call(message.chat.id)
        queue.clear()
        global current_track
        current_track = None
        await message.reply("Stopped and left voice chat!")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    asyncio.run(main())
