import html
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ParseMode,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
)
from telegram.utils.helpers import mention_html

from AloneRobot import dispatcher

JOIN_REQ_STATUS = {} 


def approve(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    JOIN_REQ_STATUS[chat_id] = True

    update.effective_message.reply_text(
        "✅ ᴀᴘᴘʀᴏᴠᴀʟ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴs ᴇɴᴀʙʟᴇᴅ.\n"
        "ɪ ᴡɪʟʟ ɴᴏᴡ sᴇɴᴅ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ ᴀʟᴇʀᴛs."
    )


def disapprove(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    JOIN_REQ_STATUS[chat_id] = False

    update.effective_message.reply_text(
        "❌ ᴀᴘᴘʀᴏᴠᴀʟ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴs ᴅɪsᴀʙʟᴇᴅ.\n"
        "ɪ ᴡᴏɴ'ᴛ sᴇɴᴅ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ ᴀʟᴇʀᴛs."
    )


# =========================
# JOIN REQUEST MESSAGE
# =========================
def join_request(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if not JOIN_REQ_STATUS.get(chat_id, False):
        return

    req = update.chat_join_request
    user = req.from_user
    chat = req.chat

    name = html.escape(user.first_name)
    username = f"@{user.username}" if user.username else "ɴᴏɴᴇ"

    text = (
        "✨ ɴᴇᴡ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ ✨\n\n"
        f"👤 ɴᴀᴍᴇ → {name}\n"
        f"🔗 ᴜsᴇʀɴᴀᴍᴇ → {username}\n"
        f"🆔 ɪᴅ → <code>{user.id}</code>\n\n"
        "📩 ᴛʜɪs ᴜsᴇʀ sᴇɴᴛ ᴀ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ."
    )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ ᴀᴄᴄᴇᴘᴛ", callback_data=f"jr_accept_{user.id}"),
                InlineKeyboardButton("❌ ʀᴇᴊᴇᴄᴛ", callback_data=f"jr_reject_{user.id}"),
            ],
            [
                InlineKeyboardButton("🔒 ᴄʟᴏsᴇ", callback_data="jr_close"),
            ],
        ]
    )

    context.bot.send_message(
        chat_id=chat.id,
        text=text,
        reply_markup=buttons,
        parse_mode=ParseMode.HTML,
    )
    
def join_request_btn(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    chat = update.effective_chat

    try:
        if data.startswith("jr_accept_"):
            target_id = int(data.split("_")[-1])
            context.bot.approve_chat_join_request(chat.id, target_id)

            query.edit_message_text("✅ ᴜsᴇʀ ᴀᴘᴘʀᴏᴠᴇᴅ.")

        elif data.startswith("jr_reject_"):
            target_id = int(data.split("_")[-1])
            context.bot.decline_chat_join_request(chat.id, target_id)

            query.edit_message_text("❌ ᴜsᴇʀ ʀᴇᴊᴇᴄᴛᴇᴅ.")

        elif data == "jr_close":
            query.delete_message()

    except Exception:
        query.answer("error", show_alert=True)



from AloneRobot.modules.disable import DisableAbleCommandHandler

APPROVE = DisableAbleCommandHandler("approve", approve, run_async=True)
DISAPPROVE = DisableAbleCommandHandler("unapprove", disapprove, run_async=True)

JOIN_REQ_HANDLER = ChatJoinRequestHandler(join_request, run_async=True)
JOIN_REQ_BTN_HANDLER = CallbackQueryHandler(join_request_btn, pattern="^jr_")

dispatcher.add_handler(APPROVE)
dispatcher.add_handler(DISAPPROVE)
dispatcher.add_handler(JOIN_REQ_HANDLER)
dispatcher.add_handler(JOIN_REQ_BTN_HANDLER)


__mod_name__ = "Aᴘᴘʀᴏᴠᴇ"
__command_list__ = ["approve", "unapprove"]
__handlers__ = [APPROVE, DISAPPROVE, JOIN_REQ_HANDLER, JOIN_REQ_BTN_HANDLER]


__help__ = """
✨ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ ᴀᴘᴘʀᴏᴠᴀʟ sʏsᴛᴇᴍ ✨

ᴀɴʏ ᴀᴅᴍɪɴ ᴏʀ ɢʀᴏᴜᴘ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜsᴇ:

❍ /approve on/off → ᴇɴᴀʙʟᴇ/ᴅɪsᴀʙʟᴇ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴs  
❍ /unapprove → ᴅɪsᴀʙʟᴇ 

ᴡʜᴇɴ ᴇɴᴀʙʟᴇᴅ, ʙᴏᴛ ᴡɪʟʟ sᴇɴᴅ ᴀʟᴇʀᴛs ᴡɪᴛʜ:
• ᴜsᴇʀ ɪɴғᴏ  
• ᴀᴄᴄᴇᴘᴛ / ʀᴇᴊᴇᴄᴛ ʙᴜᴛᴛᴏɴs  
• ᴄʟᴏsᴇ ᴏᴘᴛɪᴏɴ  
"""
