import asyncio
import aiohttp
import os
import time
import math
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
    InputMediaPhoto,
)
from pyrogram.errors import UserAlreadyParticipant, FloodWait

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, GroupCallNotFound
from pytgcalls.types.stream import StreamAudioEnded

from youtubesearchpython.__future__ import VideosSearch
from PIL import Image, ImageDraw, ImageFont

from config import API_ID, API_HASH, TOKEN, STRING_SESSION

API_BASE = "http://45.77.174.241:9090"

bot = Client(
    "AloneRobotBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TOKEN,
)

assistant = Client(
    "AloneRobotAssistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

call_py = PyTgCalls(assistant)

active_chats: Dict[int, dict] = {}
queues: Dict[int, List] = {}
loop_states: Dict[int, bool] = {}
progress_tasks: Dict[int, asyncio.Task] = {}


@dataclass
class Track:
    title: str
    video_id: str
    duration: int
    duration_text: str
    requested_by: str
    stream_url: str
    token: str
    thumbnail: str
    file_path: str
    started: float = field(default_factory=time.time)
    speed: float = 1.0


async def search_youtube(query: str):
    result = await VideosSearch(query, limit=1).next()
    if not result["result"]:
        return None

    data = result["result"][0]

    duration_text = data.get("duration", "0:00")
    duration = time_to_seconds(duration_text)

    return {
        "title": data["title"],
        "video_id": data["id"],
        "duration": duration,
        "duration_text": duration_text,
        "thumbnail": data["thumbnails"][0]["url"],
    }


async def get_video_by_url(url: str):
    if "youtu" not in url:
        return None

    if "v=" in url:
        video_id = url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0]
    else:
        return None

    result = await VideosSearch(video_id, limit=1).next()

    if not result["result"]:
        return None

    data = result["result"][0]

    duration_text = data.get("duration", "0:00")
    duration = time_to_seconds(duration_text)

    return {
        "title": data["title"],
        "video_id": data["id"],
        "duration": duration,
        "duration_text": duration_text,
        "thumbnail": data["thumbnails"][0]["url"],
    }


async def fetch_download_token(video_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/download",
            params={"url": video_id, "type": "audio"},
        ) as response:
            if response.status != 200:
                raise Exception("Failed to get download token")

            data = await response.json()
            return data["download_token"]


async def download_audio(video_id: str, token: str):
    url = f"{API_BASE}/stream/{video_id}?type=audio"

    headers = {
        "X-Download-Token": token,
    }

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{video_id}.raw")

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception("Failed to download stream")

            with open(file_path, "wb") as f:
                async for chunk in response.content.iter_chunked(1024 * 512):
                    f.write(chunk)

    return file_path


async def generate_thumbnail(track: Track):
    async with aiohttp.ClientSession() as session:
        async with session.get(track.thumbnail) as response:
            image_data = await response.read()

    bg_path = os.path.join(tempfile.gettempdir(), f"thumb_{track.video_id}.png")

    with open(bg_path, "wb") as f:
        f.write(image_data)

    image = Image.open(bg_path).convert("RGB")
    image = image.resize((1280, 720))

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 120))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(image)

    try:
        font_big = ImageFont.truetype("arial.ttf", 42)
        font_small = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((40, 500), track.title[:40], font=font_big, fill="white")
    draw.text((40, 580), f"Duration: {track.duration_text}", font=font_small, fill="white")
    draw.text((40, 630), f"Requested by: {track.requested_by}", font=font_small, fill="white")

    final_path = os.path.join(tempfile.gettempdir(), f"final_{track.video_id}.png")
    image.convert("RGB").save(final_path)

    return final_path


async def ensure_assistant(chat_id: int):
    try:
        invite = await bot.export_chat_invite_link(chat_id)
        try:
            await assistant.join_chat(invite)
        except UserAlreadyParticipant:
            pass
        except Exception:
            pass
    except Exception:
        pass


async def build_track(query: str, requester: str):
    if query.startswith("http"):
        song = await get_video_by_url(query)
    else:
        song = await search_youtube(query)

    if not song:
        raise Exception("Song not found")

    token = await fetch_download_token(song["video_id"])

    file_path = await download_audio(song["video_id"], token)

    stream_url = f"{API_BASE}/stream/{song['video_id']}?type=audio"

    return Track(
        title=song["title"],
        video_id=song["video_id"],
        duration=song["duration"],
        duration_text=song["duration_text"],
        requested_by=requester,
        stream_url=stream_url,
        token=token,
        thumbnail=song["thumbnail"],
        file_path=file_path,
    )


def time_to_seconds(time_str: str):
    try:
        parts = list(map(int, time_str.split(":")))

        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]

        return parts[0] * 60 + parts[1]
    except Exception:
        return 0


def seconds_to_time(seconds: int):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def progress_bar(current: int, total: int):
    if total <= 0:
        return "◉──────────"

    percentage = current / total
    filled = math.floor(percentage * 10)

    bar = "─" * filled + "◉" + "─" * (10 - filled)
    return bar


async def build_caption(chat_id: int):
    data = active_chats.get(chat_id)

    if not data:
        return "Nothing playing"

    track: Track = data["track"]

    elapsed = int(time.time() - track.started)

    if elapsed > track.duration:
        elapsed = track.duration

    state = data.get("state", "Playing")

    queue_count = len(queues.get(chat_id, []))

    return (
        f"🎵 **Now Playing**\n\n"
        f"**Title:** {track.title}\n"
        f"**Duration:** {track.duration_text}\n"
        f"**Requester:** {track.requested_by}\n"
        f"**State:** {state}\n"
        f"**Queue:** {queue_count}\n\n"
        f"`{progress_bar(elapsed, track.duration)}`\n"
        f"`{seconds_to_time(elapsed)} / {track.duration_text}`"
    )


def player_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⏸ Pause", callback_data="pause"),
                InlineKeyboardButton("▶ Resume", callback_data="resume"),
            ],
            [
                InlineKeyboardButton("⏹ Stop", callback_data="stop"),
                InlineKeyboardButton("⏭ Skip", callback_data="skip"),
            ],
            [
                InlineKeyboardButton("🔁 Loop", callback_data="loop"),
                InlineKeyboardButton("⚡ Speed", callback_data="speed"),
            ],
            [
                InlineKeyboardButton("➕ Queue", callback_data="queue")
            ],
        ]
    )


async def send_player(chat_id: int):
    data = active_chats.get(chat_id)

    if not data:
        return

    track: Track = data["track"]

    thumb = await generate_thumbnail(track)

    caption = await build_caption(chat_id)

    if data.get("message"):
        try:
            await data["message"].edit_media(
                InputMediaPhoto(media=thumb, caption=caption),
                reply_markup=player_buttons(),
            )
            return
        except Exception:
            pass

    message = await bot.send_photo(
        chat_id,
        photo=thumb,
        caption=caption,
        reply_markup=player_buttons(),
    )

    data["message"] = message


async def update_progress(chat_id: int):
    while chat_id in active_chats:
        try:
            await send_player(chat_id)
        except Exception:
            pass

        await asyncio.sleep(10)


async def play_track(chat_id: int, track: Track):
    headers = {
        "X-Download-Token": track.token,
    }

    ffmpeg_parameters = (
        f"-headers 'X-Download-Token: {track.token}' "
        f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    )

    stream = AudioPiped(
        track.stream_url,
        HighQualityAudio(),
        headers=headers,
        ffmpeg_parameters=ffmpeg_parameters,
    )

    try:
        await call_py.play(
            chat_id,
            stream,
        )
    except NoActiveGroupCall:
        raise Exception("Start a voice chat first")
    except GroupCallNotFound:
        raise Exception("Voice chat not found")

    active_chats[chat_id] = {
        "track": track,
        "state": "Playing",
        "message": None,
    }

    if chat_id in progress_tasks:
        progress_tasks[chat_id].cancel()

    progress_tasks[chat_id] = asyncio.create_task(update_progress(chat_id))

    await send_player(chat_id)


async def skip_current(chat_id: int):
    if loop_states.get(chat_id):
        current = active_chats[chat_id]["track"]
        current.started = time.time()
        await play_track(chat_id, current)
        return

    if not queues.get(chat_id):
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass

        if chat_id in active_chats:
            data = active_chats.pop(chat_id)

            if data.get("message"):
                try:
                    await data["message"].edit_caption("⏹ Playback ended")
                except Exception:
                    pass

        if chat_id in progress_tasks:
            progress_tasks[chat_id].cancel()
            progress_tasks.pop(chat_id, None)

        return

    next_track = queues[chat_id].pop(0)
    next_track.started = time.time()

    await play_track(chat_id, next_track)


@call_py.on_stream_end()
async def stream_end_handler(_, update: StreamAudioEnded):
    chat_id = update.chat_id

    try:
        await skip_current(chat_id)
    except Exception:
        pass


@bot.on_message(filters.command("play"))
async def play_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /play song name or youtube link")

    query = " ".join(message.command[1:])

    processing = await message.reply_text("🔄 Processing...")

    try:
        await ensure_assistant(message.chat.id)

        requester = message.from_user.mention if message.from_user else "Anonymous"

        track = await build_track(query, requester)

        if message.chat.id in active_chats:
            queues.setdefault(message.chat.id, []).append(track)

            await processing.edit_text(
                f"➕ Added to queue\n\n{track.title}"
            )
            return

        await play_track(message.chat.id, track)

        await processing.delete()

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await processing.edit_text(f"❌ Error: {str(e)}")


@bot.on_message(filters.command("pause"))
async def pause_handler(_, message: Message):
    try:
        await call_py.pause_stream(message.chat.id)
        active_chats[message.chat.id]["state"] = "Paused"
        await message.reply_text("⏸ Playback paused")
    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command("resume"))
async def resume_handler(_, message: Message):
    try:
        await call_py.resume_stream(message.chat.id)
        active_chats[message.chat.id]["state"] = "Playing"
        await message.reply_text("▶ Playback resumed")
    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command(["stop", "end"]))
async def stop_handler(_, message: Message):
    try:
        queues.pop(message.chat.id, None)

        if message.chat.id in progress_tasks:
            progress_tasks[message.chat.id].cancel()
            progress_tasks.pop(message.chat.id, None)

        await call_py.leave_call(message.chat.id)

        if message.chat.id in active_chats:
            active_chats.pop(message.chat.id)

        await message.reply_text("⏹ Playback stopped")
    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command("skip"))
async def skip_handler(_, message: Message):
    try:
        await skip_current(message.chat.id)
        await message.reply_text("⏭ Skipped")
    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command("seek"))
async def seek_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /seek seconds")

    try:
        seconds = int(message.command[1])

        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("Nothing playing")

        track: Track = data["track"]

        elapsed = int(time.time() - track.started)
        new_time = elapsed + seconds

        if new_time >= track.duration:
            new_time = track.duration - 1

        track.started = time.time() - new_time

        await message.reply_text(f"⏩ Seeked to {seconds_to_time(new_time)}")

    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command("seekback"))
async def seekback_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /seekback seconds")

    try:
        seconds = int(message.command[1])

        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("Nothing playing")

        track: Track = data["track"]

        elapsed = int(time.time() - track.started)
        new_time = max(0, elapsed - seconds)

        track.started = time.time() - new_time

        await message.reply_text(f"⏪ Seeked back to {seconds_to_time(new_time)}")

    except Exception as e:
        await message.reply_text(str(e))


@bot.on_message(filters.command("speed"))
async def speed_handler(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /speed 1.0-3.0")

    try:
        value = float(message.command[1])

        if value < 0.5 or value > 3.0:
            return await message.reply_text("Speed must be between 0.5 and 3.0")

        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("Nothing playing")

        track: Track = data["track"]
        track.speed = value

        await message.reply_text(f"⚡ Speed changed to {value}x")

    except Exception as e:
        await message.reply_text(str(e))


@bot.on_callback_query()
async def callbacks(_, query: CallbackQuery):
    chat_id = query.message.chat.id
    data = query.data

    try:
        if data == "pause":
            await call_py.pause_stream(chat_id)
            active_chats[chat_id]["state"] = "Paused"
            await query.answer("Paused")

        elif data == "resume":
            await call_py.resume_stream(chat_id)
            active_chats[chat_id]["state"] = "Playing"
            await query.answer("Resumed")

        elif data == "stop":
            queues.pop(chat_id, None)

            if chat_id in progress_tasks:
                progress_tasks[chat_id].cancel()
                progress_tasks.pop(chat_id, None)

            await call_py.leave_call(chat_id)
            active_chats.pop(chat_id, None)

            await query.message.edit_caption("⏹ Playback stopped")
            await query.answer("Stopped")

        elif data == "skip":
            await skip_current(chat_id)
            await query.answer("Skipped")

        elif data == "loop":
            current = loop_states.get(chat_id, False)
            loop_states[chat_id] = not current
            await query.answer(
                f"Loop {'enabled' if not current else 'disabled'}"
            )

        elif data == "speed":
            await query.answer("Use /speed command")

        elif data == "queue":
            queue = queues.get(chat_id, [])

            if not queue:
                return await query.answer("Queue empty", show_alert=True)

            text = "🎶 Queue List\n\n"

            for idx, item in enumerate(queue[:15], start=1):
                text += f"{idx}. {item.title}\n"

            await query.message.reply_text(text)
            await query.answer()

        await send_player(chat_id)

    except Exception as e:
        await query.answer(str(e), show_alert=True)


async def stream_recovery():
    while True:
        try:
            for chat_id, data in list(active_chats.items()):
                try:
                    await call_py.get_call(chat_id)
                except Exception:
                    track: Track = data["track"]
                    await play_track(chat_id, track)
        except Exception:
            pass

        await asyncio.sleep(30)


async def cleanup_files():
    while True:
        try:
            temp_dir = tempfile.gettempdir()

            for file in os.listdir(temp_dir):
                if file.startswith(("thumb_", "final_")) or file.endswith(".raw"):
                    path = os.path.join(temp_dir, file)

                    try:
                        if time.time() - os.path.getmtime(path) > 3600:
                            os.remove(path)
                    except Exception:
                        pass
        except Exception:
            pass

        await asyncio.sleep(600)


async def startup():
    await bot.start()
    await assistant.start()
    await call_py.start()

    asyncio.create_task(stream_recovery())
    asyncio.create_task(cleanup_files())

    print("Music system started")

    await idle()


async def idle():
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(startup())
