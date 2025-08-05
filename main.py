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
FORBIDDEN_WORDS = ['#', 'big', 'box', '#square', '#slot', 'thxbox', 'thx', 'angelia']
VALID_NUMBERS = ['USDT', 'Answer:', '#square']
FORBIDDEN_TERMS = ['http', 't.me', '@']
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
        """Remove forbidden words while preserving EXACT original formatting"""
        # Split by lines and process each line individually
        lines = message_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Only remove whole words that exactly match forbidden words
            words = line.split(' ')
            cleaned_words = []
            
            for word in words:
                if word.strip().lower() not in [w.lower() for w in FORBIDDEN_WORDS]:
                    cleaned_words.append(word)
            
            # Reconstruct the line with original spacing
            cleaned_line = ' '.join(cleaned_words)
            cleaned_lines.append(cleaned_line)
        
        # Reconstruct with original line breaks
        return '\n'.join(cleaned_lines)

    def generate_qr_code(self, url: str) -> BytesIO:
        """Generate QR code for a given URL"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    async def handle_message(self, event):
        """Process messages while perfectly preserving formatting"""
        try:
            if not event.message.text:
                return

            message_id = event.message.id
            if message_id in self.forwarded_messages:
                return

            if self.should_forward(event.message.text):
                original_text = event.message.text
                cleaned_text = self.clean_message(original_text)
                binance_links = BINANCE_LINK_PATTERN.findall(original_text)
                
                for target in self.target_channels:
                    try:
                        if binance_links:
                            qr_buffer = self.generate_qr_code(binance_links[0])
                            # Send with original formatting and QR code
                            await self.client.send_file(
                                entity=target,
                                file=qr_buffer,
                                caption=cleaned_text,
                                parse_mode=None,  # Crucial for preserving formatting
                                link_preview=False
                            )
                        else:
                            await self.client.send_message(
                                entity=target,
                                message=cleaned_text,
                                parse_mode=None,  # Preserve original formatting
                                link_preview=False
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
