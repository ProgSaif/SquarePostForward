from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Session string:", client.session.save())
