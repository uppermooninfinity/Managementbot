import html
from typing import Optional

from telegram import (
    Chat,
    ChatPermissions,
    Message,
    Update,
    User,
)
from telegram.error import BadRequest
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
)
from telegram.utils.helpers import mention_html

from AloneRobot import TIGERS, WOLVES, dispatcher
from AloneRobot.modules.helper_funcs.alternate import send_message
from AloneRobot.modules.helper_funcs.chat_status import (
    bot_admin,
    is_user_admin,
    user_admin,
)
from AloneRobot.modules.log_channel import loggable
from AloneRobot.modules.sql import antiflood_sql as sql
from AloneRobot.modules.sql.approve_sql import is_approved

FLOOD_GROUP = 3

# =========================================================
# ғʟᴏᴏᴅ sᴛᴀᴛs
# =========================================================

FLOOD_STATS = {}


# =========================================================
# ᴄʜᴇᴄᴋ ғʟᴏᴏᴅ
# =========================================================

@loggable
def check_flood(update: Update, context: CallbackContext) -> str:

    user: Optional[User] = update.effective_user
    chat: Optional[Chat] = update.effective_chat
    msg: Optional[Message] = update.effective_message

    if not user or not chat or not msg:
        return ""

    # ɪɢɴᴏʀᴇ ᴀᴅᴍɪɴs / sᴜᴅᴏ
    if (
        is_user_admin(chat, user.id)
        or user.id in TIGERS
        or user.id in WOLVES
    ):
        sql.update_flood(chat.id, None)
        return ""

    # ɪɢɴᴏʀᴇ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs
    if is_approved(chat.id, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_action = sql.update_flood(chat.id, user.id)

    if not should_action:
        return ""

    try:

        if chat.id not in FLOOD_STATS:
            FLOOD_STATS[chat.id] = {
                "muted": 0,
                "banned": 0,
                "kicked": 0,
            }

        mode, value = sql.get_flood_setting(chat.id)

        # ʙᴀɴ
        if mode == 1:

            chat.ban_member(user.id)

            FLOOD_STATS[chat.id]["banned"] += 1

            msg.reply_text(
                f"ʙᴇᴇᴘ ʙᴏᴏᴘ !\n\n"
                f"{mention_html(user.id, html.escape(user.first_name))} "
                f"ɢᴏᴛ ʙᴀɴɴᴇᴅ ғᴏʀ ғʟᴏᴏᴅɪɴɢ.",
                parse_mode="HTML",
            )

        # ᴋɪᴄᴋ
        elif mode == 2:

            chat.ban_member(user.id)
            chat.unban_member(user.id)

            FLOOD_STATS[chat.id]["kicked"] += 1

            msg.reply_text(
                f"ʙᴇᴇᴘ ʙᴏᴏᴘ !\n\n"
                f"{mention_html(user.id, html.escape(user.first_name))} "
                f"ɢᴏᴛ ᴋɪᴄᴋᴇᴅ ғᴏʀ ғʟᴏᴏᴅɪɴɢ.",
                parse_mode="HTML",
            )

        # ᴍᴜᴛᴇ
        else:

            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=False
                ),
            )

            FLOOD_STATS[chat.id]["muted"] += 1

            msg.reply_text(
                f"ʙᴇᴇᴘ ʙᴏᴏᴘ !\n\n"
                f"{mention_html(user.id, html.escape(user.first_name))} "
                f"ɢᴏᴛ ᴍᴜᴛᴇᴅ ғᴏʀ ғʟᴏᴏᴅɪɴɢ.",
                parse_mode="HTML",
            )

        return ""

    except BadRequest:

        msg.reply_text(
            "ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs.\n"
            "ᴀɴᴛɪғʟᴏᴏᴅ ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ."
        )

        sql.set_flood(chat.id, 0)

        return ""


# =========================================================
# /ᴀɴᴛɪғʟᴏᴏᴅ
# =========================================================

@user_admin
@bot_admin
def antiflood(update: Update, context: CallbackContext):

    chat = update.effective_chat
    msg = update.effective_message
    args = context.args

    # =====================================================
    # ɴᴏ ᴀʀɢs
    # =====================================================

    if not args:

        msg.reply_text(
            "❍ ᴀɴᴛɪғʟᴏᴏᴅ ᴄᴏᴍᴍᴀɴᴅs\n\n"
            "◈ /antiflood on\n"
            "ᴇɴᴀʙʟᴇ ᴀɴᴛɪғʟᴏᴏᴅ\n\n"
            "◈ /antiflood off\n"
            "ᴅɪsᴀʙʟᴇ ᴀɴᴛɪғʟᴏᴏᴅ\n\n"
            "◈ /antiflood status\n"
            "ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛs\n\n"
            "◈ /floodfreq 10\n"
            "sᴇᴛ ғʟᴏᴏᴅ ʟɪᴍɪᴛ"
        )

        return

    action = args[0].lower()

    # =====================================================
    # ᴏɴ
    # =====================================================

    if action == "on":

        current = sql.get_flood_limit(chat.id)

        if current == 0:
            sql.set_flood(chat.id, 10)

        msg.reply_text(
            "ᴀɴᴛɪғʟᴏᴏᴅ ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.\n"
            "ᴄᴜʀʀᴇɴᴛ ʟɪᴍɪᴛ ➠ 10"
        )

    # =====================================================
    # ᴏғғ
    # =====================================================

    elif action == "off":

        sql.set_flood(chat.id, 0)

        msg.reply_text(
            "ᴀɴᴛɪғʟᴏᴏᴅ ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ."
        )

    # =====================================================
    # sᴛᴀᴛᴜs
    # =====================================================

    elif action == "status":

        limit = sql.get_flood_limit(chat.id)

        mode, value = sql.get_flood_setting(chat.id)

        if limit == 0:
            status = "ᴅɪsᴀʙʟᴇᴅ"
        else:
            status = "ᴇɴᴀʙʟᴇᴅ"

        mode_name = {
            1: "ʙᴀɴ",
            2: "ᴋɪᴄᴋ",
            3: "ᴍᴜᴛᴇ",
            4: "ᴛʙᴀɴ",
            5: "ᴛᴍᴜᴛᴇ",
        }.get(mode, "ᴍᴜᴛᴇ")

        stats = FLOOD_STATS.get(
            chat.id,
            {
                "muted": 0,
                "banned": 0,
                "kicked": 0,
            },
        )

        msg.reply_text(
            "❍ ᴀɴᴛɪғʟᴏᴏᴅ sᴛᴀᴛᴜs\n\n"
            f"◈ sᴛᴀᴛᴇ ➠ {status}\n"
            f"◈ ғʟᴏᴏᴅ ʟɪᴍɪᴛ ➠ {limit}\n"
            f"◈ ᴀᴄᴛɪᴏɴ ᴍᴏᴅᴇ ➠ {mode_name}\n\n"
            "❍ ʙᴏᴛ ᴀᴄᴛɪᴏɴ sᴛᴀᴛs\n\n"
            f"◈ ᴍᴜᴛᴇᴅ ➠ {stats['muted']}\n"
            f"◈ ʙᴀɴɴᴇᴅ ➠ {stats['banned']}\n"
            f"◈ ᴋɪᴄᴋᴇᴅ ➠ {stats['kicked']}"
        )

    # =====================================================
    # ɪɴᴠᴀʟɪᴅ
    # =====================================================

    else:

        msg.reply_text(
            "ɪɴᴠᴀʟɪᴅ ᴏᴘᴛɪᴏɴ.\n\n"
            "ᴜsᴇ ➠ on / off / status"
        )


# =========================================================
# /ғʟᴏᴏᴅғʀᴇǫ
# =========================================================

@user_admin
def floodfreq(update: Update, context: CallbackContext):

    chat = update.effective_chat
    msg = update.effective_message
    args = context.args

    if not args:

        limit = sql.get_flood_limit(chat.id)

        msg.reply_text(
            f"ᴄᴜʀʀᴇɴᴛ ғʟᴏᴏᴅ ʟɪᴍɪᴛ ➠ {limit}"
        )

        return

    if not args[0].isdigit():

        msg.reply_text(
            "ᴘʟᴇᴀsᴇ ɢɪᴠᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ."
        )

        return

    limit = int(args[0])

    if limit < 4:

        msg.reply_text(
            "ғʟᴏᴏᴅ ʟɪᴍɪᴛ ᴍᴜsᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ 3."
        )

        return

    sql.set_flood(chat.id, limit)

    msg.reply_text(
        f"ғʟᴏᴏᴅ ʟɪᴍɪᴛ sᴇᴛ ᴛᴏ ➠ {limit}"
    )


# =========================================================
# ᴄʜᴀᴛ sᴇᴛᴛɪɴɢs
# =========================================================

def __chat_settings__(chat_id, user_id):

    limit = sql.get_flood_limit(chat_id)

    return f"ᴀɴᴛɪғʟᴏᴏᴅ ʟɪᴍɪᴛ ➠ {limit}"


# =========================================================
# ʜᴇʟᴘ
# =========================================================

__help__ = """
❍ ᴀɴᴛɪғʟᴏᴏᴅ ᴄᴏᴍᴍᴀɴᴅs

◈ /antiflood on
ᴇɴᴀʙʟᴇ ᴀɴᴛɪғʟᴏᴏᴅ

◈ /antiflood off
ᴅɪsᴀʙʟᴇ ᴀɴᴛɪғʟᴏᴏᴅ

◈ /antiflood status
ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛs

◈ /floodfreq 10
sᴇᴛ ғʟᴏᴏᴅ ʟɪᴍɪᴛ
"""

__mod_name__ = "ᴀɴᴛɪғʟᴏᴏᴅ"


# =========================================================
# ʜᴀɴᴅʟᴇʀs
# =========================================================

CHECK_FLOOD_HANDLER = MessageHandler(
    Filters.all & ~Filters.status_update & Filters.chat_type.groups,
    check_flood,
    run_async=True,
)

ANTIFLOOD_HANDLER = CommandHandler(
    "antiflood",
    antiflood,
    filters=Filters.chat_type.groups,
    run_async=True,
)

FLOODFREQ_HANDLER = CommandHandler(
    "floodfreq",
    floodfreq,
    filters=Filters.chat_type.groups,
    run_async=True,
)

dispatcher.add_handler(CHECK_FLOOD_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(ANTIFLOOD_HANDLER)
dispatcher.add_handler(FLOODFREQ_HANDLER)

__handlers__ = [
    (CHECK_FLOOD_HANDLER, FLOOD_GROUP),
    ANTIFLOOD_HANDLER,
    FLOODFREQ_HANDLER,
            ]
