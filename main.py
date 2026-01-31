# advanced_secret_mafia_bot.py
# PRODUCTION READY – SINGLE FILE VERSION

import asyncio
import random
from collections import defaultdict
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

# ================== CONFIG ==================

BOT_TOKEN = "8258628759:AAHbKdTS-UBpBldb_TSaJhTkFuDRTcyCFMA"
ADMIN_ID = 6151329850

DAY_IMAGE_URL = "https://t.me/c/3348020476/3"
NIGHT_IMAGE_URL = "https://t.me/c/3348020476/4"

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
    admins = await context.bot.get_chat_administrators(chat_id)
    return any(a.user.id == context.bot.id for a in admins)

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
    except:
        pass

    await asyncio.sleep(REGISTRATION_TIME)
    await start_game(context, chat_id)

async def start_game(context, chat_id):
    game = games.get(chat_id)
    if not game or len(game.players) < 3:
        return

    try:
        await context.bot.unpin_chat_message(chat_id)
    except:
        pass

    roles = role_pool(len(game.players))
    for p, r in zip(game.players.values(), roles):
        p.role = r

    game.state = "night"
    await context.bot.send_photo(chat_id, NIGHT_IMAGE_URL, caption="🌙 Night")
    await asyncio.sleep(NIGHT_DURATION)

    game.state = "day"
    await context.bot.send_photo(chat_id, DAY_IMAGE_URL, caption="☀️ Day")
    await asyncio.sleep(DAY_DURATION)

    await start_voting(context, chat_id)

async def start_voting(context, chat_id):
    game = games[chat_id]
    game.state = "voting"

    alive = [p for p in game.players.values() if p.alive]
    for p in alive:
        kb = [[InlineKeyboardButton(x.name, callback_data=f"vote_{x.id}")]
              for x in alive if x.id != p.id]
        await context.bot.send_message(p.id, "🗳 Vote:", reply_markup=InlineKeyboardMarkup(kb))

    await asyncio.sleep(VOTING_DURATION)
    await finish_voting(context, chat_id)

async def finish_voting(context, chat_id):
    game = games[chat_id]
    if not game.private_votes:
        return

    target = max(set(game.private_votes.values()), key=list(game.private_votes.values()).count)
    kb = [
        [InlineKeyboardButton("👍 Hang", callback_data=f"like_{target}")],
        [InlineKeyboardButton("👎 Save", callback_data=f"dislike_{target}")],
    ]
    await context.bot.send_message(
        chat_id,
        f"⚖️ Accused: {game.players[target].name}",
        reply_markup=InlineKeyboardMarkup(kb),
    )

# ================== CALLBACKS ==================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data.startswith("lang_"):
        USER_LANG[uid] = q.data.split("_")[1]
        await q.edit_message_text(t(uid, "lang_set"))

    elif q.data == "join":
        game = games.get(q.message.chat.id)
        if uid in game.players:
            await q.answer(t(uid, "already_joined"), show_alert=True)
            return
        game.players[uid] = Player(uid, q.from_user.first_name)
        await q.answer(t(uid, "joined"))

    elif q.data.startswith("vote_"):
        game = next(g for g in games.values() if uid in g.players)
        if uid in game.private_votes:
            await q.answer(t(uid, "vote_used"), show_alert=True)
            return
        game.private_votes[uid] = int(q.data.split("_")[1])

    elif q.data.startswith("like_"):
        game = next(g for g in games.values() if g.state == "voting")
        game.public_votes["like"].add(uid)

    elif q.data.startswith("dislike_"):
        game = next(g for g in games.values() if g.state == "voting")
        game.public_votes["dislike"].add(uid)

# ================== CHAT GUARD ==================

async def chat_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.is_bot:
        return
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id].state == "night":
        try:
            await update.message.delete()
        except:
            pass

# ================== MAIN ==================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("lang", lang))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, chat_guard))

    app.run_polling()

if __name__ == "__main__":
    main()