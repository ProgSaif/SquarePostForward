import os
import re
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Get config from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
session_string = os.getenv('SESSION_STRING')
source_chat_id = os.getenv('SOURCE_CHAT_ID')
destination_channel_id = os.getenv('DESTINATION_CHANNEL_ID')

client = TelegramClient(StringSession(session_string), api_id, api_hash)

async def format_message(text):
    crypto_match = re.match(r'^([A-Z]+)', text)
    crypto_name = crypto_match.group(1) if crypto_match else "CRYPTO"
    
    amount_match = re.search(r'(\d+ \| ~[\d.]+ [A-Z]+)', text)
    usdt_match = re.search(r'(~[\d.]+ USDT)', text)
    answer_match = re.search(r'Answer:\s*(.*?)(?=\n#|$)', text, re.DOTALL)
    
    answer = answer_match.group(1).strip() if answer_match else ""
    answer = re.sub(r'copy\s*[^\w\s]*', '', answer)
    answer = re.sub(r'([!]+)', '❕', answer).strip()
    
    formatted_msg = f"❤️‍🩹 {crypto_name} ❤️‍🩹\n"
    formatted_msg += f"💎 {amount_match.group(1) if amount_match else ''}\n"
    formatted_msg += f"💰 {usdt_match.group(1) if usdt_match else ''}\n\n"
    formatted_msg += f"Answer:\n{answer}❕{answer}❕\n\n"
    formatted_msg += "#square #slot"
    
    return formatted_msg

@client.on(events.NewMessage(chats=int(source_chat_id)))
async def handler(event):
    if not event.message.media:
        formatted_message = await format_message(event.message.text)
        await client.send_message(int(destination_channel_id), formatted_message)

async def main():
    await client.start()
    print("Bot started and running...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
