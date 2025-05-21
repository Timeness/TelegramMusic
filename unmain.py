from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream as AudioPiped, Call, StreamEnded as StreamAudioEnded
import os
import requests
import urllib.parse
from config import API_ID, API_HASH, BOT_TOKEN, SESSION_NAME
from typing import Optional, List
from dataclasses import dataclass
import asyncio
import re
import subprocess
import sys
from io import StringIO
from time import time
import traceback
from inspect import getfullargspec

@dataclass
class Track:
    path: str
    title: str = ""
    thumbnail: str = ""
    artist: str = ""
    album: str = ""
    duration: str = ""

class MusicBot:
    def __init__(self):
        self.userbot = Client("userbot_py", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_NAME)
        self.bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        self.pytgcalls = PyTgCalls(self.userbot)
        self.queue: List[Track] = []
        self.current_track: Optional[Track] = None
        self.chat_id: Optional[int] = None
        self.OWNER_ID = 5896960462
        self.LOG_CHAT_ID = -1002519094633

    @staticmethod
    def ensure_downloads_dir():
        os.makedirs("downloads", exist_ok=True)

    async def is_in_vc(self) -> bool:
        try:
            return self.chat_id in self.pytgcalls.calls
        except Exception:
            return False

    @staticmethod
    async def fetch_song(query: str) -> Optional[Track]:
        try:
            url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={urllib.parse.quote(query)}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "SUCCESS" or not data.get("data", {}).get("results"):
                return None
            song = data["data"]["results"][0]
            title = song.get("name", "Unknown Title")
            download_url = song.get("downloadUrl", [])[-1].get("link")
            thumbnail = song.get("image", [])[-1].get("link") if song.get("image") else ""
            artist = song.get("primaryArtists", "Unknown Artist")
            album = song.get("album", {}).get("name", "Unknown Album")
            duration = song.get("duration", "Unknown")
            if not download_url:
                return None
            file_path = f"downloads/{title.replace('/', '_')}.mp3"
            with open(file_path, "wb") as f:
                audio_response = requests.get(download_url, timeout=10)
                audio_response.raise_for_status()
                f.write(audio_response.content)
            return Track(path=file_path, title=title, thumbnail=thumbnail, artist=artist, album=album, duration=duration)
        except Exception:
            return None

    async def play_next(self):
        if not self.queue:
            self.current_track = None
            await self.bot.send_message(self.chat_id, "🎶 Queue is empty, playback stopped.")
            return
        self.current_track = self.queue.pop(0)
        try:
            await self.pytgcalls.play(self.chat_id, AudioPiped(self.current_track.path))
            caption = f"🎵 Now playing: {self.current_track.title}\n👤 Artist: {self.current_track.artist}\n📀 Album: {self.current_track.album}\n⏳ Duration: {self.current_track.duration}"
            if self.current_track.thumbnail:
                await self.bot.send_photo(self.chat_id, self.current_track.thumbnail, caption=caption)
            else:
                await self.bot.send_message(self.chat_id, caption)
        except Exception as e:
            await self.bot.send_message(self.chat_id, f"❌ Error playing track: {str(e)}")
            await self.play_next()

    async def on_stream_end(self, client: Client, update: StreamAudioEnded):
        if isinstance(update, StreamAudioEnded) and update.chat_id == self.chat_id:
            await self.play_next()

    async def start_command(self, _, message):
        await message.reply("🎉 Music Bot started! Use /play, /join, /skip, /pause, /resume, /stop, /queue, /ping, /e, or /sh.")

    async def ping_command(self, _, message):
        try:
            latency = self.pytgcalls.ping()
            await message.reply(f"🏓 Pong! Bot is online. Latency: {latency}ms")
        except Exception as e:
            await message.reply(f"❌ Error checking ping: {str(e)}")

    async def join_vc(self, _, message):
        self.chat_id = message.chat.id
        save_mp3_path = os.path.join(os.getcwd(), "Maybe.mp3")
        if not os.path.exists(save_mp3_path):
            await message.reply("❌ Error: Maybe.mp3 not found!")
            return
        track = Track(path=save_mp3_path, title="Maybe.mp3", artist="Unknown", album="Unknown", duration="Unknown")
        if await self.is_in_vc():
            self.queue.append(track)
            await message.reply("🎶 Added Maybe.mp3 to queue!")
            if not self.current_track:
                await self.play_next()
            return
        try:
            await self.pytgcalls.play(self.chat_id, AudioPiped(save_mp3_path))
            await message.reply("🎙️ Joined voice chat and started playing Maybe.mp3!")
            self.current_track = track
        except Exception as e:
            await message.reply(f"❌ Error joining voice chat: {str(e)}")

    async def play_song(self, _, message):
        self.chat_id = message.chat.id
        query = " ".join(message.command[1:]) or (message.reply_to_message.text if message.reply_to_message else None)
        if not query:
            await message.reply("❓ Please provide a song name!")
            return
        track = await self.fetch_song(query)
        if not track:
            await message.reply("❌ No results found or error fetching song!")
            return
        self.queue.append(track)
        caption = f"✅ Added to queue: {track.title}\n👤 Artist: {track.artist}\n📀 Album: {track.album}\n⏳ Duration: {track.duration}"
        try:
            if track.thumbnail:
                await message.reply_photo(track.thumbnail, caption=caption)
            else:
                await message.reply(caption)
        except Exception as e:
            await message.reply(f"❌ Error sending message: {str(e)}")
        if not self.current_track and not await self.is_in_vc():
            try:
                await self.pytgcalls.play(self.chat_id, AudioPiped(self.queue[0].path))
                caption = f"🎙️ Joined voice chat and started playback!\n🎵 Now playing: {self.queue[0].title}\n👤 Artist: {self.queue[0].artist}\n📀 Album: {self.queue[0].album}\n⏳ Duration: {self.queue[0].duration}"
                if self.queue[0].thumbnail:
                    await self.bot.send_photo(self.chat_id, self.queue[0].thumbnail, caption=caption)
                else:
                    await self.bot.send_message(self.chat_id, caption)
                self.current_track = self.queue.pop(0)
            except Exception as e:
                await self.bot.send_message(self.chat_id, f"❌ Error joining voice chat: {str(e)}")
        elif self.current_track:
            await message.reply(f"⏳ Queued, will play after: {self.current_track.title}")

    async def skip_song(self, _, message):
        self.chat_id = message.chat.id
        if not self.current_track or not await self.is_in_vc():
            await message.reply("❌ No song is playing or bot is not in voice chat!")
            return
        try:
            await self.pytgcalls.play(self.chat_id, None)
            await message.reply(f"⏭ Skipped: {self.current_track.title}")
            await self.play_next()
        except Exception as e:
            await message.reply(f"❌ Error skipping song: {str(e)}")

    async def pause_song(self, _, message):
        self.chat_id = message.chat.id
        if not self.current_track or not await self.is_in_vc():
            await message.reply("❌ No song is playing or bot is not in voice chat!")
            return
        try:
            await self.pytgcalls.pause(self.chat_id)
            await message.reply(f"⏸ Paused: {self.current_track.title}")
        except Exception as e:
            await message.reply(f"❌ Error pausing song: {str(e)}")

    async def resume_song(self, _, message):
        self.chat_id = message.chat.id
        if not self.current_track or not await self.is_in_vc():
            await message.reply("❌ No song is playing or bot is not in voice chat!")
            return
        try:
            call = self.pytgcalls.calls.get(self.chat_id)
            if call and call.capture == "PAUSED":
                await self.pytgcalls.resume(self.chat_id)
                await message.reply(f"▶ Resumed: {self.current_track.title}")
            else:
                await message.reply("❌ Song is not paused!")
        except Exception as e:
            await message.reply(f"❌ Error resuming song: {str(e)}")

    async def queue_command(self, _, message):
        if not self.queue and not self.current_track:
            await message.reply("🎶 Queue is empty!")
            return
        queue_text = "🎵 Current Queue:\n"
        if self.current_track:
            queue_text += f"▶ Now Playing: {self.current_track.title} (Artist: {self.current_track.artist})\n"
        for i, track in enumerate(self.queue, 1):
            queue_text += f"{i}. {track.title} (Artist: {track.artist})\n"
        await message.reply(queue_text)

    async def stop_vc(self, _, message):
        self.chat_id = message.chat.id
        try:
            await self.pytgcalls.leave_call(self.chat_id)
            self.queue.clear()
            self.current_track = None
            await message.reply("🛑 Stopped and left voice chat!")
        except Exception as e:
            await message.reply(f"❌ Error stopping voice chat: {str(e)}")

    async def edit_or_reply(self, msg: Message, **kwargs):
        func = msg.edit_text if msg.from_user.is_self else msg.reply
        spec = getfullargspec(func.__wrapped__).args
        await func(**{k: v for k, v in kwargs.items() if k in spec})

    async def aexec(self, code: str, client: Client, message: Message):
        local_vars = {}
        exec(
            f"async def __aexec(client, message):\n" +
            "\n".join(f"    {line}" for line in code.split("\n")) +
            "\n    return locals().get('__ret__')",
            globals(),
            local_vars
        )
        return await local_vars["__aexec"](client, message)

    async def eval_command(self, client: Client, message: Message):
        if len(message.command) < 2:
            return await self.edit_or_reply(message, text="🔍 Please provide code to evaluate, master!")
        code = message.text.split(" ", maxsplit=1)[1]
        t1 = time()
        stdout = sys.stdout
        stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        try:
            result = await self.aexec(
                "\n".join(
                    f"    __ret__ = {line}" if not line.strip().startswith(("print", "await"))
                    else f"    {line}"
                    for line in code.split("\n")
                ),
                client,
                message
            )
            output = sys.stdout.getvalue() or sys.stderr.getvalue()
            if result is not None:
                output = str(result) if not output else f"{output}\nResult: {result}"
            elif not output:
                output = "✅ Success"
        except Exception:
            output = traceback.format_exc()
        sys.stdout = stdout
        sys.stderr = stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n⚠️ Output truncated."
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="⏳", callback_data=f"runtime {round(time()-t1, 2)}s")]]
        )
        await message.reply_text(
            f"<b>📤 Result:</b>\n<pre language='python'>{output}</pre>",
            quote=True,
            reply_markup=reply_markup
        )
        try:
            await client.send_message(
                self.LOG_CHAT_ID,
                f"#EVAL by [{message.from_user.first_name}](tg://user?id={message.from_user.id}):\n\n"
                f"<b>📥 Code:</b>\n<pre language='python'>{code}</pre>\n\n"
                f"<b>📤 Output:</b>\n<pre language='python'>{output}</pre>",
            )
        except Exception as e:
            print("Logging failed:", e)

    async def shellrunner(self, client: Client, message: Message):
        if len(message.command) < 2:
            return await self.edit_or_reply(message, text="<b>Example:</b>\n/sh git pull")
        text = message.text.split(None, 1)[1]
        output = ""
        if "\n" in text:
            lines = text.split("\n")
        else:
            lines = [text]
        for cmd in lines:
            shell = re.split(r""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", cmd)
            try:
                process = subprocess.Popen(shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = process.communicate()
                if out:
                    output += out.decode("utf-8")
                if err:
                    output += err.decode("utf-8")
            except Exception as e:
                error_trace = traceback.format_exc()
                return await self.edit_or_reply(message, text=f"<b>❌ Error:</b>\n<pre>{error_trace}</pre>")
        if not output.strip():
            output = "No Output"
        if len(output) > 4096:
            with open("output.txt", "w+", encoding="utf-8") as f:
                f.write(output)
            await client.send_document(
                message.chat.id,
                "output.txt",
                caption="<code>Output is too long, sent as file</code>",
                reply_to_message_id=message.id
            )
            os.remove("output.txt")
        else:
            await self.edit_or_reply(message, text=f"<b>📤 Output:</b>\n<pre>{output}</pre>")

    def register_handlers(self):
        self.bot.on_message(filters.command("start"))(self.start_command)
        self.bot.on_message(filters.command("ping"))(self.ping_command)
        self.bot.on_message(filters.command("join"))(self.join_vc)
        self.bot.on_message(filters.command("play"))(self.play_song)
        self.bot.on_message(filters.command("skip"))(self.skip_song)
        self.bot.on_message(filters.command("pause"))(self.pause_song)
        self.bot.on_message(filters.command("resume"))(self.resume_song)
        self.bot.on_message(filters.command("queue"))(self.queue_command)
        self.bot.on_message(filters.command("stop"))(self.stop_vc)
        self.bot.on_message(filters.command("e") & filters.user(self.OWNER_ID))(self.eval_command)
        self.bot.on_message(filters.command("sh") & filters.user(self.OWNER_ID))(self.shellrunner)

    def run(self):
        self.ensure_downloads_dir()
        try:
            self.userbot.start()
            self.bot.start()
            self.pytgcalls.start()
            print(">>> MUSIC BOT STARTED")
            idle()
        except Exception as e:
            print(f"Error during bot execution: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            self.pytgcalls.stop()
        except Exception as e:
            print(f"Error stopping pytgcalls: {str(e)}")
        try:
            self.bot.stop()
        except Exception as e:
            print(f"Error stopping bot: {str(e)}")
        try:
            self.userbot.stop()
        except Exception as e:
            print(f"Error stopping userbot: {str(e)}")
        print(">>> MUSIC BOT STOPPED")

bot = MusicBot()
bot.register_handlers()
bot.run()
