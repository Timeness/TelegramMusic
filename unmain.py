from pyrogram import Client
from pyrogram.filters import command
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream as AudioPiped
import os
import requests
import urllib.parse
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_NAME
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Track:
    path: str
    title: str = ""

class MusicBot:
    def __init__(self):
        self.userbot = Client("userbot_py", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_NAME)
        self.bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        self.pytgcalls = PyTgCalls(self.userbot)
        self.queue: List[Track] = []
        self.current_track: Optional[Track] = None
        self.chat_id: Optional[int] = None

    @staticmethod
    def ensure_downloads_dir():
        os.makedirs("downloads", exist_ok=True)

    async def is_in_vc(self) -> bool:
        try:
            call = await self.pytgcalls.get_state(self.chat_id)
            return call is not None and call.is_running
        except Exception:
            return False

    @staticmethod
    async def fetch_song(query: str) -> Optional[Track]:
        try:
            url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={urllib.parse.quote(query)}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "SUCCESS" or not data.get("data", {}).get("results"):
                return None
            song = data["data"]["results"][0]
            title = song.get("name", "Unknown Title")
            download_url = song.get("downloadUrl", [])[-1].get("link")
            if not download_url:
                return None
            file_path = f"downloads/{title}.mp3"
            with open(file_path, "wb") as f:
                audio_response = requests.get(download_url)
                audio_response.raise_for_status()
                f.write(audio_response.content)
            return Track(path=file_path, title=title)
        except (requests.RequestException, KeyError, IndexError):
            return None

    async def play_next(self):
        if not self.queue:
            self.current_track = None
            return
        self.current_track = self.queue.pop(0)
        try:
            await self.pytgcalls.play(self.chat_id, AudioPiped(self.current_track.path))
            await self.bot.send_message(self.chat_id, f"Now playing: {self.current_track.title or os.path.basename(self.current_track.path)}")
        except Exception:
            await self.bot.send_message(self.chat_id, "Error playing track")
            await self.play_next()

    async def start_command(self, _, message):
        await message.reply("Music Bot started! Use /play, /join, /skip, /stop, or /ping.")

    async def ping_command(self, _, message):
        await message.reply("Pong! Bot is alive.")

    async def join_vc(self, _, message):
        self.chat_id = message.chat.id
        save_mp3_path = os.path.join(os.getcwd(), "Maybe.mp3")
        if not os.path.exists(save_mp3_path):
            await message.reply("Error: Maybe.mp3 not found!")
            return
        track = Track(path=save_mp3_path, title="Maybe.mp3")
        if await self.is_in_vc():
            self.queue.append(track)
            await message.reply("Added Maybe.mp3 to queue!")
            if not self.current_track:
                await self.play_next()
            return
        self.queue.append(track)
        try:
            await self.pytgcalls.play(self.chat_id, AudioPiped(save_mp3_path))
            await message.reply("Joined voice chat and started playing Maybe.mp3!")
            self.current_track = track
        except Exception:
            await message.reply("Error joining VC or playing Maybe.mp3")

    async def play_song(self, _, message):
        self.chat_id = message.chat.id
        query = " ".join(message.command[1:]) or (message.reply_to_message.text if message.reply_to_message else None)
        if not query:
            await message.reply("Please provide a song name!")
            return
        track = await self.fetch_song(query)
        if not track:
            await message.reply("No results found or error fetching song!")
            return
        self.queue.append(track)
        await message.reply(f"Added to queue: {track.title}")
        if not self.current_track:
            await self.play_next()
        if not await self.is_in_vc():
            try:
                await self.pytgcalls.play(self.chat_id, AudioPiped(self.queue[0].path))
                await message.reply("Joined voice chat and started playback!")
            except Exception:
                await message.reply("Error joining VC")

    async def skip_song(self, _, message):
        if not self.current_track:
            await message.reply("No song is playing!")
            return
        await message.reply("Skipping current song...")
        await self.play_next()

    async def stop_vc(self, _, message):
        self.chat_id = message.chat.id
        try:
            await self.pytgcalls.leave_call(self.chat_id)
            self.queue.clear()
            self.current_track = None
            await message.reply("Stopped and left voice chat!")
        except Exception:
            await message.reply("Error stopping voice chat")

    def register_handlers(self):
        self.bot.on_message(command("start"))(self.start_command)
        self.bot.on_message(command("ping"))(self.ping_command)
        self.bot.on_message(command("join"))(self.join_vc)
        self.bot.on_message(command("play"))(self.play_song)
        self.bot.on_message(command("skip"))(self.skip_song)
        self.bot.on_message(command("stop"))(self.stop_vc)

    def run(self):
        self.ensure_downloads_dir()
        try:
            self.userbot.start()
            self.bot.start()
            self.pytgcalls.start()
            print(">>> MUSIC BOT STARTED")
            idle()
        except Exception as e:
            print(f"Error during bot execution: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            self.pytgcalls.stop()
        except Exception as e:
            print(f"Error stopping pytgcalls: {e}")
        try:
            self.bot.stop()
        except Exception as e:
            print(f"Error stopping bot: {e}")
        try:
            self.userbot.stop()
        except Exception as e:
            print(f"Error stopping userbot: {e}")
        print(">>> MUSIC BOT STOPPED")


bot = MusicBot()
bot.register_handlers()
bot.run()
