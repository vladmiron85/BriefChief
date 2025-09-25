# Jira Authorization Server

Сервер для авторизации пользователей в Jira через OAuth 2.0.

## Настройка

### 1. Переменные окружения

```bash
# Jira OAuth App настройки
JIRA_CLIENT_ID=your_client_id
JIRA_CLIENT_SECRET=your_client_secret
JIRA_REDIRECT_URI=http://localhost:5000/auth/callback
JIRA_BASE_URL=https://your-domain.atlassian.net

# Шифрование токенов (сгенерируйте новый ключ для продакшена)
ENCRYPTION_KEY=your_encryption_key_here
```

### 2. Создание OAuth App в Jira

1. Перейдите в **Jira Settings** → **Apps** → **OAuth 2.0 (3LO)**
2. Создайте новое приложение
3. Укажите:
   - **Callback URL**: `http://localhost:5000/auth/callback`
   - **Scopes**: `read:jira-work`, `write:jira-work`

### 3. Установка зависимостей

```bash
pip install -r auth_requirements.txt
```

### 4. Запуск сервера

```bash
python jira_auth_server.py
```

## API Endpoints

### 1. Начало авторизации
```
GET /auth/start?telegram_user_id=123456789
```

**Параметры:**
- `telegram_user_id` - ID пользователя в Telegram

**Ответ:**
```json
{
  "auth_url": "https://your-domain.atlassian.net/oauth/authorize?...",
  "telegram_user_id": "123456789",
  "state": "telegram_user_123456789"
}
```

**Примечание:** Теперь сервер возвращает JSON с ссылкой вместо редиректа. Это позволяет работать с удаленным сервером авторизации.

### 2. Колбэк авторизации
```
GET /auth/callback?code=xxx&state=telegram_user_123456789
```

**Параметры:**
- `code` - код авторизации от Jira
- `state` - содержит `telegram_user_id`

**Ответ:** HTML страница с результатом авторизации

### 3. Проверка статуса авторизации
```
GET /auth/status/<telegram_user_id>
```

**Ответ:**
```json
{
  "authenticated": true,
  "expires_at": "2024-01-01T12:00:00",
  "scope": "read:jira-work write:jira-work"
}
```

### 4. Отзыв авторизации
```
GET /auth/revoke/<telegram_user_id>
```

## Интеграция с Telegram ботом

### 1. Добавление команды авторизации в bot.py

```python
async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    auth_url = f"http://localhost:5000/auth/start?telegram_user_id={user_id}"
    
    keyboard = [
        [InlineKeyboardButton("🔐 Authorize with Jira", url=auth_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "To use Jira features, please authorize the bot:",
        reply_markup=reply_markup
    )

# Добавить в main():
application.add_handler(CommandHandler("auth", auth_command))
```

### 2. Проверка авторизации перед использованием Jira

```python
def is_user_authenticated(telegram_user_id: str) -> bool:
    try:
        response = requests.get(f"http://localhost:5000/auth/status/{telegram_user_id}")
        return response.json().get('authenticated', False)
    except:
        return False

def get_user_jira_token(telegram_user_id: str) -> Optional[str]:
    try:
        response = requests.get(f"http://localhost:5000/auth/status/{telegram_user_id}")
        if response.json().get('authenticated', False):
            # Здесь нужно получить токен через внутренний API
            return "user_token_here"
    except:
        pass
    return None
```

## Безопасность

1. **Шифрование токенов** - все токены шифруются перед сохранением
2. **Автоматическое обновление** - токены обновляются автоматически
3. **Валидация состояния** - проверка `state` параметра для предотвращения CSRF
4. **Логирование** - все операции логируются

## Файлы

- `user_tokens.json` - зашифрованные токены пользователей
- Логи в консоли

## Пример использования

1. Пользователь отправляет `/auth` в Telegram
2. Бот показывает кнопку "Authorize with Jira"
3. Пользователь нажимает кнопку → открывается браузер
4. Пользователь авторизуется в Jira
5. Jira перенаправляет на `/auth/callback` с кодом
6. Сервер сохраняет токен для пользователя
7. Пользователь может использовать Jira функции в боте
