import os
import re
import logging
import asyncio
from threading import Thread
from flask import Flask, Response
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Filter configurations
FORBIDDEN_WORDS = ['big', 'box', 'slot', 'square', 'thxbox', 'thx', 'angelia']
VALID_NUMBERS = ['USDT', 'Answer:', '#square']
FORBIDDEN_TERMS = ['http', 't.me', '@']
BINANCE_LINK_PATTERN = re.compile(r'https://app\.binance\.com/uni-qr/cart/\d+')

class ForwarderBot:
    def __init__(self):
        self.client = TelegramClient(
            'forwarder_session',
            os.getenv('API_ID'),
            os.getenv('API_HASH')
        )
    
    def should_forward(self, message_text: str) -> bool:
        """Check if message meets forwarding criteria"""
        if not BINANCE_LINK_PATTERN.search(message_text):
            logger.debug("No Binance link found")
            return False
        
        if not any(num in message_text for num in VALID_NUMBERS):
            logger.debug("Missing required pattern")
            return False
        
        temp_text = BINANCE_LINK_PATTERN.sub('', message_text)
        if any(term.lower() in temp_text.lower() for term in FORBIDDEN_TERMS):
            logger.debug("Contains forbidden term")
            return False
        
        if any(re.search(rf'\b{re.escape(word)}\b', message_text, re.IGNORECASE) for word in FORBIDDEN_WORDS):
            logger.debug("Contains forbidden word")
            return False
        
        return True

    def clean_message(self, message_text: str) -> str:
        """Clean message text while preserving Binance links"""
        for word in FORBIDDEN_WORDS:
            message_text = re.sub(rf'\b{re.escape(word)}\b', '', message_text, flags=re.IGNORECASE)
        return '\n'.join(line.strip() for line in message_text.split('\n') if line.strip())

    async def handle_message(self, event):
        """Process and forward valid messages"""
        try:
            if not event.message.text:
                return
                
            message_text = event.message.text
            
            if self.should_forward(message_text):
                cleaned_text = self.clean_message(message_text)
                
                for target in os.getenv('TARGET_CHANNELS').split(','):
                    try:
                        await self.client.send_message(
                            entity=int(target),
                            message=cleaned_text,
                            link_preview=False,
                            file=None  # Remove all media
                        )
                        logger.info(f"Forwarded to {target}")
                    except Exception as e:
                        logger.error(f"Forward failed to {target}: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def run(self):
        """Start the bot"""
        await self.client.start(bot_token=os.getenv('BOT_TOKEN'))
        logger.info("Bot started successfully")
        
        @self.client.on(events.NewMessage(chats=os.getenv('SOURCE_CHANNELS').split(',')))
        async def handler(event):
            await self.handle_message(event)
        
        await self.client.run_until_disconnected()

# Health check endpoints
@app.route('/')
def home():
    return "Telegram Forwarder Bot"

@app.route('/health')
def health():
    if bot.client.is_connected():
        return Response("OK", status=200)
    return Response("Service Unavailable", status=503)

def run_web_server():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)))

if __name__ == '__main__':
    # Initialize bot
    bot = ForwarderBot()
    
    # Start Flask web server in background
    Thread(target=run_web_server, daemon=True).start()
    
    # Start Telegram client
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
