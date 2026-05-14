import asyncio
import aiohttp
import os
import time
import math
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from AloneRobot import pbot as alone 

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
    InputMediaPhoto,
)
from pyrogram.errors import UserAlreadyParticipant, FloodWait

from youtubesearchpython.__future__ import VideosSearch
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from AloneRobot.config import API_ID, API_HASH, TOKEN
from AloneRobot.modules.call import (
    call_py,
    assistant,
    active_chats,
    queues,
    loop_states,
    progress_tasks,
    shuffle_states,
    user_stats,
    register_stream_end_handler,
    ensure_assistant,
    play_audio,
    pause_stream as call_pause_stream,
    resume_stream as call_resume_stream,
    leave_call,
)

API_BASE = "http://45.77.174.241:9090"

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
    plays: int = 0
    created_at: float = field(default_factory=time.time)


async def search_youtube(query: str):
    """Search for a video on YouTube"""
    try:
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
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        return None


async def get_video_by_url(url: str):
    """Extract video info from YouTube URL"""
    try:
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
    except Exception as e:
        print(f"Error getting video by URL: {e}")
        return None


async def fetch_download_token(video_id: str):
    """Fetch download token from API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/download",
                params={"url": video_id, "type": "audio"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise Exception("Failed to get download token")

                data = await response.json()
                return data["download_token"]
    except Exception as e:
        print(f"Error fetching download token: {e}")
        raise


async def download_audio(video_id: str, token: str):
    """Download audio file"""
    try:
        url = f"{API_BASE}/stream/{video_id}?type=audio"

        headers = {
            "X-Download-Token": token,
        }

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"{video_id}.raw")

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    raise Exception("Failed to download stream")

                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        f.write(chunk)

        return file_path
    except Exception as e:
        print(f"Error downloading audio: {e}")
        raise


async def generate_thumbnail(track: Track, theme: str = "purple"):
    """Generate Spotify-like thumbnail with enhanced design"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(track.thumbnail, timeout=aiohttp.ClientTimeout(total=10)) as response:
                image_data = await response.read()

        bg_path = os.path.join(tempfile.gettempdir(), f"thumb_{track.video_id}.png")

        with open(bg_path, "wb") as f:
            f.write(image_data)

        # Load and resize image
        image = Image.open(bg_path).convert("RGB")
        image = image.resize((1280, 720))

        # Create a blurred background version
        blur_bg = image.filter(ImageFilter.GaussianBlur(radius=15))
        blur_bg = blur_bg.resize((1280, 720))

        # Create darker overlay for text readability
        overlay = Image.new("RGBA", blur_bg.size, (0, 0, 0, 180))
        blur_bg = Image.alpha_composite(blur_bg.convert("RGBA"), overlay)

        # Add album art in the center
        album_size = 350
        album_x = (1280 - album_size) // 2
        album_y = 80
        image = image.resize((album_size, album_size))
        blur_bg.paste(image, (album_x, album_y))

        # Draw text
        draw = ImageDraw.Draw(blur_bg)

        try:
            font_title = ImageFont.truetype("arial.ttf", 56)
            font_info = ImageFont.truetype("arial.ttf", 32)
            font_small = ImageFont.truetype("arial.ttf", 24)
        except Exception:
            font_title = ImageFont.load_default()
            font_info = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Title (with text wrapping)
        title_text = track.title[:45]
        draw.text((80, 480), title_text, font=font_title, fill="white")

        # Duration
        draw.text((80, 560), f"⏱️ {track.duration_text}", font=font_info, fill="#1DB954")

        # Requested by
        draw.text((80, 620), f"👤 {track.requested_by[:30]}", font=font_small, fill="#B3B3B3")

        # Views/Plays count
        draw.text((850, 560), f"▶️ Plays: {track.plays}", font=font_info, fill="#1DB954")

        # Playback speed indicator (if not 1.0x)
        if track.speed != 1.0:
            draw.text((850, 620), f"⚡ Speed: {track.speed}x", font=font_small, fill="#FFD700")

        final_path = os.path.join(tempfile.gettempdir(), f"final_{track.video_id}.png")
        blur_bg.convert("RGB").save(final_path)

        return final_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


async def build_track(query: str, requester: str):
    """Build track object from query"""
    try:
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
    except Exception as e:
        print(f"Error building track: {e}")
        raise


def time_to_seconds(time_str: str) -> int:
    """Convert time string to seconds"""
    try:
        parts = list(map(int, time_str.split(":")))

        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]

        return parts[0] * 60 + parts[1]
    except Exception:
        return 0


def seconds_to_time(seconds: int) -> str:
    """Convert seconds to time string"""
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def progress_bar(current: int, total: int) -> str:
    """Generate visual progress bar"""
    if total <= 0:
        return "▮──────────── 0%"

    percentage = (current / total) * 100
    filled = math.floor((current / total) * 20)

    bar = "▮" * filled + "▯" * (20 - filled)
    return f"{bar} {percentage:.1f}%"


async def build_caption(chat_id: int) -> str:
    """Build player caption with detailed info"""
    data = active_chats.get(chat_id)

    if not data:
        return "🎵 **Nothing playing**\n\nUse /play to start playing music"

    track: Track = data["track"]
    elapsed = int(time.time() - track.started)

    if elapsed > track.duration:
        elapsed = track.duration

    state = data.get("state", "Playing")
    queue_count = len(queues.get(chat_id, []))
    
    loop_state = loop_states.get(chat_id, 0)
    loop_text = "🔁 Loop All" if loop_state == 1 else "🔂 Loop One" if loop_state == 2 else "➡️ No Loop"
    
    shuffle_state = shuffle_states.get(chat_id, False)
    shuffle_text = "🔀 Shuffle ON" if shuffle_state else "🔀 Shuffle OFF"

    caption = (
        f"🎵 **Now Playing**\n\n"
        f"**Title:** `{track.title}`\n"
        f"**Duration:** `{track.duration_text}`\n"
        f"**Requester:** `{track.requested_by}`\n"
        f"**State:** `{state}`\n"
        f"**Speed:** `{track.speed}x`\n"
        f"**Queue:** `{queue_count} songs`\n\n"
        f"{progress_bar(elapsed, track.duration)}\n"
        f"`{seconds_to_time(elapsed)} / {track.duration_text}`\n\n"
        f"{loop_text} • {shuffle_text}"
    )
    
    return caption


def player_buttons():
    """Generate player control buttons"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⏮ Previous", callback_data="previous"),
                InlineKeyboardButton("⏸ Pause", callback_data="pause"),
                InlineKeyboardButton("▶ Resume", callback_data="resume"),
                InlineKeyboardButton("⏭ Next", callback_data="next"),
            ],
            [
                InlineKeyboardButton("⏹ Stop", callback_data="stop"),
                InlineKeyboardButton("🔁 Loop", callback_data="loop"),
                InlineKeyboardButton("🔀 Shuffle", callback_data="shuffle"),
            ],
            [
                InlineKeyboardButton("⚡ Speed", callback_data="speed"),
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
            ],
            [
                InlineKeyboardButton("➕ Queue", callback_data="queue"),
                InlineKeyboardButton("🎵 Now Playing", callback_data="nowplaying"),
            ],
        ]
    )


async def send_player(chat_id: int):
    """Send or update player message"""
    try:
        data = active_chats.get(chat_id)

        if not data:
            return

        track: Track = data["track"]
        thumb = await generate_thumbnail(track)

        if not thumb:
            return

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
    except Exception as e:
        print(f"Error sending player: {e}")


async def update_progress(chat_id: int):
    """Update player progress periodically"""
    while chat_id in active_chats:
        try:
            await send_player(chat_id)
        except Exception:
            pass

        await asyncio.sleep(8)


async def play_track(chat_id: int, track: Track):
    """Play a track"""
    try:
        # Use ffmpeg to play from stream URL
        success = await play_audio(chat_id, track.stream_url, volume=100)
        
        if not success:
            raise Exception("❌ Failed to play track")

        active_chats[chat_id] = {
            "track": track,
            "state": "Playing",
            "message": None,
            "history": [track],
        }

        # Track play statistics
        if chat_id not in user_stats:
            user_stats[chat_id] = {"total_plays": 0, "total_duration": 0}
        
        user_stats[chat_id]["total_plays"] += 1
        user_stats[chat_id]["total_duration"] += track.duration
        track.plays += 1

        if chat_id in progress_tasks:
            progress_tasks[chat_id].cancel()

        progress_tasks[chat_id] = asyncio.create_task(update_progress(chat_id))

        await send_player(chat_id)
    except Exception as e:
        print(f"Error playing track: {e}")
        raise


async def skip_current(chat_id: int):
    """Skip to next track"""
    try:
        loop_state = loop_states.get(chat_id, 0)
        
        # Loop one mode
        if loop_state == 2:
            current = active_chats[chat_id]["track"]
            current.started = time.time()
            await play_track(chat_id, current)
            return

        # No more tracks
        if not queues.get(chat_id):
            try:
                await leave_call(chat_id)
            except Exception:
                pass

            if chat_id in active_chats:
                data = active_chats.pop(chat_id)
                if data.get("message"):
                    try:
                        await data["message"].edit_caption("⏹ **Playback ended**\n\nQueue is empty")
                    except Exception:
                        pass

            if chat_id in progress_tasks:
                progress_tasks[chat_id].cancel()
                progress_tasks.pop(chat_id, None)

            return

        # Play next track
        next_track = queues[chat_id].pop(0)
        next_track.started = time.time()

        await play_track(chat_id, next_track)
    except Exception as e:
        print(f"Error skipping track: {e}")


async def previous_track(chat_id: int):
    """Go to previous track"""
    try:
        data = active_chats.get(chat_id)
        if not data or not data.get("history"):
            return

        history = data["history"]
        if len(history) < 2:
            return

        # Remove current track
        history.pop()
        prev_track = history[-1]
        prev_track.started = time.time()

        await play_track(chat_id, prev_track)
    except Exception as e:
        print(f"Error going to previous track: {e}")


async def stream_end_handler(chat_id: int):
    """Handle stream end event - called from call.py"""
    try:
        await skip_current(chat_id)
    except Exception as e:
        print(f"Error in stream end handler: {e}")


@alone.on_message(filters.command("play"))
async def play_handler(_, message: Message):
    """Handle /play command"""
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/play song name` or `song URL`\n\nExample: `/play Blinding Lights The Weeknd`")

    query = " ".join(message.command[1:])
    processing = await message.reply_text("🔄 **Processing...**\n\nSearching for the song...")

    try:
        await ensure_assistant(bot, message.chat.id)

        requester = message.from_user.mention if message.from_user else "Anonymous"

        track = await build_track(query, requester)

        if message.chat.id in active_chats:
            queues.setdefault(message.chat.id, []).append(track)

            await processing.edit_text(
                f"✅ **Added to queue**\n\n"
                f"🎵 **{track.title}**\n"
                f"⏱️ Duration: {track.duration_text}\n"
                f"📍 Position: #{len(queues[message.chat.id])}"
            )
            return

        await play_track(message.chat.id, track)
        await processing.delete()

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await processing.edit_text(f"⏳ Flood wait: {e.value}s. Please try again.")
    except Exception as e:
        await processing.edit_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("pause"))
async def pause_handler(_, message: Message):
    """Handle /pause command"""
    try:
        if message.chat.id not in active_chats:
            return await message.reply_text("❌ Nothing is playing")

        await call_pause_stream(message.chat.id)
        active_chats[message.chat.id]["state"] = "Paused"
        await message.reply_text("⏸ **Playback paused**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("resume"))
async def resume_handler(_, message: Message):
    """Handle /resume command"""
    try:
        if message.chat.id not in active_chats:
            return await message.reply_text("❌ Nothing is playing")

        await call_resume_stream(message.chat.id)
        active_chats[message.chat.id]["state"] = "Playing"
        await message.reply_text("▶ **Playback resumed**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command(["stop", "end"]))
async def stop_handler(_, message: Message):
    """Handle /stop command"""
    try:
        if message.chat.id not in active_chats:
            return await message.reply_text("❌ Nothing is playing")

        queues.pop(message.chat.id, None)
        loop_states.pop(message.chat.id, None)
        shuffle_states.pop(message.chat.id, None)

        if message.chat.id in progress_tasks:
            progress_tasks[message.chat.id].cancel()
            progress_tasks.pop(message.chat.id, None)

        await leave_call(message.chat.id)

        if message.chat.id in active_chats:
            active_chats.pop(message.chat.id)

        await message.reply_text("⏹ **Playback stopped**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("skip"))
async def skip_handler(_, message: Message):
    """Handle /skip command"""
    try:
        if message.chat.id not in active_chats:
            return await message.reply_text("❌ Nothing is playing")

        await skip_current(message.chat.id)
        await message.reply_text("⏭ **Skipped to next track**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("previous"))
async def previous_handler(_, message: Message):
    """Handle /previous command"""
    try:
        if message.chat.id not in active_chats:
            return await message.reply_text("❌ Nothing is playing")

        await previous_track(message.chat.id)
        await message.reply_text("⏮ **Playing previous track**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("seek"))
async def seek_handler(_, message: Message):
    """Handle /seek command"""
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/seek seconds`\n\nExample: `/seek 30`")

    try:
        seconds = int(message.command[1])
        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("❌ Nothing is playing")

        track: Track = data["track"]
        elapsed = int(time.time() - track.started)
        new_time = elapsed + seconds

        if new_time >= track.duration:
            new_time = track.duration - 1
        elif new_time < 0:
            new_time = 0

        track.started = time.time() - new_time

        await message.reply_text(f"⏩ **Seeked to** `{seconds_to_time(new_time)}`")

    except ValueError:
        await message.reply_text("❌ Please provide a valid number")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("seekback"))
async def seekback_handler(_, message: Message):
    """Handle /seekback command"""
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/seekback seconds`\n\nExample: `/seekback 10`")

    try:
        seconds = int(message.command[1])
        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("❌ Nothing is playing")

        track: Track = data["track"]
        elapsed = int(time.time() - track.started)
        new_time = max(0, elapsed - seconds)

        track.started = time.time() - new_time

        await message.reply_text(f"⏪ **Seeked back to** `{seconds_to_time(new_time)}`")

    except ValueError:
        await message.reply_text("❌ Please provide a valid number")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("speed"))
async def speed_handler(_, message: Message):
    """Handle /speed command"""
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/speed number`\n\n**Range:** `0.5` to `3.0`\n\nExample: `/speed 1.5`")

    try:
        value = float(message.command[1])

        if value < 0.5 or value > 3.0:
            return await message.reply_text("❌ Speed must be between `0.5` and `3.0`")

        data = active_chats.get(message.chat.id)

        if not data:
            return await message.reply_text("❌ Nothing is playing")

        track: Track = data["track"]
        track.speed = value

        await message.reply_text(f"⚡ **Speed changed to** `{value}x`")

    except ValueError:
        await message.reply_text("❌ Please provide a valid decimal number")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("queue"))
async def queue_handler(_, message: Message):
    """Handle /queue command"""
    try:
        chat_id = message.chat.id
        queue = queues.get(chat_id, [])

        if not queue:
            return await message.reply_text("📭 **Queue is empty**\n\nUse `/play` to add songs")

        text = "🎶 **Queue List**\n\n"

        for idx, item in enumerate(queue[:20], start=1):
            text += f"`{idx:2d}.` **{item.title}** `[{item.duration_text}]`\n"

        if len(queue) > 20:
            text += f"\n... and `{len(queue) - 20}` more songs"

        await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("nowplaying"))
async def nowplaying_handler(_, message: Message):
    """Handle /nowplaying command"""
    try:
        chat_id = message.chat.id
        data = active_chats.get(chat_id)

        if not data:
            return await message.reply_text("❌ Nothing is playing")

        track = data["track"]
        elapsed = int(time.time() - track.started)

        text = (
            f"🎵 **Now Playing**\n\n"
            f"**Title:** `{track.title}`\n"
            f"**Duration:** `{track.duration_text}`\n"
            f"**Requested by:** `{track.requested_by}`\n"
            f"**Plays:** `{track.plays}`\n"
            f"**Speed:** `{track.speed}x`\n\n"
            f"{progress_bar(elapsed, track.duration)}\n"
            f"`{seconds_to_time(elapsed)} / {track.duration_text}`"
        )

        await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_message(filters.command("mstats"))
async def stats_handler(_, message: Message):
    """Handle /stats command"""
    try:
        chat_id = message.chat.id
        stats = user_stats.get(chat_id, {"total_plays": 0, "total_duration": 0})

        text = (
            f"📊 **Music Statistics**\n\n"
            f"**Total Plays:** `{stats['total_plays']}`\n"
            f"**Total Duration:** `{seconds_to_time(stats['total_duration'])}`\n"
            f"**Average Song:** `{seconds_to_time(stats['total_duration'] // max(1, stats['total_plays']))}`"
        )

        await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")


@alone.on_callback_query()
async def callbacks(_, query: CallbackQuery):
    """Handle callback queries"""
    chat_id = query.message.chat.id
    data = query.data

    try:
        if data == "pause":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            await call_pause_stream(chat_id)
            active_chats[chat_id]["state"] = "Paused"
            await query.answer("⏸ Paused")

        elif data == "resume":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            await call_resume_stream(chat_id)
            active_chats[chat_id]["state"] = "Playing"
            await query.answer("▶ Resumed")

        elif data == "stop":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            queues.pop(chat_id, None)
            if chat_id in progress_tasks:
                progress_tasks[chat_id].cancel()
                progress_tasks.pop(chat_id, None)
            await leave_call(chat_id)
            active_chats.pop(chat_id, None)
            await query.message.edit_caption("⏹ **Playback stopped**")
            await query.answer("⏹ Stopped")

        elif data == "skip":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            await skip_current(chat_id)
            await query.answer("⏭ Skipped")

        elif data == "previous":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            await previous_track(chat_id)
            await query.answer("⏮ Previous")

        elif data == "next":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            await skip_current(chat_id)
            await query.answer("⏭ Next")

        elif data == "loop":
            current = loop_states.get(chat_id, 0)
            next_state = (current + 1) % 3
            loop_states[chat_id] = next_state
            
            if next_state == 0:
                await query.answer("➡️ Loop OFF")
            elif next_state == 1:
                await query.answer("🔁 Loop All")
            else:
                await query.answer("🔂 Loop One")

        elif data == "shuffle":
            current = shuffle_states.get(chat_id, False)
            shuffle_states[chat_id] = not current
            await query.answer(f"🔀 Shuffle {'ON' if not current else 'OFF'}")

        elif data == "speed":
            await query.answer("Use /speed command to change speed", show_alert=True)

        elif data == "stats":
            stats = user_stats.get(chat_id, {"total_plays": 0, "total_duration": 0})
            text = (
                f"📊 **Music Statistics**\n\n"
                f"**Total Plays:** `{stats['total_plays']}`\n"
                f"**Total Duration:** `{seconds_to_time(stats['total_duration'])}`"
            )
            await query.answer(text, show_alert=True)

        elif data == "queue":
            queue = queues.get(chat_id, [])

            if not queue:
                return await query.answer("📭 Queue is empty", show_alert=True)

            text = "🎶 **Queue List**\n\n"

            for idx, item in enumerate(queue[:10], start=1):
                text += f"`{idx}.` {item.title}\n"

            if len(queue) > 10:
                text += f"\n... and `{len(queue) - 10}` more"

            await query.answer(text, show_alert=True)

        elif data == "nowplaying":
            if chat_id not in active_chats:
                return await query.answer("❌ Nothing is playing", show_alert=True)
            
            track = active_chats[chat_id]["track"]
            elapsed = int(time.time() - track.started)
            
            text = (
                f"🎵 **Now Playing**\n\n"
                f"**{track.title}**\n"
                f"`{seconds_to_time(elapsed)} / {track.duration_text}`"
            )
            await query.answer(text, show_alert=True)

        await send_player(chat_id)

    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)


async def cleanup_files():
    """Clean up temporary files"""
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
        except Exception as e:
            print(f"Error in cleanup: {e}")

        await asyncio.sleep(600)


async def startup():
    """Start the music bot"""
    try:
        await bot.start()
        
        # Start call system
        from AloneRobot.modules.call import start_call_system, stream_recovery_task
        await start_call_system()
        
        # Register stream end handler
        await register_stream_end_handler(stream_end_handler)
        
        asyncio.create_task(stream_recovery_task())
        asyncio.create_task(cleanup_files())

        print("🎵 Music system started successfully")
    except Exception as e:
        print(f"Error starting music system: {e}")

    await idle()


async def idle():
    """Keep the bot running"""
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(startup())

print("🎶 loaded snowy music ")
