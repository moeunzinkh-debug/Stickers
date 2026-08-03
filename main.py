import os
import re
import tempfile
import uuid
import subprocess
import asyncio
from pathlib import Path
from PIL import Image
from telegram import Update, InputSticker, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from aiohttp import web

# ============ CONFIGURATION ============
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8000))

# Conversation states
SELECTING_LANGUAGE, SETTING_NAME, SETTING_TITLE, ADDING_STICKERS, SELECTING_SET_TO_ADD = range(5)

# Store sticker sets per user (in-memory, use DB for production)
USER_STICKER_SETS = {}

# Language data
LANG = {
    "en": {
        "welcome": "👋 *Welcome to Sticker Bot!*\n\nI will help you create your own Telegram Sticker Set.",
        "how_to_use": (
            "📌 *How to use:*\n\n"
            "*Step 1:* Send a short name for your sticker set (e.g., `mystickers`)\n"
            "*Step 2:* Send a display title for your sticker pack\n\n"
            "Then send photos or videos to add as stickers:\n"
            "• No caption → default emoji 😊\n"
            "• With emoji in caption → uses that emoji\n\n"
            "*Commands:*\n"
            "• /start or /new — Create a new sticker set\n"
            "• /add — Add stickers to an existing set\n"
            "• /list — View all your sticker sets\n"
            "• /done — Finish adding stickers"
        ),
        "choose_lang": "🌐 Please choose your language:",
        "lang_set": "✅ Language set to English!",
        "invalid_name": "❌ Invalid name. Use only English letters (a-z) and numbers (0-9):",
        "name_set": "✅ Short name set: `{name}`\nNow send a display title for your Sticker Pack:",
        "title_empty": "❌ Title cannot be empty. Please send a title:",
        "title_set": (
            "✅ Title set: *{title}*\n\n"
            "Now send me photos or videos to convert to stickers.\n"
            "• No caption → default emoji 😊\n"
            "• With emoji in caption → uses that emoji\n"
            "Send /done when finished."
        ),
        "send_start_first": "⚠️ Please send /start first!",
        "sticker_added": "✅ Sticker added!\nEmoji: {emoji}\nLink: t.me/addstickers/{name}",
        "set_created": "✅ New Sticker Set created!\nEmoji: {emoji}\nLink: t.me/addstickers/{name}",
        "video_too_large": "❌ Video too large! Please send under 50MB.",
        "video_error": "❌ Could not process video. Make sure ffmpeg is installed.",
        "done": (
            "🎉 Done! Your sticker set:\nt.me/addstickers/{name}\n\n"
            "*What's next?*\n"
            "• /add — Add more stickers to this set\n"
            "• /new — Create a new set\n"
            "• /list — View all your sets"
        ),
        "no_sets": "📭 You don't have any sticker sets yet.\nSend /start to create one!",
        "your_sets": "📂 *Your Sticker Sets:*\n\n",
        "select_set": "🔽 Select a sticker set to add stickers to:",
        "set_selected": "✅ Selected: *{title}*\nSend me photos or videos to add!\nSend /done when finished.",
        "cancelled": "❌ Cancelled! Send /start to begin again.",
    },
    "kh": {
        "welcome": "👋 *សូមស្វាគមន៍មកកាន់ Sticker Bot!*\n\nខ្ញុំនឹងជួយអ្នកបង្កើត Sticker Set ផ្ទាល់ខ្លួននៅ Telegram។",
        "how_to_use": (
            "📌 *របៀបប្រើប្រាស់៖*\n\n"
            "*ជំហានទី ១៖* ផ្ញើឈ្មោះសម្រាប់ Sticker Set (ឧទាហរណ៍៖ `mystickers`)\n"
            "*ជំហានទី ២៖* ផ្ញើឈ្មោះបង្ហាញសម្រាប់ Sticker Pack\n\n"
            "បន្ទាប់មកផ្ញើរូបភាព ឬ វីដេអូ ដើម្បីបំប្លែងជា Sticker៖\n"
            "• គ្មាន caption → emoji លំនាំដើម 😊\n"
            "• មាន emoji ក្នុង caption → ប្រើ emoji នោះ\n\n"
            "*Commands៖*\n"
            "• /start ឬ /new — បង្កើត Sticker Set ថ្មី\n"
            "• /add — បន្ថែម Sticker ទៅ Set ដែលមានស្រាប់\n"
            "• /list — មើល Sticker Set ទាំងអស់\n"
            "• /done — បញ្ចប់ការបន្ថែម Sticker"
        ),
        "choose_lang": "🌐 សូមជ្រើសរើសភាសារបស់អ្នក៖",
        "lang_set": "✅ ភាសាត្រូវបានកំណត់ជាខ្មែរ!",
        "invalid_name": "❌ ឈ្មោះមិនត្រឹមត្រូវ។ សូមប្រើអក្សរឡាតាំង (a-z) និងលេខ (0-9)៖",
        "name_set": "✅ ឈ្មោះបានកំណត់៖ `{name}`\nឥឡូវនេះ សូមផ្ញើឈ្មោះបង្ហាញសម្រាប់ Sticker Pack៖",
        "title_empty": "❌ ចំណងជើងមិនអាចទទេបានទេ។ សូមផ្ញើចំណងជើង៖",
        "title_set": (
            "✅ ចំណងជើងបានកំណត់៖ *{title}*\n\n"
            "ឥឡូវនេះ សូមផ្ញើរូបភាព ឬ វីដេអូ ដើម្បីបំប្លែងជា Sticker។\n"
            "• គ្មាន caption → emoji លំនាំដើម 😊\n"
            "• មាន emoji ក្នុង caption → ប្រើ emoji នោះ\n"
            "ផ្ញើ /done នៅពេលរួចរាល់។"
        ),
        "send_start_first": "⚠️ សូមផ្ញើ /start ជាមុនសិន!",
        "sticker_added": "✅ បានបន្ថែម Sticker!\nEmoji៖ {emoji}\nLink៖ t.me/addstickers/{name}",
        "set_created": "✅ បានបង្កើត Sticker Set ថ្មី!\nEmoji៖ {emoji}\nLink៖ t.me/addstickers/{name}",
        "video_too_large": "❌ វីដេអូធំពេក! សូមផ្ញើតិចជាង 50MB។",
        "video_error": "❌ មិនអាចកែច្នៃវីដេអូបានទេ។ សូមប្រាកដថា ffmpeg បានដំឡើង។",
        "done": (
            "🎉 រួចរាល់! Sticker Set របស់អ្នក៖\nt.me/addstickers/{name}\n\n"
            "*ចង់ធ្វើអ្វីបន្ទាប់?*\n"
            "• /add — បន្ថែម Sticker ទៅ Set នេះ\n"
            "• /new — បង្កើត Set ថ្មី\n"
            "• /list — មើល Set ទាំងអស់"
        ),
        "no_sets": "📭 អ្នកមិនទាន់មាន Sticker Set ទេ។\nផ្ញើ /start ដើម្បីបង្កើត!",
        "your_sets": "📂 *Sticker Set របស់អ្នក៖*\n\n",
        "select_set": "🔽 ជ្រើសរើស Sticker Set ដើម្បីបន្ថែម Sticker៖",
        "set_selected": "✅ បានជ្រើសរើស៖ *{title}*\nផ្ញើរូបភាព ឬ វីដេអូមកខ្ញុំ!\nផ្ញើ /done នៅពេលរួចរាល់។",
        "cancelled": "❌ បានបោះបង់! ផ្ញើ /start ដើម្បីចាប់ផ្តើមឡើងវិញ។",
    }
}


def get_text(context, key, **kwargs):
    lang = context.user_data.get("lang", "en")
    text = LANG.get(lang, LANG["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def get_user_sets(user_id):
    return USER_STICKER_SETS.get(user_id, [])


def add_user_set(user_id, set_name, set_title):
    if user_id not in USER_STICKER_SETS:
        USER_STICKER_SETS[user_id] = []
    USER_STICKER_SETS[user_id].append({"name": set_name, "title": set_title})


# ============ STICKER PROCESSING ============
def prepare_sticker_image(input_path: Path, output_path: Path):
    with Image.open(input_path) as img:
        ratio = min(512 / img.width, 512 / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        new_img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        new_img.paste(img, ((512 - new_size[0]) // 2, (512 - new_size[1]) // 2))
        new_img.save(output_path, "PNG")


def process_video_sticker(input_path: Path, output_path: Path):
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', str(input_path),
            '-t', '2.9',
            '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0',
            '-c:v', 'libvpx-vp9',
            '-pix_fmt', 'yuva420p',
            '-b:v', '200k',
            '-crf', '30',
            '-an',
            str(output_path)
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"FFmpeg error: {e}")
        return False


def extract_emojis(text):
    if not text:
        return ["😊"]
    try:
        import emoji
        emojis = [char for char in text if char in emoji.EMOJI_DATA]
        return emojis if emojis else ["😊"]
    except ImportError:
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        emojis = emoji_pattern.findall(text)
        return emojis if emojis else ["😊"]


# ============ HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="lang_kh"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 *Please choose your language / សូមជ្រើសរើសភាសា*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return SELECTING_LANGUAGE


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    lang = "en" if query.data == "lang_en" else "kh"
    context.user_data["lang"] = lang
    
    welcome = get_text(context, "welcome")
    how_to = get_text(context, "how_to_use")
    
    await query.edit_message_text(
        f"{welcome}\n\n{how_to}",
        parse_mode="Markdown"
    )
    return SETTING_NAME


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().lower()
    name = re.sub(r'[^a-z0-9]', '', name)
    if not name:
        await update.message.reply_text(get_text(context, "invalid_name"))
        return SETTING_NAME
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    unique_prefix = str(uuid.uuid4().hex)[:6]
    full_name = f"s{unique_prefix}{name}_by_{bot_username}"
    context.user_data['sticker_set_name'] = full_name
    
    await update.message.reply_text(
        get_text(context, "name_set", name=full_name),
        parse_mode="Markdown"
    )
    return SETTING_TITLE


async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text(get_text(context, "title_empty"))
        return SETTING_TITLE
    
    context.user_data['sticker_set_title'] = title
    
    user_id = update.effective_user.id
    set_name = context.user_data['sticker_set_name']
    add_user_set(user_id, set_name, title)
    
    await update.message.reply_text(
        get_text(context, "title_set", title=title),
        parse_mode="Markdown"
    )
    return ADDING_STICKERS


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_name = context.user_data.get('sticker_set_name')
    set_title = context.user_data.get('sticker_set_title')
    user_id = update.effective_user.id

    if not set_name or not set_title:
        await update.message.reply_text(get_text(context, "send_start_first"))
        return ADDING_STICKERS

    caption = update.message.caption if update.message.caption else ""
    emojis = extract_emojis(caption)
    
    print(f"[DEBUG] Photo caption: '{caption}'")
    print(f"[DEBUG] Emojis: {emojis}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    photo_file = await update.message.photo[-1].get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_path = Path(temp_dir) / "raw.png"
        processed_path = Path(temp_dir) / "processed.png"
        await photo_file.download_to_drive(raw_path)
        prepare_sticker_image(raw_path, processed_path)
        
        try:
            with open(processed_path, 'rb') as sticker_file:
                await context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=set_name,
                    sticker=InputSticker(sticker=sticker_file, emoji_list=emojis),
                )
            await update.message.reply_text(
                get_text(context, "sticker_added", emoji=''.join(emojis), name=set_name)
            )
        except Exception as e:
            error_msg = str(e).lower()
            print(f"[DEBUG] Error: {e}")
            if any(x in error_msg for x in ["not found", "stickerset_invalid", "doesn't exist"]):
                with open(processed_path, 'rb') as sticker_file:
                    await context.bot.create_new_sticker_set(
                        user_id=user_id,
                        name=set_name,
                        title=set_title,
                        stickers=[InputSticker(sticker=sticker_file, emoji_list=emojis)],
                        sticker_format="static",
                    )
                await update.message.reply_text(
                    get_text(context, "set_created", emoji=''.join(emojis), name=set_name)
                )
            else:
                await update.message.reply_text(f"❌ Error: {e}")
                
    return ADDING_STICKERS


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.animation
    set_name = context.user_data.get('sticker_set_name')
    set_title = context.user_data.get('sticker_set_title')
    user_id = update.effective_user.id

    if not set_name or not set_title:
        await update.message.reply_text(get_text(context, "send_start_first"))
        return ADDING_STICKERS

    caption = update.message.caption if update.message.caption else ""
    emojis = extract_emojis(caption)
    
    print(f"[DEBUG] Video caption: '{caption}'")
    print(f"[DEBUG] Emojis: {emojis}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")
    video_file = await video.get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_path = Path(temp_dir) / "raw.mp4"
        processed_path = Path(temp_dir) / "processed.webm"
        await video_file.download_to_drive(raw_path)
        
        file_size = raw_path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text(get_text(context, "video_too_large"))
            return ADDING_STICKERS
        
        if process_video_sticker(raw_path, processed_path):
            try:
                with open(processed_path, 'rb') as sticker_file:
                    await context.bot.add_sticker_to_set(
                        user_id=user_id,
                        name=set_name,
                        sticker=InputSticker(sticker=sticker_file, emoji_list=emojis),
                    )
                await update.message.reply_text(
                    get_text(context, "sticker_added", emoji=''.join(emojis), name=set_name)
                )
            except Exception as e:
                error_msg = str(e).lower()
                print(f"[DEBUG] Error: {e}")
                if any(x in error_msg for x in ["not found", "stickerset_invalid", "doesn't exist"]):
                    with open(processed_path, 'rb') as sticker_file:
                        await context.bot.create_new_sticker_set(
                            user_id=user_id,
                            name=set_name,
                            title=set_title,
                            stickers=[InputSticker(sticker=sticker_file, emoji_list=emojis)],
                            sticker_format="video",
                        )
                    await update.message.reply_text(
                        get_text(context, "set_created", emoji=''.join(emojis), name=set_name)
                    )
                else:
                    await update.message.reply_text(f"❌ Error: {e}")
        else:
            await update.message.reply_text(get_text(context, "video_error"))

    return ADDING_STICKERS


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_name = context.user_data.get('sticker_set_name')
    if set_name:
        await update.message.reply_text(
            get_text(context, "done", name=set_name)
        )
    else:
        await update.message.reply_text(get_text(context, "cancelled"))
    
    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    
    return ConversationHandler.END


async def new_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)


async def list_sets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sets = get_user_sets(user_id)
    
    if not sets:
        await update.message.reply_text(get_text(context, "no_sets"))
        return
    
    text = get_text(context, "your_sets")
    for i, s in enumerate(sets, 1):
        text += f"{i}. *{s['title']}*\n   t.me/addstickers/{s['name']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def add_to_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sets = get_user_sets(user_id)
    
    if not sets:
        await update.message.reply_text(get_text(context, "no_sets"))
        return ConversationHandler.END
    
    keyboard = []
    for s in sets:
        keyboard.append([InlineKeyboardButton(s['title'], callback_data=f"add_{s['name']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_text(context, "select_set"),
        reply_markup=reply_markup
    )
    return SELECTING_SET_TO_ADD


async def select_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    set_name = query.data.replace("add_", "")
    user_id = update.effective_user.id
    sets = get_user_sets(user_id)
    
    selected = next((s for s in sets if s['name'] == set_name), None)
    if not selected:
        await query.edit_message_text("❌ Set not found.")
        return ConversationHandler.END
    
    context.user_data['sticker_set_name'] = selected['name']
    context.user_data['sticker_set_title'] = selected['title']
    
    await query.edit_message_text(
        get_text(context, "set_selected", title=selected['title']),
        parse_mode="Markdown"
    )
    return ADDING_STICKERS


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    context.user_data.clear()
    context.user_data["lang"] = lang
    await update.message.reply_text(get_text(context, "cancelled"))
    return ConversationHandler.END


# ============ WEBHOOK SERVER ============
async def health_check(request):
    return web.Response(text="✅ Bot is alive!", status=200)


async def webhook_handler(request):
    application = request.app['telegram_app']
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return web.Response(status=200)


async def setup_webhook(application: Application):
    await application.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook",
        allowed_updates=Update.ALL_TYPES
    )


# ============ MAIN ============
async def main():
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("new", new_set),
            CommandHandler("add", add_to_set),
        ],
        states={
            SELECTING_LANGUAGE: [CallbackQueryHandler(language_callback, pattern="^lang_")],
            SETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            SETTING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_title)],
            ADDING_STICKERS: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.VIDEO | filters.ANIMATION, handle_video),
                CommandHandler("done", done)
            ],
            SELECTING_SET_TO_ADD: [CallbackQueryHandler(select_set_callback, pattern="^add_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("list", list_sets))
    
    app = web.Application()
    app['telegram_app'] = application
    app.router.add_get('/', health_check)
    app.router.add_post('/webhook', webhook_handler)
    
    await application.initialize()
    await application.start()
    await setup_webhook(application)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    print(f"🚀 Server running on port {PORT}")
    print(f"🔗 Webhook URL: {WEBHOOK_URL}/webhook")
    await site.start()
    
    while True:
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(main())
