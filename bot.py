import os
import logging
import requests
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from LLM import get_available_models, handle_llm_command
# from proposals_editor import propose, set_field, on_callback

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Telethon client configuration (for accessing full chat history)
# These need to be set as environment variables
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING", "")

# Jira Auth Server configuration
JIRA_AUTH_SERVER_URL = os.environ.get("JIRA_AUTH_SERVER_URL", "http://localhost:5000")

# LLM API calls are now handled in LLM package

# Initialize Telethon client
client = None

# Function to create a fresh Telethon client
async def create_telethon_client():
    global client
    # Create a new client with the session string
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    
    # Start the client with the bot token
    await client.start(bot_token=TOKEN)
    logger.info("Telethon client started successfully")
    return client

# Jira Authorization functions
def is_user_authenticated(telegram_user_id: str) -> bool:
    """Проверить, авторизован ли пользователь в Jira"""
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/status/{telegram_user_id}")
        return response.json().get('authenticated', False)
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return False

def get_user_jira_token(telegram_user_id: str) -> Optional[str]:
    """Получить токен пользователя для Jira API"""
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/status/{telegram_user_id}")
        if response.json().get('authenticated', False):
            # Здесь нужно будет добавить внутренний API для получения токена
            # Пока возвращаем заглушку
            return "authenticated_user_token"
    except Exception as e:
        logger.error(f"Error getting user token: {e}")
    return None

# Get last 50 chat messages using Telethon
async def get_chat_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    global client
    
    if client is None or not client.is_connected():
        logger.error("Telethon client is not connected")
        return "Error: Could not connect to Telegram to retrieve messages."
    
    chat_id = update.effective_chat.id
    
    # Get last 50 messages using Telethon
    messages = []
    try:
        logger.info("Getting last 50 messages from chat")
        message_count = 0
        async for message in client.iter_messages(chat_id, limit=50):
            # Skip bot's own messages
            if message.from_id and hasattr(message.from_id, 'user_id') and message.from_id.user_id == context.bot.id:
                continue
                
            # Add message to our collection if it has text
            if message.text:
                sender = None
                if message.sender:
                    sender = message.sender.username or message.sender.first_name
                else:
                    sender = "Unknown"
                messages.append(f"{sender}: {message.text}")
                message_count += 1
        
        logger.info(f"Retrieved {message_count} messages from chat history")
        
        # Join messages into a single string
        return "\n".join(messages) if messages else "No messages found in chat."
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        return f"Error retrieving messages: {str(e)}"

# Command handler for /auth command
async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для авторизации пользователя в Jira"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Проверяем, авторизован ли уже пользователь
    if is_user_authenticated(user_id):
        await update.message.reply_text(
            f"✅ {user_name}, вы уже авторизованы в Jira!\n"
            f"Можете использовать команды для работы с задачами."
        )
        return
    
    try:
        # Получаем ссылку для авторизации от сервера
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/start?telegram_user_id={user_id}")
        
        if response.status_code == 200:
            auth_data = response.json()
            auth_url = auth_data.get('auth_url')
            
            if auth_url:
                keyboard = [
                    [InlineKeyboardButton("🔐 Авторизоваться в Jira", url=auth_url)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"👋 {user_name}, для работы с Jira необходимо авторизоваться.\n\n"
                    f"Нажмите кнопку ниже, чтобы перейти к авторизации:",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"❌ {user_name}, не удалось получить ссылку для авторизации.\n"
                    f"Попробуйте позже или обратитесь к администратору."
                )
        else:
            await update.message.reply_text(
                f"❌ {user_name}, сервер авторизации недоступен.\n"
                f"Попробуйте позже или обратитесь к администратору."
            )
            
    except Exception as e:
        logger.error(f"Error getting auth URL: {e}")
        await update.message.reply_text(
            f"❌ {user_name}, произошла ошибка при получении ссылки для авторизации.\n"
            f"Попробуйте позже или обратитесь к администратору."
        )

# Command handler for /status command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для проверки статуса авторизации"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if is_user_authenticated(user_id):
        await update.message.reply_text(
            f"✅ {user_name}, вы авторизованы в Jira!\n"
            f"Можете использовать все функции бота."
        )
    else:
        await update.message.reply_text(
            f"❌ {user_name}, вы не авторизованы в Jira.\n"
            f"Используйте команду /auth для авторизации."
        )

# Command handler for /brief command with auth check
async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для анализа чата с проверкой авторизации"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Проверяем авторизацию
    if not is_user_authenticated(user_id):
        await update.message.reply_text(
            f"❌ {user_name}, для использования этой функции необходимо авторизоваться в Jira.\n"
            f"Используйте команду /auth для авторизации."
        )
        return
    
    # Показываем доступные модели
    available_models = get_available_models()
    
    # Create keyboard buttons dynamically
    keyboard = []
    for model_id, display_name in available_models.items():
        keyboard.append([InlineKeyboardButton(display_name, callback_data=model_id)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите модель LLM:", reply_markup=reply_markup)

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log user ID who called the bot
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    logger.info(f"Test command called by user ID: {user_id}, Name: {user_name}")
    
    # Check authentication
    if not is_user_authenticated(user_id):
        await update.message.reply_text(
            f"❌ {user_name}, для использования этой функции необходимо авторизоваться в Jira.\n"
            f"Используйте команду /auth для авторизации."
        )
        return
    
    test_file_name = "sample_chat_dialogue_workplace.txt"
    test_chat_history = ""
    if os.path.exists(test_file_name):
        with open(test_file_name, "r", encoding="utf-8") as f:
            test_chat_history = f.read().strip()
    await update.message.reply_text("Processing messages using OpenAI...")
    response, success = await handle_llm_command(test_chat_history, 'model_openai', str(user_id))
    
    # Send response and store the message ID if successful
    await update.message.reply_text(response)

# Callback handler for model selection with auth check
async def brief_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для обработки выбора модели с проверкой авторизации"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Проверяем авторизацию
    if not is_user_authenticated(user_id):
        await query.edit_message_text(
            "❌ Для использования этой функции необходимо авторизоваться в Jira.\n"
            "Используйте команду /auth для авторизации."
        )
        return
    
    model = query.data
    await query.edit_message_text(f"Обработка сообщений с помощью {model}...")
    
    # Получаем сообщения чата
    await query.edit_message_text("Получение сообщений чата...")
    messages = await get_chat_messages(update, context)
    
    if messages == "No messages found in chat.":
        await query.edit_message_text("Сообщения в чате не найдены.")
        return
    
    # Обрабатываем сообщения с помощью LLM
    response, success = await handle_llm_command(messages, model, str(user_id))
    
    # Отправляем ответ
    await query.edit_message_text(response)

# Main function
async def main() -> None:
    try:
        # Create and start Telethon client first (only once)
        logger.info("Creating and starting Telethon client...")
        await create_telethon_client()
        
        # Create application
        application = Application.builder().token(TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("auth", auth_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("brief", brief_command))
        application.add_handler(CommandHandler("test", test_command))
 #       application.add_handler(CommandHandler("propose", propose))
 #       application.add_handler(CommandHandler("set", set_field))
        application.add_handler(CallbackQueryHandler(brief_callback, pattern="^model_"))
 #       application.add_handler(CallbackQueryHandler(on_callback, pattern="^(?!model_).+"))
        
        # Run the bot with updater
        logger.info("Starting Telegram bot application...")
        await application.initialize()
        await application.start()
        
        # Keep the application running
        await application.updater.start_polling()
        
        # Use a simple loop to keep the application running
        logger.info("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise
    finally:
        # Properly close the client when the bot stops
        logger.info("Shutting down...")
        if client and client.is_connected():
            await client.disconnect()
        await application.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
