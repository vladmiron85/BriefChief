MESSAGES = {
    "ru": {
        "telethon_not_connected": "Ошибка: Не удалось подключиться к Telegram для получения сообщений.",
        "no_messages_found": "Сообщения в чате не найдены.",
        "error_retrieving_messages": "Ошибка при получении сообщений: {error}",
        
        "auth_already_authorized": "✅ {user_name}, вы уже авторизованы в Jira!\nМожете использовать команды для работы с задачами.",
        "auth_button": "🔐 Авторизоваться в Jira",
        "auth_prompt": "👋 {user_name}, для работы с Jira необходимо авторизоваться.\n\nНажмите кнопку ниже, чтобы перейти к авторизации:",
        "auth_url_failed": "❌ {user_name}, не удалось получить ссылку для авторизации.\nПопробуйте позже или обратитесь к администратору.",
        "auth_server_unavailable": "❌ {user_name}, сервер авторизации недоступен.\nПопробуйте позже или обратитесь к администратору.",
        "auth_error": "❌ {user_name}, произошла ошибка при получении ссылки для авторизации.\nПопробуйте позже или обратитесь к администратору.",
        
        "status_authorized": "✅ {user_name}, вы авторизованы в Jira!\nМожете использовать все функции бота.",
        "status_not_authorized": "❌ {user_name}, вы не авторизованы в Jira.\nИспользуйте команду /auth для авторизации.",
        
        "auth_required": "❌ {user_name}, для использования этой функции необходимо авторизоваться в Jira.\nИспользуйте команду /auth для авторизации.",
        "auth_required_short": "❌ Для использования этой функции необходимо авторизоваться в Jira.\nИспользуйте команду /auth для авторизации.",
        
        "select_model": "Выберите модель LLM:",
        "processing_with_model": "Обработка сообщений с помощью {model}...",
        "getting_messages": "Получение сообщений чата...",
        "processing_openai": "Обработка сообщений с помощью OpenAI...",
    },
    
    "en": {
        "telethon_not_connected": "Error: Could not connect to Telegram to retrieve messages.",
        "no_messages_found": "No messages found in chat.",
        "error_retrieving_messages": "Error retrieving messages: {error}",
        
        "auth_already_authorized": "✅ {user_name}, you are already authorized in Jira!\nYou can use commands to work with tasks.",
        "auth_button": "🔐 Authorize with Jira",
        "auth_prompt": "👋 {user_name}, you need to authorize with Jira to use this feature.\n\nClick the button below to proceed with authorization:",
        "auth_url_failed": "❌ {user_name}, failed to get authorization link.\nPlease try again later or contact the administrator.",
        "auth_server_unavailable": "❌ {user_name}, authorization server is unavailable.\nPlease try again later or contact the administrator.",
        "auth_error": "❌ {user_name}, an error occurred while getting authorization link.\nPlease try again later or contact the administrator.",
        
        "status_authorized": "✅ {user_name}, you are authorized in Jira!\nYou can use all bot features.",
        "status_not_authorized": "❌ {user_name}, you are not authorized in Jira.\nUse /auth command to authorize.",
        
        "auth_required": "❌ {user_name}, you need to authorize with Jira to use this feature.\nUse /auth command to authorize.",
        "auth_required_short": "❌ You need to authorize with Jira to use this feature.\nUse /auth command to authorize.",
        
        "select_model": "Select LLM model:",
        "processing_with_model": "Processing messages with {model}...",
        "getting_messages": "Getting chat messages...",
        "processing_openai": "Processing messages using OpenAI...",
    }
}

def get_message(key: str, lang: str = "en", **kwargs) -> str:
    message = MESSAGES.get(lang, MESSAGES["en"]).get(key, key)
    if kwargs:
        return message.format(**kwargs)
    return message

def get_user_language(user_id: int) -> str:
    return "en"

