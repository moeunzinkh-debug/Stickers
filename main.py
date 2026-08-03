import os
import re
import tempfile
import uuid
import subprocess
import asyncio
from pathlib import Path
from PIL import Image
from telegram import Update, InputSticker
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from aiohttp import web

# ============ CONFIGURATION ============
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8000))

# Conversation states
SETTING_NAME, SETTING_TITLE, ADDING_STICKERS = range(3)


# ============ STICKER PROCESSING ============
def prepare_sticker_image(input_path: Path, output_path: Path):
    """Resize image to 512x512 as required by Telegram."""
    with Image.open(input_path) as img:
        ratio = min(512 / img.width, 512 / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        new_img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        new_img.paste(img, ((512 - new_size[0]) // 2, (512 - new_size[1]) // 2))
        new_img.save(output_path, "PNG")


def process_video_sticker(input_path: Path, output_path: Path):
    """Process video to meet Telegram requirements: .webm, 512x512, <3s, <256KB."""
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


# ============ EMOJI HANDLING ============
def extract_emojis(text):
    """Extract emoji from text. Returns default 😊 if no emoji found."""
    if not text:
        return ["😊"]
    
    try:
        import emoji
        emojis = [char for char in text if char in emoji.EMOJI_DATA]
        return emojis if emojis else ["😊"]
    except ImportError:
        # Fallback if emoji library not available
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        emojis = emoji_pattern.findall(text)
        return emojis if emojis else ["😊"]


# ============ HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Welcome to Sticker Bot!*\n\n"
        "I will help you create your own Telegram Sticker Set.\n\n"
        "📌 *How to use:*\n"
        "1️⃣ Send me a name for your sticker set (e.g., `mystickers`)\n"
        "2️⃣ Send me a title for your sticker set\n"
        "3️⃣ Send me photos or videos to add as stickers\n"
        "   • Send photo/video *without caption* → uses default emoji 😊\n"
        "   • Send photo/video *with caption containing emoji* → uses that emoji\n"
        "4️⃣ Send /done when you're finished\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👋 *សូមស្វាគមន៍មកកាន់ Sticker Bot!*\n\n"
        "ខ្ញុំនឹងជួយអ្នកបង្កើត Sticker Set ផ្ទាល់ខ្លួននៅ Telegram។\n\n"
        "📌 *របៀបប្រើប្រាស់:*\n"
        "1️⃣ ផ្ញើឈ្មោះសម្រាប់ Sticker Set (ឧទាហរណ៍៖ `mystickers`)\n"
        "2️⃣ ផ្ញើចំណងជើងសម្រាប់ Sticker Set\n"
        "3️⃣ ផ្ញើរូបភាព ឬ វីដេអូ ដើម្បីបន្ថែមជា Sticker\n"
        "   • ផ្ញើរូប/វីដេអូ *ដោយមិនមាន caption* → ប្រើ emoji លំនាំដើម 😊\n"
        "   • ផ្ញើរូប/វីដេអូ *ជាមួយ caption មាន emoji* → ប្រើ emoji នោះ\n"
        "4️⃣ ផ្ញើ /done នៅពេលរួចរាល់"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")
    return SETTING_NAME


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().lower()
    name = re.sub(r'[^a-z0-9]', '', name)
    if not name:
        await update.message.reply_text(
            "❌ Invalid name. Please send a name using only English letters (a-z) and numbers (0-9):\n\n"
            "❌ ឈ្មោះមិនត្រឹមត្រូវ។ សូមផ្ញើឈ្មោះជាអក្សរឡាតាំង (a-z) និងលេខ (0-9)៖"
        )
        return SETTING_NAME
    
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    unique_prefix = str(uuid.uuid4().hex)[:6]
    full_name = f"s{unique_prefix}{name}_by_{bot_username}"
    context.user_data['sticker_set_name'] = full_name
    
    await update.message.reply_text(
        f"✅ Name set: `{full_name}`\n"
        f"Now send a title for your Sticker Set:\n\n"
        f"✅ ឈ្មោះបានកំណត់៖ `{full_name}`\n"
        f"ឥឡូវនេះ សូមផ្ញើចំណងជើង (Title) សម្រាប់ Sticker Set៖"
    )
    return SETTING_TITLE


async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text(
            "❌ Title cannot be empty. Please send a title:\n\n"
            "❌ ចំណងជើងមិនអាចទទេបានទេ។ សូមផ្ញើចំណងជើង៖"
        )
        return SETTING_TITLE
    
    context.user_data['sticker_set_title'] = title
    await update.message.reply_text(
        f"✅ Title set: *{title}*\n\n"
        f"Now send me photos or videos to add as stickers.\n"
        f"• No caption → default emoji 😊\n"
        f"• With emoji in caption → uses that emoji\n"
        f"Send /done when finished.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ ចំណងជើងបានកំណត់៖ *{title}*\n\n"
        f"ឥឡូវនេះ សូមផ្ញើរូបភាព ឬ វីដេអូ ដើម្បីបន្ថែមជា Sticker។\n"
        f"• គ្មាន caption → emoji លំនាំដើម 😊\n"
        f"• មាន emoji ក្នុង caption → ប្រើ emoji នោះ\n"
        f"ផ្ញើ /done នៅពេលរួចរាល់។"
    )
    return ADDING_STICKERS


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_name = context.user_data.get('sticker_set_name')
    set_title = context.user_data.get('sticker_set_title')
    user_id = update.effective_user.id

    if not set_name or not set_title:
        await update.message.reply_text(
            "⚠️ Please send /start first!\n\n"
            "⚠️ សូមផ្ញើ /start ជាមុនសិន!"
        )
        return ADDING_STICKERS

    # យក caption ពី message (អាចទទេបាន)
    caption = update.message.caption if update.message.caption else ""
    emojis = extract_emojis(caption)
    
    print(f"[DEBUG] Photo caption: '{caption}'")
    print(f"[DEBUG] Emojis extracted: {emojis}")

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
                f"✅ Sticker added successfully!\n"
                f"Emoji: {''.join(emojis)}\n"
                f"Link: t.me/addstickers/{set_name}\n\n"
                f"✅ បានបន្ថែម Sticker រួចរាល់!\n"
                f"Emoji៖ {''.join(emojis)}\n"
                f"Link៖ t.me/addstickers/{set_name}"
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
                    f"✅ New Sticker Set created!\n"
                    f"Emoji: {''.join(emojis)}\n"
                    f"Link: t.me/addstickers/{set_name}\n\n"
                    f"✅ បានបង្កើត Sticker Set ថ្មី!\n"
                    f"Emoji៖ {''.join(emojis)}\n"
                    f"Link៖ t.me/addstickers/{set_name}"
                )
            else:
                await update.message.reply_text(
                    f"❌ Error: {e}\n\n"
                    f"❌ កំហុស៖ {e}"
                )
                
    return ADDING_STICKERS


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.animation
    set_name = context.user_data.get('sticker_set_name')
    set_title = context.user_data.get('sticker_set_title')
    user_id = update.effective_user.id

    if not set_name or not set_title:
        await update.message.reply_text(
            "⚠️ Please send /start first!\n\n"
            "⚠️ សូមផ្ញើ /start ជាមុនសិន!"
        )
        return ADDING_STICKERS

    # យក caption ពី message (អាចទទេបាន)
    caption = update.message.caption if update.message.caption else ""
    emojis = extract_emojis(caption)
    
    print(f"[DEBUG] Video caption: '{caption}'")
    print(f"[DEBUG] Emojis extracted: {emojis}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")
    video_file = await video.get_file()

    with tempfile.TemporaryDirectory() as temp_dir:
        raw_path = Path(temp_dir) / "raw.mp4"
        processed_path = Path(temp_dir) / "processed.webm"
        await video_file.download_to_drive(raw_path)
        
        file_size = raw_path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text(
                "❌ Video too large! Please send a video under 50MB.\n\n"
                "❌ វីដេអូធំពេក! សូមផ្ញើវីដេអូតិចជាង 50MB។"
            )
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
                    f"✅ Video Sticker added!\n"
                    f"Emoji: {''.join(emojis)}\n"
                    f"Link: t.me/addstickers/{set_name}\n\n"
                    f"✅ បានបន្ថែម Video Sticker រួចរាល់!\n"
                    f"Emoji៖ {''.join(emojis)}\n"
                    f"Link៖ t.me/addstickers/{set_name}"
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
                        f"✅ New Video Sticker Set created!\n"
                        f"Emoji: {''.join(emojis)}\n"
                        f"Link: t.me/addstickers/{set_name}\n\n"
                        f"✅ បានបង្កើត Video Sticker Set ថ្មី!\n"
                        f"Emoji៖ {''.join(emojis)}\n"
                        f"Link៖ t.me/addstickers/{set_name}"
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Error: {e}\n\n"
                        f"❌ កំហុស៖ {e}"
                    )
        else:
            await update.message.reply_text(
                "❌ Could not process video. Please make sure ffmpeg is installed.\n\n"
                "❌ មិនអាចកែច្នៃវីដេអូបានទេ។ សូមប្រាកដថា ffmpeg បានដំឡើង។"
            )

    return ADDING_STICKERS


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_name = context.user_data.get('sticker_set_name')
    if set_name:
        await update.message.reply_text(
            f"🎉 Done! Check your stickers here:\n"
            f"t.me/addstickers/{set_name}\n\n"
            f"🎉 រួចរាល់! ឆែកមើល Sticker នៅទីនេះ៖\n"
            f"t.me/addstickers/{set_name}\n\n"
            f"Send /start to create a new set.\n"
            f"ផ្ញើ /start ដើម្បីបង្កើត Set ថ្មី។"
        )
    else:
        await update.message.reply_text(
            "🎉 Done! Send /start to create a new Sticker Set.\n\n"
            "🎉 រួចរាល់! ផ្ញើ /start ដើម្បីបង្កើត Sticker Set ថ្មី។"
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Cancelled! Send /start to begin again.\n\n"
        "❌ បានបោះបង់! ផ្ញើ /start ដើម្បីចាប់ផ្តើមឡើងវិញ។"
    )
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
        entry_points=[CommandHandler("start", start)],
        states={
            SETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            SETTING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_title)],
            ADDING_STICKERS: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.VIDEO | filters.ANIMATION, handle_video),
                CommandHandler("done", done)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
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
