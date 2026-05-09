from math import ceil
from typing import Dict, List
from uuid import uuid4
from functools import wraps

from telegram import (
    MAX_MESSAGE_LENGTH,
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ParseMode,
    Update,
)
from telegram.error import TelegramError

from AloneRobot import NO_LOAD, OWNER_ID


class EqInlineKeyboardButton(InlineKeyboardButton):
    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __gt__(self, other):
        return self.text > other.text


def split_message(msg: str) -> List[str]:
    if len(msg) < MAX_MESSAGE_LENGTH:
        return [msg]

    lines = msg.splitlines(True)
    small_msg = ""
    result = []

    for line in lines:
        if len(small_msg) + len(line) < MAX_MESSAGE_LENGTH:
            small_msg += line
        else:
            result.append(small_msg)
            small_msg = line
    else:
        result.append(small_msg)

    return result


# =========================
# 3x3 MODULE GRID PAGINATION
# =========================
def paginate_modules(page_n: int, module_dict: Dict, prefix, chat=None) -> List:
    if not chat:
        modules = sorted(
            [
                EqInlineKeyboardButton(
                    x.__mod_name__,
                    callback_data=f"{prefix}_module({x.__mod_name__.lower()})",
                )
                for x in module_dict.values()
            ]
        )
    else:
        modules = sorted(
            [
                EqInlineKeyboardButton(
                    x.__mod_name__,
                    callback_data=f"{prefix}_module({chat},{x.__mod_name__.lower()})",
                )
                for x in module_dict.values()
            ]
        )

    # 3 buttons per row
    pairs = [modules[i:i + 3] for i in range(0, len(modules), 3)]

    # 3 rows per page = 9 buttons
    max_num_pages = ceil(len(pairs) / 3)

    if max_num_pages == 0:
        max_num_pages = 1

    modulo_page = page_n % max_num_pages

    pairs = pairs[modulo_page * 3 : (modulo_page + 1) * 3]

    # Navigation buttons
    if max_num_pages > 1:
        pairs.append(
            [
                EqInlineKeyboardButton(
                    "◁",
                    callback_data=f"{prefix}_prev({modulo_page})",
                ),
                EqInlineKeyboardButton(
                    "• ʜᴏᴍᴇ •",
                    callback_data="alone_back",
                ),
                EqInlineKeyboardButton(
                    "▷",
                    callback_data=f"{prefix}_next({modulo_page})",
                ),
            ]
        )
    else:
        pairs.append(
            [
                EqInlineKeyboardButton(
                    "• ʙᴀᴄᴋ •",
                    callback_data="alone_back",
                )
            ]
        )

    return pairs


def article(
    title: str = "",
    description: str = "",
    message_text: str = "",
    thumb_url: str = None,
    reply_markup: InlineKeyboardMarkup = None,
    disable_web_page_preview: bool = False,
) -> InlineQueryResultArticle:

    return InlineQueryResultArticle(
        id=uuid4(),
        title=title,
        description=description,
        thumb_url=thumb_url,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            disable_web_page_preview=disable_web_page_preview,
        ),
        reply_markup=reply_markup,
    )


def send_to_list(
    bot: Bot, send_to: list, message: str, markdown=False, html=False
) -> None:
    if html and markdown:
        raise Exception("Can only send with either markdown or HTML!")

    for user_id in set(send_to):
        try:
            if markdown:
                bot.send_message(
                    user_id,
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif html:
                bot.send_message(
                    user_id,
                    message,
                    parse_mode=ParseMode.HTML,
                )
            else:
                bot.send_message(user_id, message)

        except TelegramError:
            pass


def build_keyboard(buttons):
    keyb = []

    for btn in buttons:
        if btn.same_line and keyb:
            keyb[-1].append(
                InlineKeyboardButton(
                    btn.name,
                    url=btn.url,
                )
            )
        else:
            keyb.append(
                [
                    InlineKeyboardButton(
                        btn.name,
                        url=btn.url,
                    )
                ]
            )

    return keyb


def revert_buttons(buttons):
    res = ""

    for btn in buttons:
        if btn.same_line:
            res += "\n[{}](buttonurl://{}:same)".format(
                btn.name,
                btn.url,
            )
        else:
            res += "\n[{}](buttonurl://{})".format(
                btn.name,
                btn.url,
            )

    return res


def build_keyboard_parser(bot, chat_id, buttons):
    keyb = []

    for btn in buttons:
        if btn.url == "{rules}":
            btn.url = "http://t.me/{}?start={}".format(
                bot.username,
                chat_id,
            )

        if btn.same_line and keyb:
            keyb[-1].append(
                InlineKeyboardButton(
                    btn.name,
                    url=btn.url,
                )
            )
        else:
            keyb.append(
                [
                    InlineKeyboardButton(
                        btn.name,
                        url=btn.url,
                    )
                ]
            )

    return keyb


def user_bot_owner(func):
    @wraps(func)
    def is_user_bot_owner(bot: Bot, update: Update, *args, **kwargs):
        user = update.effective_user

        if user and user.id == OWNER_ID:
            return func(bot, update, *args, **kwargs)

    return is_user_bot_owner


def build_keyboard_alternate(buttons):
    keyb = []

    for btn in buttons:
        if btn[2] and keyb:
            keyb[-1].append(
                InlineKeyboardButton(
                    btn[0],
                    url=btn[1],
                )
            )
        else:
            keyb.append(
                [
                    InlineKeyboardButton(
                        btn[0],
                        url=btn[1],
                    )
                ]
            )

    return keyb


def is_module_loaded(name):
    return name not in NO_LOAD
