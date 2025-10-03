# 🤖 BriefChief

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)

**BriefChief** is an intelligent Telegram bot that analyzes your team's chat conversations and automatically identifies task agreements, deadlines, and action items. It seamlessly integrates with Jira to provide context-aware insights powered by AI.

## ✨ Features

- 🔍 **Smart Chat Analysis** - Uses GPT-4o to analyze conversation history and extract task agreements
- 📋 **Jira Integration** - OAuth 2.0 authentication with full Jira API access
- 🌐 **Multi-language Support** - Built-in i18n support (English and Russian)
- 🔐 **Secure Authentication** - Token encryption and secure credential management
- 🛠️ **LangChain Agent** - Intelligent agent with Jira tools for context-aware responses
- 📊 **Task Tracking** - Automatically suggests task updates and status changes
- 💬 **Natural Language Processing** - Understands context and filters out casual conversations

## 💻 How it looks like
![Example of DriefChief usage](https://github.com/user-attachments/assets/d1a50550-3f6d-49af-a478-c13f56daa70f)

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Telegram Bot   │─────▶│  LLM Handler     │─────▶│    OpenAI       │
│  (bot.py)       │      │  (call_llm)      │      │    GPT-4o       │
└────────┬────────┘      └────────┬─────────┘      └─────────────────┘
         │                        │
         │                        │ Tools
         │                        ▼
         │               ┌──────────────────┐
         │               │  Jira Tools      │
         │               │  (LangChain)     │
         │               └────────┬─────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│  Jira Auth      │◀────▶│  Jira Cloud API  │
│  Server         │      │  (OAuth 2.0)     │
└─────────────────┘      └──────────────────┘
```

## 📋 Prerequisites

- Python 3.10 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Telegram API credentials (from [my.telegram.org](https://my.telegram.org/apps))
- OpenAI API Key
- Jira Cloud account with OAuth 2.0 app configured
- PostgreSQL or file-based storage for tokens

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/vladmiron85/BriefChief.git
cd briefchief
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

For the Jira Auth Server:
```bash
pip install -r jira_auth_server/requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_STRING=your_session_string

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Jira Auth Server URL
JIRA_AUTH_SERVER_URL=http://localhost:5000

# Internal API Key (for secure communication)
INTERNAL_API_KEY=your_generated_internal_api_key
```

### 4. Configure Jira Auth Server

Create `.env` file in `jira_auth_server/` directory:

```env
# Jira OAuth 2.0 Configuration
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_REDIRECT_URI=https://yourdomain.com/auth/callback
JIRA_BASE_URL=https://auth.atlassian.com

# Token Encryption
ENCRYPTION_KEY=your_fernet_encryption_key

# Internal API Key (must match bot's key)
INTERNAL_API_KEY=your_generated_internal_api_key
```

### 5. Generate Required Keys

**Generate Telegram Session String:**
```bash
python generate_session.py
```

**Generate Encryption Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Generate Internal API Key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 6. Set Up Jira OAuth App

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Create a new OAuth 2.0 (3LO) app
3. Set callback URL: `http://localhost:5000/auth/callback` (for local development)
4. Add permissions: `read:jira-work`, `read:jira-user`, `write:jira-work` (the last one is dangerous. don't switch it on during experiments until you 100% sure that your AI agent is fine)
5. Copy Client ID and Client Secret to your `.env` file

### 7. Start the Services

**Terminal 1 - Start Jira Auth Server:**
```bash
cd jira_auth_server
python jira_auth_server.py
```

**Terminal 2 - Start Telegram Bot:**
```bash
python bot.py
```

## 💡 Usage

### Bot Commands

- `/auth` - Authenticate with Jira
- `/status` - Check your Jira authentication status
- `/brief` - Analyze recent chat messages and identify task agreements
- `/test` - Test with pre-generated chat history

### Example Workflow

1. **Authenticate with Jira:**
   ```
   User: /auth
   Bot: 👋 Please authorize with Jira...
   [User clicks button and completes OAuth flow]
   Bot: ✅ Authorization Successful!
   ```

2. **Analyze Chat:**
   ```
   User: /brief
   Bot: Select LLM model:
   [User selects OpenAI]
   Bot: Getting chat messages...
   Bot: Processing messages with OpenAI...
   
   Found task agreements:
   
   Task: Update login page design
   State change: New status is In Progress
   Comment to add: Team agreed to use blue color scheme...
   Task link: PROJ-123
   ```

## 📁 Project Structure

```
briefchief/
├── bot.py                      # Main Telegram bot
├── messages.py                 # i18n message definitions
├── generate_session.py         # Telegram session generator
├── requirements.txt            # Python dependencies
├── .env.example               # Example environment variables
│
├── LLM/                       # LLM and AI logic
│   ├── __init__.py
│   ├── llm_handler.py        # LLM orchestration
│   ├── jira_tools.py         # Jira LangChain tools
│   ├── prompt_system.txt     # System prompt
│   └── prompt_user.txt       # User prompt template
│
└── jira_auth_server/         # Jira OAuth server
    ├── jira_auth_server.py   # Flask auth server
    ├── requirements.txt       # Auth server dependencies
    ├── .env.example          # Example auth server config
    ├── JIRA_AUTH_README.md   # Detailed auth docs
    └── auth_flow_diagram.md  # OAuth flow diagram
```

## 🔧 Configuration

### Customizing Prompts

Edit `LLM/prompt_system.txt` and `LLM/prompt_user.txt` to customize how the AI analyzes conversations:

```text
# prompt_system.txt
You are an AI assistant specialized in analyzing chat conversations...

# prompt_user.txt
Your task is to:
1. Read through the provided chat history
2. Identify any agreements made on tasks
3. Summarize changes to be made
...
```

### Adding New Languages

Edit `messages.py` to add new language support:

```python
MESSAGES = {
    "ru": { ... },
    "en": { ... },
    "es": {  # Add Spanish
        "auth_button": "🔐 Autorizar con Jira",
        ...
    }
}
```

## 🔒 Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Rotate encryption keys** regularly in production
3. **Use HTTPS** for production Jira OAuth callbacks
4. **Implement rate limiting** on public endpoints
5. **Keep dependencies updated** - Run `pip install --upgrade -r requirements.txt`

## 🐛 Troubleshooting

### Bot doesn't respond
- Check if both services are running (bot and auth server)
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check logs for errors

### Jira authentication fails
- Verify OAuth app configuration in Atlassian
- Check `JIRA_CLIENT_ID` and `JIRA_CLIENT_SECRET`
- Ensure callback URL matches exactly

### LLM returns errors
- Verify `OPENAI_API_KEY` is valid and has credits
- Check OpenAI API status
- Review prompt templates for syntax errors

### "Could not connect to Telegram" error
- Regenerate session string with `generate_session.py`
- Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [LangChain](https://github.com/langchain-ai/langchain) - LLM application framework
- [OpenAI](https://openai.com/) - GPT-4 API
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram client library
