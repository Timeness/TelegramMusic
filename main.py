from pyrogram import Client, idle
from pyrogram.filters import command
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream as AudioPiped
import os
import requests
import urllib.parse

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
        call = await pytgcalls.get_state(chat_id)
        return call is not None and call.is_running
    except Exception:
        return False

@bot.on_message(command("start"))
async def start_command(client, message):
    await message.reply("Music Bot started! Use /play to play a song, /join to join VC and play save.mp3, /skip to skip, /stop to stop, or /ping to check status.")

@bot.on_message(command("ping"))
async def ping_command(client, message):
    await message.reply("Pong! Bot is alive.")

@bot.on_message(command("join"))
async def join_vc(client, message):
    global current_track, CHAT_ID
    CHAT_ID = message.chat.id
    save_mp3_path = os.path.join(os.getcwd(), "Maybe.mp3")  # Path to save.mp3 in root directory

    # Check if save.mp3 exists
    if not os.path.exists(save_mp3_path):
        await message.reply("Error: Maybe.mp3 not found in the root directory!")
        return

    try:
        # Check if already in VC
        if await is_in_vc(CHAT_ID):
            # Add save.mp3 to queue
            queue.append(save_mp3_path)
            await message.reply("Added Maybe.mp3 to queue!")
            if not current_track:
                await play_next()
            return

        # Join VC and play save.mp3
        queue.append(save_mp3_path)
        await pytgcalls.play(
            CHAT_ID,
            AudioPiped(save_mp3_path)
        )
        await message.reply("Joined voice chat and started playing save.mp3!")
        current_track = save_mp3_path
    except Exception as e:
        await message.reply(f"Error joining VC or playing save.mp3: {str(e)}")

@bot.on_message(command("play"))
async def play_song(client, message):
    global current_track, CHAT_ID
    CHAT_ID = message.chat.id
    query = " ".join(message.command[1:]) or (message.reply_to_message.text if message.reply_to_message else None)
    if not query:
        await message.reply("Please provide a song name!")
        return

    try:
        # Query JioSaavn API
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={urllib.parse.quote(query)}"
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for bad status
        data = response.json()

        # Check status and results
        if data.get("status") != "SUCCESS" or not data.get("data", {}).get("results") or len(data["data"]["results"]) == 0:
            await message.reply("No results found for your query!")
            return

        # Get first result
        song = data["data"]["results"][0]
        title = song.get("name", "Unknown Title")
        download_urls = song.get("downloadUrl", [])

        # Use the last download URL (highest quality, as per JavaScript)
        if not download_urls:
            await message.reply("No downloadable URL found for this song!")
            return
        download_url = download_urls[-1].get("link")
        if not download_url:
            await message.reply("Invalid download URL for this song!")
            return

        # Download the song
        file_path = f"downloads/{title}.mp3"
        with open(file_path, "wb") as f:
            audio_response = requests.get(download_url)
            audio_response.raise_for_status()
            f.write(audio_response.content)

        queue.append(file_path)
        await message.reply(f"Added to queue: {title}")
        if not current_track:
            await play_next()
    except requests.RequestException as e:
        await message.reply(f"Error fetching song from JioSaavn: {str(e)}. Try a different song.")
        return
    except KeyError as e:
        await message.reply(f"Error processing API response: Missing field {str(e)}. Try a different song.")
        return
    except IndexError as e:
        await message.reply(f"Error accessing results: {str(e)}. Try a different song.")
        return
    except Exception as e:
        await message.reply(f"Unexpected error: {str(e)}. Try a different song.")
        return

    if not await is_in_vc(CHAT_ID):
        try:
            await pytgcalls.play(
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
        await pytgcalls.play(
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
        await pytgcalls.leave_call(CHAT_ID)
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
