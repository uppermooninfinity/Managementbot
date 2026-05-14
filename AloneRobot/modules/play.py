import asyncio
import aiohttp
import os
import time
import math
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, InputMediaPhoto
from pyrogram.errors import FloodWait, UserAlreadyParticipant

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped, AudioQuality
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

call = PyTgCalls(assistant)

active: Dict[int, dict] = {}
queue: Dict[int, List] = {}
loop: Dict[int, bool] = {}
tasks: Dict[int, asyncio.Task] = {}


@dataclass
class Track:
    title: str
    video_id: str
    duration: int
    duration_text: str
    requester: str
    stream: str
    token: str
    thumb: str
    started: float = field(default_factory=time.time)


def to_sec(t):
    try:
        p = list(map(int, t.split(":")))
        if len(p) == 2:
            return p[0] * 60 + p[1]
        return p[0] * 3600 + p[1] * 60 + p[2]
    except:
        return 0


def fmt(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def bar(c, t):
    if t <= 0:
        return "◉──────────"
    p = c / t
    f = int(p * 10)
    return "─" * f + "◉" + "─" * (10 - f)


async def yt(query):
    r = await VideosSearch(query, limit=1).next()
    if not r.get("result"):
        return None
    d = r["result"][0]
    return {
        "title": d["title"],
        "video_id": d["id"],
        "duration": to_sec(d.get("duration", "0:00")),
        "duration_text": d.get("duration", "0:00"),
        "thumb": d["thumbnails"][0]["url"],
    }


async def token(video_id):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_BASE}/download", params={"url": video_id, "type": "audio"}) as r:
            return (await r.json())["download_token"]


async def stream(video_id):
    return f"{API_BASE}/stream/{video_id}?type=audio"


async def build(q, user):
    s = await yt(q)
    if not s:
        raise Exception("Not found")
    t = await token(s["video_id"])
    return Track(
        title=s["title"],
        video_id=s["video_id"],
        duration=s["duration"],
        duration_text=s["duration_text"],
        requester=user,
        stream=await stream(s["video_id"]),
        token=t,
        thumb=s["thumb"],
    )


async def thumb(track: Track):
    async with aiohttp.ClientSession() as s:
        async with s.get(track.thumb) as r:
            img = await r.read()

    p = os.path.join(tempfile.gettempdir(), f"{track.video_id}.jpg")
    with open(p, "wb") as f:
        f.write(img)

    im = Image.open(p).convert("RGB").resize((1280, 720))
    dr = ImageDraw.Draw(im)

    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()

    dr.text((40, 500), track.title[:45], fill="white", font=font)
    dr.text((40, 560), f"Duration: {track.duration_text}", fill="white")
    dr.text((40, 610), f"By: {track.requester}", fill="white")

    out = os.path.join(tempfile.gettempdir(), f"out_{track.video_id}.jpg")
    im.save(out)
    return out


def buttons():
    return InlineKeyboardMarkup([
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
        [InlineKeyboardButton("➕ Queue", callback_data="queue")]
    ])


async def caption(chat_id):
    d = active.get(chat_id)
    if not d:
        return "Nothing playing"
    tr = d["track"]
    el = int(time.time() - tr.started)
    return (
        f"🎵 Now Playing\n\n"
        f"{tr.title}\n"
        f"{tr.duration_text}\n"
        f"{tr.requester}\n\n"
        f"{bar(el, tr.duration)}\n"
        f"{fmt(el)} / {tr.duration_text}"
    )


async def play(chat_id, track):
    st = AudioPiped(track.stream, AudioQuality.HIGH)
    await call.play(chat_id, st)

    active[chat_id] = {"track": track, "state": "playing"}

    if chat_id in tasks:
        tasks[chat_id].cancel()

    async def upd():
        while chat_id in active:
            try:
                tr = active[chat_id]["track"]
                img = await thumb(tr)
                cap = await caption(chat_id)
                await bot.send_photo(chat_id, img, caption=cap, reply_markup=buttons())
            except:
                pass
            await asyncio.sleep(10)

    tasks[chat_id] = asyncio.create_task(upd())


async def skip(chat_id):
    if queue.get(chat_id):
        nxt = queue[chat_id].pop(0)
        await play(chat_id, nxt)
    else:
        await call.leave_call(chat_id)
        active.pop(chat_id, None)


@bot.on_message(filters.command("play"))
async def p(_, m: Message):
    q = " ".join(m.command[1:])
    msg = await m.reply("loading")
    try:
        tr = await build(q, m.from_user.mention)
        if m.chat.id in active:
            queue.setdefault(m.chat.id, []).append(tr)
            return await msg.edit("queued")
        await play(m.chat.id, tr)
        await msg.delete()
    except Exception as e:
        await msg.edit(str(e))


@bot.on_message(filters.command("pause"))
async def pause(_, m):
    await call.pause_stream(m.chat.id)


@bot.on_message(filters.command("resume"))
async def resume(_, m):
    await call.resume_stream(m.chat.id)


@bot.on_message(filters.command("stop"))
async def stop(_, m):
    await call.leave_call(m.chat.id)
    active.pop(m.chat.id, None)


@bot.on_message(filters.command("skip"))
async def sk(_, m):
    await skip(m.chat.id)


@bot.on_callback_query()
async def cb(_, q: CallbackQuery):
    c = q.message.chat.id

    if q.data == "pause":
        await call.pause_stream(c)
    elif q.data == "resume":
        await call.resume_stream(c)
    elif q.data == "stop":
        await call.leave_call(c)
        active.pop(c, None)
    elif q.data == "skip":
        await skip(c)
    elif q.data == "loop":
        loop[c] = not loop.get(c, False)
    elif q.data == "queue":
        qlist = queue.get(c, [])
        text = "\n".join([x.title for x in qlist[:10]]) or "empty"
        await q.message.reply(text)

    await q.answer()


@call.on_stream_end()
async def end(_, u: StreamAudioEnded):
    await skip(u.chat_id)


async def main():
    await bot.start()
    await assistant.start()
    await call.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
