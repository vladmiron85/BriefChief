import asyncio

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

async def generate_session_string():
    print("This script will help you generate a session string for Telethon.")
    print("You'll need your API ID and API Hash from https://my.telegram.org/apps\n")
    
    api_id = input("Enter your API ID: ")
    api_hash = input("Enter your API Hash: ")
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("API ID must be an integer.")
        return
    
    print("\nConnecting to Telegram...")
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("\nConnection successful!")
        
        bot_token = input("\nEnter your bot token (from @BotFather): ")
        if bot_token:
            await client.start(bot_token=bot_token)
            session_string = client.session.save()
            print("\nYour session string (for bot token authentication):")
            print(session_string)
            print("\nSet this as your TELEGRAM_SESSION_STRING environment variable.")
            return
        
        print("\nNo bot token provided. Proceeding with user authentication.")
        print("You'll need to log in with a phone number.")
        
        await client.start()
        session_string = client.session.save()
        
        print("\nYour session string:")
        print(session_string)
        print("\nSet this as your TELEGRAM_SESSION_STRING environment variable.")

if __name__ == "__main__":
    asyncio.run(generate_session_string())
