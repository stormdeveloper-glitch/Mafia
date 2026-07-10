# advanced_secret_mafia_bot.py
# PRODUCTION READY – SINGLE FILE VERSION

import asyncio
import os
import random
import logging
import boto3
from botocore.client import Config
from collections import defaultdict
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()

# ================== LOGGING ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== CONFIG ==================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "bot tokeningiz")
ADMIN_ID = int(os.environ.get("ADMIN_ID") or 6151329850)

DAY_IMAGE_URL = os.environ.get("DAY_IMAGE_URL", "https://t.me/c/3348020476/3")
NIGHT_IMAGE_URL = os.environ.get("NIGHT_IMAGE_URL", "https://t.me/c/3348020476/4")

def get_presigned_url(object_name, expiration=3600):
    s3_endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT")
    s3_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    s3_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("AWS_BUCKET_NAME")

    if not all([s3_endpoint, s3_access_key, s3_secret_key, bucket_name]):
        if object_name == "day.gif":
            return DAY_IMAGE_URL
        return NIGHT_IMAGE_URL

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
            config=Config(signature_version='s3v4')
        )
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"S3 presigned URL generation error for {object_name}: {e}")
        if object_name == "day.gif":
            return DAY_IMAGE_URL
        return NIGHT_IMAGE_URL

REGISTRATION_TIME = 120
NIGHT_DURATION = 120
DAY_DURATION = 120
VOTING_DURATION = 60

WIN_REWARD = 60

PRICES = {
    "shield": 20,
    "documents": 15,
    "active_role": 25,
}

# ================== LANGUAGE ==================

LANGUAGES = {
    "uz": {
        "need_admin": "❗ Bot guruhda ADMIN bo‘lishi shart!",
        "make_admin": "📌 Botni admin qiling va qayta urinib ko‘ring.",
        "reg_started": "📝 Ro‘yxatdan o‘tish boshlandi",
        "joined": "✅ Siz o‘yinga qo‘shildingiz",
        "already_joined": "⚠️ Siz allaqachon qo‘shilgansiz",
        "night": "🌙 Kecha boshlandi\n🤫 Shahar uxlayapti...",
        "day": "☀️ Tong otdi\n💬 Endi bahslashish mumkin",
        "vote_used": "⚠️ Siz allaqachon ovoz bergansiz",
        "shop_blocked": "⛔ O‘yin davomida shop yopiq!",
        "not_enough_money": "❌ Pul yetarli emas",
        "gift_sent": "🎁 Sovg‘a yuborildi",
        "lang_set": "✅ Til o‘zgartirildi",
    },
    "ru": {
        "need_admin": "❗ Бот должен быть администратором!",
        "make_admin": "📌 Сделайте бота администратором и попробуйте снова.",
        "reg_started": "📝 Регистрация началась",
        "joined": "✅ Вы присоединились",
        "already_joined": "⚠️ Вы уже в игре",
        "night": "🌙 Ночь наступила\n🤫 Город спит...",
        "day": "☀️ Утро наступило\n💬 Можно обсуждать",
        "vote_used": "⚠️ Вы уже голосовали",
        "shop_blocked": "⛔ Магазин закрыт!",
        "not_enough_money": "❌ Недостаточно средств",
        "gift_sent": "🎁 Подарок отправлен",
        "lang_set": "✅ Язык изменён",
    },
    "en": {
        "need_admin": "❗ Bot must be an admin!",
        "make_admin": "📌 Make the bot admin and try again.",
        "reg_started": "📝 Registration started",
        "joined": "✅ You joined the game",
        "already_joined": "⚠️ You already joined",
        "night": "🌙 Night started\n🤫 City sleeps...",
        "day": "☀️ Morning started\n💬 Discussion allowed",
        "vote_used": "⚠️ You already voted",
        "shop_blocked": "⛔ Shop is closed!",
        "not_enough_money": "❌ Not enough money",
        "gift_sent": "🎁 Gift sent",
        "lang_set": "✅ Language updated",
    },
}

USER_LANG = {}
def t(uid, key):
    return LANGUAGES.get(USER_LANG.get(uid, "uz"), LANGUAGES["uz"]).get(key, key)

# ================== DATA ==================

class Player:
    def __init__(self, uid, name):
        self.id = uid
        self.name = name
        self.alive = True
        self.role = None
        self.shield = 0

class Game:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.state = "registration"
        self.players = {}
        self.reg_msg_id = None
        self.used_night = set()
        self.night_actions = []
        self.private_votes = {}
        self.public_votes = {"like": set(), "dislike": set()}

games = {}
USER_DATA = defaultdict(lambda: {
    "money": 0,
    "shield": 0,
    "documents": 0,
    "active_role": 0
})

# ================== HELPERS ==================

async def is_bot_admin(context, chat_id):
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        return any(a.user.id == context.bot.id for a in admins)
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        return False

def role_pool(n):
    roles = ["don", "mafia", "doctor", "killer"]
    while len(roles) < n:
        roles.append("citizen")
    random.shuffle(roles)
    return roles

# ================== COMMANDS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎭 Advanced Secret Mafia Bot")

async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇺🇿 Uzbek", callback_data="lang_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ]
    await update.message.reply_text("🌍 Language:", reply_markup=InlineKeyboardMarkup(kb))

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id

    if not await is_bot_admin(context, chat_id):
        await update.message.reply_text(
            t(uid, "need_admin") + "\n" + t(uid, "make_admin")
        )
        return

    # Check if game already exists and is active
    if chat_id in games:
        existing_game = games[chat_id]
        if existing_game.state in ["registration", "night", "day", "voting"]:
            await update.message.reply_text("⚠️ Bu guruhda allaqachon o'yin faol! / A game is already active in this chat.")
            return

    game = Game(chat_id)
    games[chat_id] = game

    msg = await update.message.reply_text(
        t(uid, "reg_started"),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Join", callback_data="join")]]
        ),
    )
    game.reg_msg_id = msg.message_id
    try:
        await context.bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
    except Exception as e:
        logger.warning(f"Could not pin message in chat {chat_id}: {e}")

    await asyncio.sleep(REGISTRATION_TIME)
    await start_game(context, chat_id)

async def start_game(context, chat_id):
    game = games.get(chat_id)
    if not game:
        return
    if len(game.players) < 3:
        try:
            await context.bot.send_message(chat_id, "⚠️ O'yin boshlanishi uchun kamida 3 ta ishtirokchi kerak! / Minimum 3 players required to start.")
        except Exception as e:
            logger.error(f"Error sending message in chat {chat_id}: {e}")
        # Clean up
        games.pop(chat_id, None)
        return

    try:
        await context.bot.unpin_chat_message(chat_id)
    except Exception as e:
        logger.warning(f"Could not unpin message in chat {chat_id}: {e}")

    roles = role_pool(len(game.players))
    for p, r in zip(game.players.values(), roles):
        p.role = r

    game.state = "night"
    try:
        night_url = get_presigned_url("night.gif")
        await context.bot.send_animation(chat_id, night_url, caption="🌙 Night")
    except Exception as e:
        logger.error(f"Error sending night animation to chat {chat_id}: {e}")
    await asyncio.sleep(NIGHT_DURATION)

    game.state = "day"
    try:
        day_url = get_presigned_url("day.gif")
        await context.bot.send_animation(chat_id, day_url, caption="☀️ Day")
    except Exception as e:
        logger.error(f"Error sending day animation to chat {chat_id}: {e}")
    await asyncio.sleep(DAY_DURATION)

    await start_voting(context, chat_id)

async def start_voting(context, chat_id):
    game = games.get(chat_id)
    if not game:
        return
    game.state = "voting"

    alive = [p for p in game.players.values() if p.alive]
    for p in alive:
        kb = [[InlineKeyboardButton(x.name, callback_data=f"vote_{x.id}")]
              for x in alive if x.id != p.id]
        try:
            await context.bot.send_message(p.id, "🗳 Vote:", reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            logger.warning(f"Could not send private voting message to user {p.id}: {e}")

    await asyncio.sleep(VOTING_DURATION)
    await finish_voting(context, chat_id)

async def finish_voting(context, chat_id):
    game = games.get(chat_id)
    if not game or not game.private_votes:
        if game:
            try:
                await context.bot.send_message(chat_id, "🗳 Hech kim ovoz bermadi. / No votes were cast.")
            except Exception as e:
                logger.error(f"Error sending message in chat {chat_id}: {e}")
        return

    target = max(set(game.private_votes.values()), key=list(game.private_votes.values()).count)
    
    # Check if target is a valid player
    if target not in game.players:
        logger.warning(f"Target player {target} not in game players.")
        return

    kb = [
        [InlineKeyboardButton("👍 Hang", callback_data=f"like_{target}")],
        [InlineKeyboardButton("👎 Save", callback_data=f"dislike_{target}")],
    ]
    try:
        await context.bot.send_message(
            chat_id,
            f"⚖️ Accused: {game.players[target].name}",
            reply_markup=InlineKeyboardMarkup(kb),
        )
    except Exception as e:
        logger.error(f"Error sending voting finish message in chat {chat_id}: {e}")

# ================== CALLBACKS ==================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    try:
        await q.answer()
    except Exception as e:
        logger.warning(f"Could not answer callback query: {e}")
        
    uid = q.from_user.id

    if q.data.startswith("lang_"):
        USER_LANG[uid] = q.data.split("_")[1]
        try:
            await q.edit_message_text(t(uid, "lang_set"))
        except Exception as e:
            logger.error(f"Error editing language message: {e}")

    elif q.data == "join":
        chat_id = q.message.chat.id
        game = games.get(chat_id)
        if not game:
            await q.answer("O'yin topilmadi / Game not found", show_alert=True)
            return
        if game.state != "registration":
            await q.answer("Ro'yxatdan o'tish yopilgan / Registration is closed", show_alert=True)
            return
        if uid in game.players:
            await q.answer(t(uid, "already_joined"), show_alert=True)
            return
        game.players[uid] = Player(uid, q.from_user.first_name)
        await q.answer(t(uid, "joined"))

    elif q.data.startswith("vote_"):
        game = next((g for g in games.values() if uid in g.players), None)
        if not game:
            await q.answer("O'yin topilmadi / Game not found", show_alert=True)
            return
        if game.state != "voting":
            await q.answer("Ovoz berish faol emas / Voting is not active", show_alert=True)
            return
        if uid in game.private_votes:
            await q.answer(t(uid, "vote_used"), show_alert=True)
            return
        
        try:
            target_id = int(q.data.split("_")[1])
            game.private_votes[uid] = target_id
            await q.answer("Ovoz qabul qilindi / Vote recorded")
        except ValueError:
            logger.error(f"Invalid vote target callback data: {q.data}")

    elif q.data.startswith("like_"):
        game = next((g for g in games.values() if uid in g.players and g.state == "voting"), None)
        if not game:
            await q.answer("Siz ushbu o'yinda emassiz yoki o'yin ovoz berish bosqichida emas / You are not in this game or it is not in voting phase", show_alert=True)
            return
        game.public_votes["like"].add(uid)
        await q.answer("👍")

    elif q.data.startswith("dislike_"):
        game = next((g for g in games.values() if uid in g.players and g.state == "voting"), None)
        if not game:
            await q.answer("Siz ushbu o'yinda emassiz yoki o'yin ovoz berish bosqichida emas / You are not in this game or it is not in voting phase", show_alert=True)
            return
        game.public_votes["dislike"].add(uid)
        await q.answer("👎")

# ================== ADMIN PANEL ==================

async def set_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("⛔ Siz admin emassiz! / Access denied.")
        return

    cmd_name = update.message.text.split()[0].lower()
    
    if not update.message.reply_to_message:
        await update.message.reply_text("📌 Iltimos, ushbu buyruqni biror GIF, rasm yoki videoga reply qilib yuboring.")
        return

    reply = update.message.reply_to_message
    file = None
    file_name = "day.gif" if "day" in cmd_name else "night.gif"
    content_type = "image/gif"
    
    if reply.animation:
        file = await reply.animation.get_file()
        content_type = reply.animation.mime_type or "image/gif"
    elif reply.document:
        file = await reply.document.get_file()
        content_type = reply.document.mime_type or "application/octet-stream"
    elif reply.video:
        file = await reply.video.get_file()
        content_type = reply.video.mime_type or "video/mp4"
    elif reply.photo:
        file = await reply.photo[-1].get_file()
        content_type = "image/jpeg"
        
    if not file:
        await update.message.reply_text("❌ Rasm, GIF yoki video topilmadi.")
        return

    s3_endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT")
    s3_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    s3_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("AWS_BUCKET_NAME")

    if all([s3_endpoint, s3_access_key, s3_secret_key, bucket_name]):
        status_msg = await update.message.reply_text("🔄 Fayl Railway Bucket'ga yuklanmoqda...")
        try:
            import io
            file_bytearray = await file.download_as_bytearray()
            file_io = io.BytesIO(file_bytearray)
            
            s3_client = boto3.client(
                's3',
                endpoint_url=s3_endpoint,
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                config=Config(signature_version='s3v4')
            )
            s3_client.upload_fileobj(
                file_io,
                bucket_name,
                file_name,
                ExtraArgs={'ContentType': content_type}
            )
            await status_msg.edit_text(f"✅ Muvaffaqiyatli yuklandi! Railway Bucket'ga `{file_name}` sifatida saqlandi.")
        except Exception as e:
            logger.error(f"S3 Upload error: {e}")
            await status_msg.edit_text(f"❌ Yuklashda xatolik yuz berdi: {e}")
    else:
        global DAY_IMAGE_URL, NIGHT_IMAGE_URL
        if "day" in cmd_name:
            DAY_IMAGE_URL = file.file_path
            await update.message.reply_text(f"✅ Vaqtinchalik sozlandi (S3 ulanmagan). Kunduzgi havola: {DAY_IMAGE_URL}")
        else:
            NIGHT_IMAGE_URL = file.file_path
            await update.message.reply_text(f"✅ Vaqtinchalik sozlandi (S3 ulanmagan). Tungi havola: {NIGHT_IMAGE_URL}")

# ================== CHAT GUARD ==================

async def chat_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.is_bot:
        return
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id].state == "night":
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message in chat {chat_id}: {e}")

# ================== MAIN ==================

def main():
    if BOT_TOKEN == "bot tokeningiz" or not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Iltimos, uni environment yoki .env faylda sozlang.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("lang", lang))
    app.add_handler(CommandHandler("setday", set_media))
    app.add_handler(CommandHandler("setnight", set_media))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, chat_guard))

    logger.info("Bot ishga tushmoqda...")
    app.run_polling()

if __name__ == "__main__":
    main()
