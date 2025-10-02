# Jira Authorization Server

OAuth 2.0 authentication server for authorizing users in Jira.

## Setup

### 1. Environment Variables

```bash
# Jira OAuth App settings
JIRA_CLIENT_ID=your_client_id
JIRA_CLIENT_SECRET=your_client_secret
JIRA_REDIRECT_URI=http://localhost:5000/auth/callback
JIRA_BASE_URL=https://auth.atlassian.com

# Token encryption (generate a new key for production)
ENCRYPTION_KEY=your_encryption_key_here

# Internal API key for bot authentication
INTERNAL_API_KEY=your_internal_api_key_here
```

### 2. Creating OAuth App in Jira

1. Go to **[Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)**
2. Create a new OAuth 2.0 (3LO) application
3. Configure:
   - **Callback URL**: `http://localhost:5000/auth/callback` (for local development)
   - **Scopes**: `read:jira-work`, `read:jira-user`, `write:jira-work`

### 3. Installing Dependencies

```bash
pip install -r requirements.txt
```

### 4. Starting the Server

```bash
python jira_auth_server.py
```

## API Endpoints

### 1. Start Authorization
```
GET /auth/start?telegram_user_id=123456789
```

**Parameters:**
- `telegram_user_id` - User ID in Telegram

**Response:**
```json
{
  "auth_url": "https://auth.atlassian.com/oauth/authorize?...",
  "telegram_user_id": "123456789",
  "state": "telegram_user_123456789"
}
```

**Note:** The server now returns JSON with a link instead of redirecting. This allows working with a remote authorization server.

### 2. Authorization Callback
```
GET /auth/callback?code=xxx&state=telegram_user_123456789
```

**Parameters:**
- `code` - authorization code from Jira
- `state` - contains `telegram_user_id`

**Response:** HTML page with authorization result

### 3. Check Authorization Status
```
GET /auth/status/<telegram_user_id>
```

**Response:**
```json
{
  "authenticated": true,
  "expires_at": "2024-01-01T12:00:00",
  "scope": "read:jira-work read:jira-user"
}
```

### 4. Get User Token (Requires API Key)
```
GET /auth/token/<telegram_user_id>
```

**Headers:**
```
Authorization: Bearer <INTERNAL_API_KEY>
```

**Response:**
```json
{
  "access_token": "decrypted_access_token",
  "jira_account_id": "user_account_id",
  "jira_email": "user@example.com",
  "jira_cloud_id": "cloud_id",
  "expires_at": "2024-01-01T12:00:00"
}
```

### 5. Revoke Authorization
```
GET /auth/revoke/<telegram_user_id>
```

**Response:**
```json
{
  "message": "Authentication revoked successfully"
}
```

## Integration with Telegram Bot

### 1. Adding Authorization Command in bot.py

```python
async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/start?telegram_user_id={user_id}")
        
        if response.status_code == 200:
            auth_data = response.json()
            auth_url = auth_data.get('auth_url')
            
            keyboard = [
                [InlineKeyboardButton("🔐 Authorize with Jira", url=auth_url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "To use Jira features, please authorize the bot:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error getting auth URL: {e}")

# Add to main():
application.add_handler(CommandHandler("auth", auth_command))
```

### 2. Checking Authorization Before Using Jira

```python
def is_user_authenticated(telegram_user_id: str) -> bool:
    try:
        response = requests.get(f"{JIRA_AUTH_SERVER_URL}/auth/status/{telegram_user_id}")
        return response.json().get('authenticated', False)
    except:
        return False

def get_user_jira_credentials(telegram_user_id: str) -> Optional[Dict]:
    try:
        headers = {
            'Authorization': f'Bearer {INTERNAL_API_KEY}'
        }
        response = requests.get(
            f"{JIRA_AUTH_SERVER_URL}/auth/token/{telegram_user_id}",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None
```

## Security

1. **Token Encryption** - All tokens are encrypted before storage using Fernet symmetric encryption
2. **Automatic Token Refresh** - Tokens are automatically refreshed when they expire
3. **State Validation** - Validates `state` parameter to prevent CSRF attacks
4. **API Key Authentication** - Internal API requires Bearer token for accessing user credentials
5. **Constant-Time Comparison** - Uses `hmac.compare_digest` to prevent timing attacks
6. **Logging** - All operations are logged for audit trail

## Files

- `user_tokens.json` - Encrypted user tokens (automatically created)
- Logs output to console

## Usage Flow

1. User sends `/auth` command in Telegram
2. Bot displays "Authorize with Jira" button
3. User clicks button → browser opens
4. User authorizes in Jira
5. Jira redirects to `/auth/callback` with authorization code
6. Server exchanges code for access token and refresh token
7. Server retrieves user info (account ID, email, cloud ID)
8. Server encrypts and stores tokens
9. User can now use Jira features in the bot

## Token Management

### Token Storage Structure

```json
{
  "123456789": {
    "access_token": "encrypted_token",
    "refresh_token": "encrypted_refresh_token",
    "expires_at": "2024-01-01T12:00:00+00:00",
    "token_type": "Bearer",
    "scope": "read:jira-work read:jira-user",
    "created_at": "2024-01-01T10:00:00+00:00",
    "updated_at": "2024-01-01T10:00:00+00:00",
    "jira_account_id": "account_id",
    "jira_email": "user@example.com",
    "jira_cloud_id": "cloud_id"
  }
}
```

### Token Refresh

Tokens are automatically refreshed when:
- Token expires within 5 minutes
- Token is expired when requested

The refresh process:
1. Checks if refresh token exists
2. Exchanges refresh token for new access token
3. Updates stored token data
4. Returns new credentials

## Production Deployment

### Environment Setup

1. Use HTTPS for callback URLs
2. Set proper `JIRA_REDIRECT_URI` for your domain
3. Generate secure encryption keys
4. Use environment variables, not hardcoded values
5. Enable production logging

### Security Recommendations

1. **Never expose** `.env` files or `user_tokens.json`
2. **Rotate** encryption keys periodically
3. **Monitor** failed authentication attempts
4. **Implement** rate limiting on public endpoints
5. **Use** secure session storage in production
6. **Enable** HTTPS only in production
7. **Set** proper CORS policies if using web frontend

## Troubleshooting

### "INTERNAL_API_KEY not configured" error
- Make sure `INTERNAL_API_KEY` is set in `.env`
- Verify the key is the same in both bot and auth server

### "Unauthorized" when calling /auth/token
- Check `Authorization` header format: `Bearer <API_KEY>`
- Verify `INTERNAL_API_KEY` matches between services

### "Token expired" errors
- Token refresh should happen automatically
- Check if `refresh_token` is stored
- Verify Jira OAuth app has offline access

### OAuth callback fails
- Verify callback URL matches exactly in Jira OAuth app
- Check if `JIRA_CLIENT_ID` and `JIRA_CLIENT_SECRET` are correct
- Ensure auth server is accessible from the internet (for production)

## Development Tips

### Testing Locally

```bash
# Terminal 1 - Start auth server
cd jira_auth_server
python jira_auth_server.py

# Terminal 2 - Start bot
python bot.py
```

### Viewing Stored Tokens

```python
import json
with open('user_tokens.json', 'r') as f:
    tokens = json.load(f)
    print(json.dumps(tokens, indent=2))
```

### Clearing All Tokens

```bash
rm user_tokens.json
```

## Support

For issues related to:
- **OAuth flow**: Check [Atlassian OAuth 2.0 docs](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)
- **Token encryption**: See [Cryptography Fernet docs](https://cryptography.io/en/latest/fernet/)
- **Flask server**: Review [Flask documentation](https://flask.palletsprojects.com/)
