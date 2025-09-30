import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import Flask, request, jsonify, redirect, url_for
import requests
from cryptography.fernet import Fernet
import base64

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
JIRA_CLIENT_ID = os.environ.get("JIRA_CLIENT_ID", "")
JIRA_CLIENT_SECRET = os.environ.get("JIRA_CLIENT_SECRET", "")
JIRA_REDIRECT_URI = os.environ.get("JIRA_REDIRECT_URI", "https://www.briefchief.ai/auth/callback")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://auth.atlassian.com")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", Fernet.generate_key().decode())
# API key for bot authentication
API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# File to store user tokens
TOKENS_FILE = "user_tokens.json"

# Initialize encryption
fernet = Fernet(ENCRYPTION_KEY.encode())

def load_user_tokens() -> Dict[str, Dict]:
    """Load user tokens from file"""
    if os.path.exists(TOKENS_FILE):
        try:
            with open(TOKENS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
    return {}

def save_user_tokens(tokens: Dict[str, Dict]) -> None:
    """Save user tokens to file"""
    try:
        with open(TOKENS_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")

def encrypt_token(token: str) -> str:
    """Encrypt token for storage"""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt token from storage"""
    return fernet.decrypt(encrypted_token.encode()).decode()

def verify_api_key(request) -> bool:
    """Verify API key from request headers"""
    if not API_KEY:
        logger.error("INTERNAL_API_KEY not configured!")
        return False
    
    # Check Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logger.warning("Missing Authorization header")
        return False
    
    # Expected format: "Bearer <API_KEY>"
    if not auth_header.startswith('Bearer '):
        logger.warning("Invalid Authorization header format")
        return False
    
    provided_key = auth_header[7:]  # Remove "Bearer " prefix
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(provided_key, API_KEY)

def is_token_valid(token_data: Dict) -> bool:
    """Check if token is still valid"""
    if not token_data.get('expires_at'):
        return False
    
    expires_at = datetime.fromisoformat(token_data['expires_at'])
    return datetime.now() < expires_at

def refresh_token_if_needed(user_id: str, token_data: Dict) -> Optional[Dict]:
    """Refresh token if it's expired or about to expire"""
    if not token_data.get('refresh_token'):
        return None
    
    try:
        # Check if token expires in less than 5 minutes
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() + timedelta(minutes=5) < expires_at:
            return token_data  # Token is still valid
        
        # Refresh token
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': decrypt_token(token_data['refresh_token']),
            'client_id': JIRA_CLIENT_ID,
            'client_secret': JIRA_CLIENT_SECRET
        }
        
        response = requests.post(
            f"{JIRA_BASE_URL}/oauth/token",
            data=refresh_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            new_token_data = response.json()
            
            # Calculate new expiration time
            expires_in = new_token_data.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Update token data
            updated_token_data = {
                'access_token': encrypt_token(new_token_data['access_token']),
                'refresh_token': encrypt_token(new_token_data.get('refresh_token', '')),
                'expires_at': expires_at.isoformat(),
                'token_type': new_token_data.get('token_type', 'Bearer'),
                'scope': new_token_data.get('scope', ''),
                'updated_at': datetime.now().isoformat()
            }
            
            # Save updated token
            tokens = load_user_tokens()
            tokens[user_id] = updated_token_data
            save_user_tokens(tokens)
            
            logger.info(f"Token refreshed for user {user_id}")
            return updated_token_data
        else:
            logger.error(f"Failed to refresh token for user {user_id}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {e}")
        return None

@app.route('/auth/start')
def start_auth():
    """Start OAuth flow - return authorization URL to bot"""
    telegram_user_id = request.args.get('telegram_user_id')
    
    if not telegram_user_id:
        return jsonify({'error': 'telegram_user_id is required'}), 400
    
    # Store telegram_user_id in session or state parameter
    state = f"telegram_user_{telegram_user_id}"
    
    # Build authorization URL
    auth_url = (
        f"{JIRA_BASE_URL}/authorize?"
        f"client_id={JIRA_CLIENT_ID}&"
        f"redirect_uri={JIRA_REDIRECT_URI}&"
        f"response_type=code&prompt=consent&"
        f"scope=read:jira-work%20read:jira-user&"
        f"state={state}"
    )
    
    logger.info(f"Generated auth URL for telegram user {telegram_user_id}")
    
    # Return the URL instead of redirecting
    return jsonify({
        'auth_url': auth_url,
        'telegram_user_id': telegram_user_id,
        'state': state
    })

@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback from Jira"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return jsonify({'error': f'OAuth error: {error}'}), 400
    
    if not code or not state:
        return jsonify({'error': 'Missing code or state parameter'}), 400
    
    # Extract telegram_user_id from state
    if not state.startswith('telegram_user_'):
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    telegram_user_id = state.replace('telegram_user_', '')
    
    try:
        # Exchange code for token
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': JIRA_REDIRECT_URI,
            'client_id': JIRA_CLIENT_ID,
            'client_secret': JIRA_CLIENT_SECRET
        }
        
        response = requests.post(
            f"{JIRA_BASE_URL}/oauth/token",
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            token_response = response.json()
            
            # Calculate expiration time
            expires_in = token_response.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Get user information to retrieve account_id and email
            access_token = token_response['access_token']
            jira_user_info = get_jira_user_info(access_token)
            
            # Encrypt and store token
            encrypted_token_data = {
                'access_token': encrypt_token(token_response['access_token']),
                'refresh_token': encrypt_token(token_response.get('refresh_token', '')),
                'expires_at': expires_at.isoformat(),
                'token_type': token_response.get('token_type', 'Bearer'),
                'scope': token_response.get('scope', ''),
                'created_at': datetime.now().isoformat(),
                'jira_account_id': jira_user_info.get('account_id', ''),
                'jira_email': jira_user_info.get('email', ''),
                'jira_cloud_id': jira_user_info.get('cloud_id', '')
            }
            
            # Save token for user
            tokens = load_user_tokens()
            tokens[telegram_user_id] = encrypted_token_data
            save_user_tokens(tokens)
            
            logger.info(f"Successfully authenticated user {telegram_user_id}")
            
            # Return success page
            return """
            <html>
                <head>
                    <title>Jira Authorization Success</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .success { color: #28a745; }
                        .info { color: #6c757d; margin-top: 20px; }
                    </style>
                </head>
                <body>
                    <h1 class="success">✅ Authorization Successful!</h1>
                    <p>You have successfully authorized the BriefChief bot to access your Jira account.</p>
                    <p class="info">You can now close this window and return to Telegram.</p>
                    <script>
                        setTimeout(function() {
                            window.close();
                        }, 3000);
                    </script>
                </body>
            </html>
            """
        else:
            logger.error(f"Token exchange failed: {response.text}")
            return jsonify({'error': 'Token exchange failed'}), 400
            
    except Exception as e:
        logger.error(f"Error in auth callback: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/status/<telegram_user_id>')
def auth_status(telegram_user_id: str):
    """Check if user is authenticated"""
    tokens = load_user_tokens()
    
    if telegram_user_id not in tokens:
        return jsonify({'authenticated': False, 'message': 'User not authenticated'})
    
    token_data = tokens[telegram_user_id]
    
    # Try to refresh token if needed
    refreshed_token = refresh_token_if_needed(telegram_user_id, token_data)
    if refreshed_token:
        token_data = refreshed_token
    
    if is_token_valid(token_data):
        return jsonify({
            'authenticated': True,
            'expires_at': token_data['expires_at'],
            'scope': token_data['scope']
        })
    else:
        return jsonify({'authenticated': False, 'message': 'Token expired'})

@app.route('/auth/token/<telegram_user_id>')
def get_token(telegram_user_id: str):
    """Get user's Jira token and credentials for MCP server (requires API key)"""
    # Verify API key
    if not verify_api_key(request):
        logger.warning(f"Unauthorized token request for user {telegram_user_id}")
        return jsonify({'error': 'Unauthorized'}), 401
    
    tokens = load_user_tokens()
    
    if telegram_user_id not in tokens:
        return jsonify({'error': 'User not authenticated'}), 404
    
    token_data = tokens[telegram_user_id]
    
    # Try to refresh token if needed
    refreshed_token = refresh_token_if_needed(telegram_user_id, token_data)
    if refreshed_token:
        token_data = refreshed_token
    
    if is_token_valid(token_data):
        return jsonify({
            'access_token': decrypt_token(token_data['access_token']),
            'jira_account_id': token_data.get('jira_account_id', ''),
            'jira_email': token_data.get('jira_email', ''),
            'jira_cloud_id': token_data.get('jira_cloud_id', ''),
            'expires_at': token_data['expires_at']
        })
    else:
        return jsonify({'error': 'Token expired'}), 401

@app.route('/auth/revoke/<telegram_user_id>')
def revoke_auth(telegram_user_id: str):
    """Revoke user authentication"""
    tokens = load_user_tokens()
    
    if telegram_user_id in tokens:
        del tokens[telegram_user_id]
        save_user_tokens(tokens)
        logger.info(f"Revoked authentication for user {telegram_user_id}")
        return jsonify({'message': 'Authentication revoked successfully'})
    else:
        return jsonify({'message': 'User not authenticated'}), 404

def get_jira_user_info(access_token: str) -> Dict:
    """Get Jira user information using access token"""
    try:
        # First, get accessible resources (cloud IDs)
        resources_response = requests.get(
            'https://api.atlassian.com/oauth/token/accessible-resources',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if resources_response.status_code == 200:
            resources = resources_response.json()
            if resources:
                cloud_id = resources[0]['id']
                
                # Get user profile
                profile_response = requests.get(
                    f'https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if profile_response.status_code == 200:
                    profile = profile_response.json()
                    return {
                        'account_id': profile.get('accountId', ''),
                        'email': profile.get('emailAddress', ''),
                        'cloud_id': cloud_id,
                        'display_name': profile.get('displayName', '')
                    }
        
        logger.error(f"Failed to get user info: resources {resources_response.status_code}")
        return {}
    except Exception as e:
        logger.error(f"Error getting Jira user info: {e}")
        return {}

def get_user_token(telegram_user_id: str) -> Optional[str]:
    """Get valid access token for user"""
    tokens = load_user_tokens()
    
    if telegram_user_id not in tokens:
        return None
    
    token_data = tokens[telegram_user_id]
    
    # Try to refresh token if needed
    refreshed_token = refresh_token_if_needed(telegram_user_id, token_data)
    if refreshed_token:
        token_data = refreshed_token
    
    if is_token_valid(token_data):
        return decrypt_token(token_data['access_token'])
    else:
        return None

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

if __name__ == '__main__':
    # Generate encryption key if not set
    if ENCRYPTION_KEY == Fernet.generate_key().decode():
        logger.warning("ENCRYPTION_KEY not set! Generated a new one. Set it as environment variable for production.")
    
    # Check if API key is set
    if not API_KEY:
        logger.error("INTERNAL_API_KEY not set! This is required for bot authentication.")
        logger.error("Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
        import sys
        sys.exit(1)
    
    logger.info("Starting Jira Auth Server...")
    logger.info(f"Jira Base URL: {JIRA_BASE_URL}")
    logger.info(f"Redirect URI: {JIRA_REDIRECT_URI}")
    logger.info("Internal API authentication: ENABLED")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
