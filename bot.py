import asyncio
import logging
import os
from typing import Optional, Tuple

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession

from LLM import get_available_models, handle_llm_command
from messages import get_message, get_user_language

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING", "")
JIRA_AUTH_SERVER_URL = os.environ.get("JIRA_AUTH_SERVER_URL", "http://localhost:5000")

client = None

async def create_telethon_client():
    global client
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start(bot_token=TOKEN)
    logger.info("Telethon client started successfully")
    return client

def get_user_info(update: Update) -> Tuple[int, str, str]:
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_lang = get_user_language(user_id)
    return user_id, user_name, user_lang

def is_user_authenticated(telegram_user_id: int) -> bool:
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/status/{telegram_user_id}")
        return response.json().get('authenticated', False)
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return False

async def check_auth_and_reply(update: Update, user_id: int, user_name: str, user_lang: str) -> bool:
    if not is_user_authenticated(user_id):
        reply_method = update.message.reply_text if hasattr(update, 'message') else update.callback_query.edit_message_text
        message_key = "auth_required" if hasattr(update, 'message') else "auth_required_short"
        await reply_method(get_message(message_key, user_lang, user_name=user_name))
        return False
    return True

async def get_chat_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, user_lang: str) -> str:
    global client
    
    if client is None or not client.is_connected():
        logger.error("Telethon client is not connected")
        return get_message("telethon_not_connected", user_lang)
    
    messages = []
    try:
        logger.info("Getting last 50 messages from chat")
        async for message in client.iter_messages(update.effective_chat.id, limit=50):
            if message.from_id and hasattr(message.from_id, 'user_id') and message.from_id.user_id == context.bot.id:
                continue
            if message.text:
                sender = message.sender.username or message.sender.first_name if message.sender else "Unknown"
                messages.append(f"{sender}: {message.text}")
        
        logger.info(f"Retrieved {len(messages)} messages from chat history")
        return "\n".join(messages) if messages else get_message("no_messages_found", user_lang)
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        return get_message("error_retrieving_messages", user_lang, error=str(e))

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, user_name, user_lang = get_user_info(update)
    
    if is_user_authenticated(user_id):
        await update.message.reply_text(get_message("auth_already_authorized", user_lang, user_name=user_name))
        return
    
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/start?telegram_user_id={user_id}")
        
        if response.status_code == 200 and (auth_url := response.json().get('auth_url')):
            keyboard = [[InlineKeyboardButton(get_message("auth_button", user_lang), url=auth_url)]]
            await update.message.reply_text(
                get_message("auth_prompt", user_lang, user_name=user_name),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif response.status_code == 200:
            await update.message.reply_text(get_message("auth_url_failed", user_lang, user_name=user_name))
        else:
            await update.message.reply_text(get_message("auth_server_unavailable", user_lang, user_name=user_name))
    except Exception as e:
        logger.error(f"Error getting auth URL: {e}")
        await update.message.reply_text(get_message("auth_error", user_lang, user_name=user_name))

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, user_name, user_lang = get_user_info(update)
    message_key = "status_authorized" if is_user_authenticated(user_id) else "status_not_authorized"
    await update.message.reply_text(get_message(message_key, user_lang, user_name=user_name))

async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, user_name, user_lang = get_user_info(update)
    
    if not await check_auth_and_reply(update, user_id, user_name, user_lang):
        return
    
    keyboard = [[InlineKeyboardButton(name, callback_data=model_id)] 
                for model_id, name in get_available_models().items()]
    await update.message.reply_text(
        get_message("select_model", user_lang),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id, user_name, user_lang = get_user_info(update)
    logger.info(f"Test command called by user ID: {user_id}, Name: {user_name}")
    
    if not await check_auth_and_reply(update, user_id, user_name, user_lang):
        return
    
    test_chat_history = ""
    if os.path.exists("generated_daily_chat.txt"):
        with open("generated_daily_chat.txt", "r", encoding="utf-8") as f:
            test_chat_history = f.read().strip()
    
    await update.message.reply_text(get_message("processing_openai", user_lang))
    response, success = await handle_llm_command(test_chat_history, 'model_openai', str(user_id))
    await update.message.reply_text(response, parse_mode='HTML')

async def brief_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id, user_name, user_lang = get_user_info(update)
    
    if not await check_auth_and_reply(update, user_id, user_name, user_lang):
        return
    
    await query.edit_message_text(get_message("processing_with_model", user_lang, model=query.data))
    await query.edit_message_text(get_message("getting_messages", user_lang))
    
    messages = await get_chat_messages(update, context, user_lang)
    if messages == get_message("no_messages_found", user_lang):
        await query.edit_message_text(messages)
        return
    
    response, success = await handle_llm_command(messages, query.data, str(user_id))
    await query.edit_message_text(response, parse_mode='HTML')

async def main() -> None:
    try:
        logger.info("Creating and starting Telethon client...")
        await create_telethon_client()
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("auth", auth_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("brief", brief_command))
        application.add_handler(CommandHandler("test", test_command))
        application.add_handler(CallbackQueryHandler(brief_callback, pattern="^model_"))
        
        logger.info("Starting Telegram bot application...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise
    finally:
        logger.info("Shutting down...")
        if client and client.is_connected():
            await client.disconnect()
        await application.stop()

if __name__ == "__main__":
    asyncio.run(main())
