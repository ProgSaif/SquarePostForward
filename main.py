import os
import re
import logging
import asyncio
import qrcode
from io import BytesIO
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
FORBIDDEN_WORDS = ['#slot', 'thxbox', 'thx', 'angelia']
VALID_NUMBERS = ['USDT', 'DOGE', 'BTTC', 'Answer:']
BINANCE_LINK_PATTERN = re.compile(r'(https://app\.binance\.com/uni-qr/cart/\d+)')

class ForwarderBot:
    def __init__(self):
        self.client = TelegramClient(
            'forwarder_session',
            int(os.getenv('API_ID')),
            os.getenv('API_HASH')
        )
        self.source_channels = [
            int(ch.strip()) for ch in 
            os.getenv('SOURCE_CHANNELS', '-1002804941127,-1002327293945').split(',') 
            if ch.strip()
        ]
        self.target_channels = [
            int(ch.strip()) for ch in 
            os.getenv('TARGET_CHANNELS', '-1002767963315,-1002361267520').split(',') 
            if ch.strip()
        ]
        self.forwarded_messages = set()

    async def initialize(self):
        """Initialize channel entities"""
        self.resolved_sources = []
        for chat_id in self.source_channels:
            try:
                entity = await self.client.get_entity(chat_id)
                self.resolved_sources.append(entity)
                logger.debug(f"Resolved source channel: {chat_id}")
            except Exception as e:
                logger.error(f"Failed to resolve channel {chat_id}: {e}")

    def should_forward(self, message_text: str) -> bool:
        """Check forwarding criteria"""
        if not BINANCE_LINK_PATTERN.search(message_text):
            return False
        return any(num in message_text for num in VALID_NUMBERS)

    def clean_message(self, message_text: str) -> str:
        """Remove forbidden words while preserving ALL formatting including monospace"""
        # Remove only complete matches of forbidden words
        for word in FORBIDDEN_WORDS:
            message_text = re.sub(
                rf'\b{re.escape(word)}\b',
                '',
                message_text,
                flags=re.IGNORECASE
            )
        return message_text

    def generate_qr_code(self, url: str) -> BytesIO:
        """Generate QR code with custom styling"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG", quality=100)
        buffer.seek(0)
        return buffer

    async def handle_message(self, event):
        """Process messages with perfect formatting preservation"""
        try:
            if not event.message.text:
                return

            message_id = event.message.id
            if message_id in self.forwarded_messages:
                return

            if self.should_forward(event.message.text):
                original_text = event.message.text
                binance_links = BINANCE_LINK_PATTERN.findall(original_text)
                
                # Keep the first Binance link in the text (will be clickable)
                if binance_links:
                    # Replace all Binance links with just the first one
                    cleaned_text = BINANCE_LINK_PATTERN.sub(binance_links[0], original_text)
                    # Still remove forbidden words
                    cleaned_text = self.clean_message(cleaned_text)
                else:
                    cleaned_text = self.clean_message(original_text)
                
                for target in self.target_channels:
                    try:
                        if binance_links:
                            qr_buffer = self.generate_qr_code(binance_links[0])
                            # Send with the original link preserved in text
                            await self.client.send_file(
                                entity=target,
                                file=qr_buffer,
                                caption=cleaned_text,
                                parse_mode='md',  # Preserves all formatting
                                link_preview=True  # This enables link embedding
                            )
                        else:
                            await self.client.send_message(
                                entity=target,
                                message=cleaned_text,
                                parse_mode='md',
                                link_preview=True  # Enable link embedding
                            )
                        
                        self.forwarded_messages.add(message_id)
                        logger.info(f"Perfectly forwarded to {target}")
                    except Exception as e:
                        logger.error(f"Forward failed to {target}: {e}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")

    async def run(self):
        """Main bot loop"""
        await self.client.start(bot_token=os.getenv('BOT_TOKEN'))
        me = await self.client.get_me()
        logger.info(f"Bot started as @{me.username}")

        await self.initialize()
        
        @self.client.on(events.NewMessage(chats=self.resolved_sources))
        async def handler(event):
            await self.handle_message(event)

        logger.info("Bot is running and monitoring channels")
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
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')))

if __name__ == '__main__':
    bot = ForwarderBot()
    Thread(target=run_web_server, daemon=True).start()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
