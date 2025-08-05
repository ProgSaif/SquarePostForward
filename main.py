import os
import re
import logging
from telethon import TelegramClient, events, types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Filter configurations
FORBIDDEN_WORDS = ['big', 'box', 'slot', 'square', 'thxbox', 'thx', 'angelia']
VALID_NUMBERS = ['Answer:', '#square']
FORBIDDEN_TERMS = ['box']
BINANCE_LINK_PATTERN = re.compile(r'https://app\.binance\.com/uni-qr/cart/\d+')

# Initialize client
client = TelegramClient('forwarder_bot', os.getenv('API_ID'), os.getenv('API_HASH'))

def should_forward(message_text):
    """Check if message meets all forwarding criteria"""
    # Must contain a Binance QR link
    if not BINANCE_LINK_PATTERN.search(message_text):
        return False
    
    # Check for valid numbers/patterns
    if not any(num in message_text for num in VALID_NUMBERS):
        return False
    
    # Check for forbidden terms
    if any(term.lower() in message_text.lower() for term in FORBIDDEN_TERMS):
        return False
    
    # Check for forbidden words (case insensitive)
    if any(re.search(rf'\b{re.escape(word)}\b', message_text, re.IGNORECASE) for word in FORBIDDEN_WORDS):
        return False
    
    return True

def clean_message(message_text):
    """Clean the message text while preserving Binance links"""
    # Remove forbidden words
    for word in FORBIDDEN_WORDS:
        message_text = re.sub(rf'\b{re.escape(word)}\b', '', message_text, flags=re.IGNORECASE)
    
    # Clean up extra spaces and empty lines
    message_text = '\n'.join(line.strip() for line in message_text.split('\n') if line.strip())
    
    return message_text.strip()

async def process_message(event):
    """Process and forward valid messages"""
    try:
        # Skip if no text content
        if not event.message.text:
            return
            
        message_text = event.message.text
        
        if should_forward(message_text):
            cleaned_text = clean_message(message_text)
            
            # Extract Binance link
            binance_link = BINANCE_LINK_PATTERN.search(message_text).group(0)
            
            # Forward to all target channels (text only)
            for target in os.getenv('TARGET_CHANNELS').split(','):
                try:
                    await client.send_message(
                        entity=int(target),
                        message=cleaned_text,
                        link_preview=False,  # Prevent link preview
                        file=None  # Remove all media
                    )
                    logging.info(f"Forwarded message with Binance link to {target}")
                except Exception as e:
                    logging.error(f"Failed to forward to {target}: {str(e)}")
        else:
            logging.info("Message didn't meet forwarding criteria")
            
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")

@client.on(events.NewMessage(chats=os.getenv('SOURCE_CHANNELS').split(',')))
async def handler(event):
    # Skip messages that are purely media (no text)
    if event.message.text or (event.message.text and event.message.media):
        await process_message(event)

async def run():
    await client.start(bot_token=os.getenv('BOT_TOKEN'))
    logging.info("Bot started and running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    client.loop.run_until_complete(run())
