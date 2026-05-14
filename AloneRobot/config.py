from pyrogram import filters

class Config(object):
    LOGGER = True
    # REQUIRED
    # Login to https://my.telegram.org and fill in these slots with the details given by it

    API_ID = 37467897  # integer value, dont use ""
    API_HASH = "b1c9ba3d6180a099e35d6498d8434bf0"
    TOKEN = ""  # This var used to be API_KEY but it is now TOKEN, adjust accordingly.
    OWNER_ID = 8364692780 # If you dont know, run the bot and do /id in your private chat with it, also an integer
    
    SUPPORT_CHAT = "theinfinfinity_support"  # Your own group for support, do not add the @
    START_IMG = "https://graph.org/file/5bf10b670c93c624af3e0-6d476603a36e8052b0.jpg"
    EVENT_LOGS = (-1003882647583)  # Prints information like gbans, sudo promotes, AI enabled disable states that may help in debugging and shit
    MONGO_DB_URI= "mongodb+srv://knight4563:knight4563@cluster0.a5br0se.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    # RECOMMENDED
    DATABASE_URL = ""  # A sql database url from elephantsql.com
    CASH_API_KEY = (
        ""  # Get your API key from https://www.alphavantage.co/support/#api-key
    )
    STRING_SESSION = ""
    TIME_API_KEY = ""
    # Get your API key from https://timezonedb.com/api

    # Optional fields
    CHATBOT_API="" # get it from @FallenChat_Bot using /token
    BL_CHATS = []  # List of groups that you want blacklisted.
    DRAGONS = [7487670897,8409591285]  # User id of sudo users
    DEV_USERS = [7487670897,8409591285]  # User id of dev users
    DEMONS = [7487670897,8409591285]  # User id of support users
    TIGERS = [7487670897,8409591285]  # User id of tiger users
    WOLVES = [7487670897,8409591285]  # User id of whitelist users

    ALLOW_CHATS = True
    ALLOW_EXCL = True
    DEL_CMDS = True
    INFOPIC = True
    LOAD = []
    NO_LOAD = []
    STRICT_GBAN = True
    TEMP_DOWNLOAD_DIRECTORY = "./"
    WORKERS = 8
    

# Module-level exports for direct imports
API_ID = Config.API_ID
API_HASH = Config.API_HASH
TOKEN = Config.TOKEN
STRING_SESSION = Config.STRING_SESSION
OWNER_ID = Config.OWNER_ID

BANNED_USERS = filters.user()

class Production(Config):
    LOGGER = True


class Development(Config):
    LOGGER = True
