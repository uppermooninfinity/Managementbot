"""
PyTgCalls Management Module
Handles all group call operations, event handlers, and state management
"""

import asyncio
import time
from typing import Callable, Dict, List, Optional

from pyrogram import Client
from pyrogram.errors import UserAlreadyParticipant

from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.stream import StreamAudioEnded

from AloneRobot.config import API_ID, API_HASH, STRING_SESSION

# ============ PyTgCalls Client Setup ============

assistant = Client(
    "AloneRobotAssistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

call_py = PyTgCalls(assistant)

# ============ Global State Management ============

active_chats: Dict[int, dict] = {}
queues: Dict[int, List] = {}
loop_states: Dict[int, int] = {}  # 0: no loop, 1: loop all, 2: loop one
progress_tasks: Dict[int, asyncio.Task] = {}
shuffle_states: Dict[int, bool] = {}
user_stats: Dict[int, dict] = {}  # Track user listening stats

# ============ Event Handlers Registry ============

stream_end_handlers: List[Callable] = []


# ============ Event Handler Functions ============

async def register_stream_end_handler(handler: Callable):
    """Register a callback for stream end events"""
    stream_end_handlers.append(handler)
    print(f"✅ Stream end handler registered: {handler.__name__}")


async def on_stream_end(update: StreamAudioEnded):
    """Handle stream end event"""
    chat_id = update.chat_id
    print(f"🎵 Stream ended in chat: {chat_id}")
    
    # Call all registered handlers
    for handler in stream_end_handlers:
        try:
            await handler(chat_id)
        except Exception as e:
            print(f"❌ Error in stream handler: {e}")


# ============ Call Management Functions ============

async def ensure_assistant(bot: Client, chat_id: int):
    """Ensure assistant bot is in the chat"""
    try:
        invite = await bot.export_chat_invite_link(chat_id)
        try:
            await assistant.join_chat(invite)
        except UserAlreadyParticipant:
            pass
        except Exception:
            pass
    except Exception as e:
        print(f"Error ensuring assistant: {e}")
        pass


async def play_audio(chat_id: int, stream_url: str, volume: int = 100) -> bool:
    """
    Play audio in a voice chat
    
    Args:
        chat_id: Target chat ID
        stream_url: Audio stream URL
        volume: Volume level (0-200)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        await call_py.play(chat_id, stream_url, volume=volume)
        return True
    except Exception as e:
        print(f"❌ Error playing audio: {e}")
        try:
            # Try alternative method
            await call_py.play(chat_id, stream_url)
            return True
        except Exception as alt_error:
            print(f"❌ Alternative play method failed: {alt_error}")
            return False


async def pause_stream(chat_id: int):
    """Pause playback in a chat"""
    try:
        await call_py.pause_stream(chat_id)
    except Exception as e:
        print(f"Error pausing stream: {e}")
        raise


async def resume_stream(chat_id: int):
    """Resume playback in a chat"""
    try:
        await call_py.resume_stream(chat_id)
    except Exception as e:
        print(f"Error resuming stream: {e}")
        raise


async def leave_call(chat_id: int):
    """Leave a voice chat"""
    try:
        await call_py.leave_call(chat_id)
        print(f"✅ Left call in chat {chat_id}")
    except Exception as e:
        print(f"⚠️ Error leaving call: {e}")


async def get_call_info(chat_id: int):
    """Get current call information"""
    try:
        return await call_py.get_call(chat_id)
    except Exception as e:
        print(f"Error getting call info: {e}")
        return None


# ============ Background Tasks ============

async def stream_recovery_task():
    """Recover from stream disconnections"""
    while True:
        try:
            for chat_id, data in list(active_chats.items()):
                try:
                    await get_call_info(chat_id)
                except Exception:
                    # Try to reconnect
                    print(f"🔄 Attempting to recover stream in chat {chat_id}")
                    try:
                        track = data.get("track")
                        if track:
                            await play_audio(chat_id, track.stream_url)
                    except Exception as recovery_error:
                        print(f"❌ Recovery failed for chat {chat_id}: {recovery_error}")
        except Exception as e:
            print(f"Error in stream recovery: {e}")

        await asyncio.sleep(30)


async def cleanup_temp_files():
    """Clean up temporary files periodically"""
    import os
    import tempfile
    
    while True:
        try:
            temp_dir = tempfile.gettempdir()

            for file in os.listdir(temp_dir):
                if file.startswith(("thumb_", "final_")) or file.endswith(".raw"):
                    path = os.path.join(temp_dir, file)

                    try:
                        if time.time() - os.path.getmtime(path) > 3600:  # 1 hour
                            os.remove(path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error in cleanup: {e}")

        await asyncio.sleep(600)  # Every 10 minutes


# ============ Startup/Shutdown Functions ============

async def start_call_system():
    """Initialize the call system"""
    try:
        print("🎵 Starting call system...")
        await assistant.start()
        await call_py.start()
        
        # Register the stream end handler
        call_py.on_stream_end()(on_stream_end)
        
        print("✅ Call system started successfully")
    except Exception as e:
        print(f"❌ Error starting call system: {e}")
        raise


async def stop_call_system():
    """Gracefully shutdown the call system"""
    try:
        print("🛑 Stopping call system...")
        
        # Leave all active calls
        for chat_id in list(active_chats.keys()):
            try:
                await leave_call(chat_id)
            except Exception:
                pass
        
        # Stop the assistant
        await assistant.stop()
        
        print("✅ Call system stopped")
    except Exception as e:
        print(f"❌ Error stopping call system: {e}")


# ============ Utility Functions ============

def get_active_chats() -> List[int]:
    """Get list of active chat IDs"""
    return list(active_chats.keys())


def get_queue_count(chat_id: int) -> int:
    """Get number of songs in queue"""
    return len(queues.get(chat_id, []))


def get_current_track(chat_id: int):
    """Get currently playing track"""
    data = active_chats.get(chat_id)
    if data:
        return data.get("track")
    return None


def is_playing(chat_id: int) -> bool:
    """Check if music is currently playing"""
    return chat_id in active_chats


def get_player_state(chat_id: int) -> Optional[str]:
    """Get current player state (Playing, Paused, etc)"""
    data = active_chats.get(chat_id)
    if data:
        return data.get("state")
    return None
