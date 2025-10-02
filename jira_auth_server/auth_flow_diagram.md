# Jira Authorization Flow Diagram

```
┌─────────────────┐    /auth     ┌─────────────────┐
│   Telegram Bot  │ ────────────► │  Auth Server    │
│                 │               │                 │
│ 1. User sends   │               │ 2. Generates    │
│    /auth        │               │    auth URL and │
│    command      │               │    returns JSON │
│                 │               │    response     │
└─────────────────┘               └─────────────────┘
         │                                 │
         │ JSON response                   │
         │ {auth_url: "...",               │
         │  telegram_user_id: "123"}       │
         ▼                                 │
┌─────────────────┐               ┌─────────────────┐
│   Telegram Bot  │               │      Jira       │
│                 │               │                 │
│ 3. Shows button │               │ 4. Displays     │
│    with         │               │    authorization│
│    auth_url     │               │    form         │
└─────────────────┘               └─────────────────┘
         │                                 │
         │ user clicks button              │
         ▼                                 │
┌─────────────────┐               ┌─────────────────┐
│   Web Browser   │ ◄─────────────│      Jira       │
│                 │               │                 │
│ 6. User         │               │ 5. Displays     │
│    authorizes   │               │    authorization│
│    in Jira      │               │    form         │
└─────────────────┘               └─────────────────┘
                                           │
                                           │ callback
                                           ▼
┌─────────────────┐               ┌─────────────────┐
│   Auth Server   │ ◄─────────────│      Jira       │
│                 │               │                 │
│ 8. Receives     │               │ 7. Sends        │
│    code + state │               │    code + state │
│    with user_id │               │    (user_id)    │
└─────────────────┘               └─────────────────┘
         │
         │ exchange code for token
         ▼
┌─────────────────┐
│      Jira       │
│                 │
│ 9. Exchanges    │
│    code for     │
│    access_token │
└─────────────────┘
         │
         │ token response
         ▼
┌─────────────────┐
│   Auth Server   │
│                 │
│ 10. Encrypts    │
│     and saves   │
│     token for   │
│     telegram_id │
└─────────────────┘
         │
         │ success page
         ▼
┌─────────────────┐
│   Web Browser   │
│                 │
│ 11. Shows       │
│     success and │
│     auto-closes │
└─────────────────┘

┌─────────────────┐    /brief     ┌─────────────────┐
│   Telegram Bot  │ ────────────► │  Auth Server    │
│                 │               │                 │
│ 12. User uses   │               │ 13. Verifies    │
│     /brief      │               │     authorization│
│     command     │               │     by user_id  │
└─────────────────┘               └─────────────────┘
         │
         │ if authenticated
         ▼
┌─────────────────┐
│   Telegram Bot  │
│                 │
│ 14. Executes    │
│     command     │
│     with token  │
└─────────────────┘
```

## Key Points for Passing telegram_user_id:

### 1. In OAuth `state` Parameter:
```
/auth/start?telegram_user_id=123456789
↓
state = "telegram_user_123456789"
↓
/auth/callback?code=xxx&state=telegram_user_123456789
```

### 2. Security:
- The `state` parameter prevents CSRF attacks
- Telegram ID is passed only in `state`, not in the URL
- Tokens are encrypted before storage
- State is validated on callback to ensure request authenticity

## Complete Flow Summary:

1. **User initiates**: `/auth` command in Telegram
2. **Bot requests**: Auth server for authorization URL
3. **Server generates**: URL with `state=telegram_user_{id}`
4. **Bot displays**: Authorization button with URL
5. **User clicks**: Opens browser to Jira OAuth page
6. **User authorizes**: Grants permissions to the app
7. **Jira redirects**: To callback URL with `code` and `state`
8. **Server validates**: State parameter contains telegram_user_id
9. **Server exchanges**: Authorization code for access token
10. **Server retrieves**: User information from Jira API
11. **Server encrypts**: And stores token with telegram_user_id as key
12. **Browser shows**: Success page and auto-closes
13. **Bot can access**: Jira on behalf of user with stored token

## Testing the Flow:

```bash
# 1. Start auth server
python jira_auth_server.py

# 2. Test auth initiation
curl "http://localhost:5000/auth/start?telegram_user_id=123456789"

# 3. Open returned auth_url in browser

# 4. After authorization, check callback
# Should redirect to /auth/callback?code=...&state=telegram_user_123456789

# 5. Verify token is stored
cat user_tokens.json
```
