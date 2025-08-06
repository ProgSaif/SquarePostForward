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
from PIL import ImageDraw, ImageFont

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
FORBIDDEN_WORDS = ['big', 'box', '#square', '#slot', 'thxbox', 'thx', 'angelia']
VALID_NUMBERS = ['USDT', 'Answer:', '#square']
BINANCE_LINK_PATTERN = re.compile(r'(https://app\.binance\.com/uni-qr/cart/\d+)')

class ForwarderBot:
    def __init__(self):
        self.client = TelegramClient(
            os.path.join(os.getcwd(), 'forwarder_session'),
            int(os.getenv('API_ID')),
            os.getenv('API_HASH'),
            connection_retries=5,
            base_logger=logger
        )
        self.source_channels = [
            int(ch.strip()) for ch in 
            os.getenv('SOURCE_CHANNELS', '-1002804941127,-1002327293945').split(',') 
            if ch.strip()
        ]
        self.target_channels = [
            int(ch.strip()) for ch in 
            os.getenv('TARGET_CHANNELS', '-1002767963315,-1002361267520,-1002171874012').split(',') 
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
                logger.info(f"Successfully resolved source channel: {chat_id}")
            except Exception as e:
                logger.error(f"Failed to resolve channel {chat_id}: {e}")
                raise

    def should_forward(self, message_text: str) -> bool:
        """Check forwarding criteria"""
        if not message_text:
            return False
            
        has_binance = bool(BINANCE_LINK_PATTERN.search(message_text))
        has_valid = any(num in message_text for num in VALID_NUMBERS)
        
        logger.debug(f"Forward check - Binance: {has_binance}, Valid: {has_valid}")
        return has_binance and has_valid

    def generate_qr_code(self, url: str) -> BytesIO:
        """Generate QR code with RedPacketHub centered (Pillow 10+ compatible)"""
        qr = qrcode.QRCode(
            version=4,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=6,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        text = " Telegram Red Packet 🧧 Hub "
        
        # Modern Pillow 10+ compatible text measurement
        if hasattr(draw, 'textbbox'):  # Newer Pillow versions
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:  # Fallback for older versions
            text_width, text_height = draw.textsize(text, font=font)
        
        position = ((img.size[0] - text_width) // 2, (img.size[1] - text_height) // 2)
        
        # Draw background rectangle
        draw.rectangle(
            [position[0] - 10, position[1] - 10, 
             position[0] + text_width + 10, position[1] + text_height + 10],
            fill="white"
        )
        draw.text(position, text, fill="black", font=font)
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    async def handle_message(self, event):
        """Process incoming messages"""
        try:
            logger.info(f"New message from chat {event.chat_id}")

            if not event.message.text:
                logger.debug("No text content, skipping")
                return

            message_id = event.message.id
            if message_id in self.forwarded_messages:
                logger.debug("Message already forwarded")
                return

            if self.should_forward(event.message.text):
                logger.info("Message meets forwarding criteria")
                original_text = event.message.text
                binance_links = BINANCE_LINK_PATTERN.findall(original_text)
                
                cleaned_text = BINANCE_LINK_PATTERN.sub(
                    binance_links[0] if binance_links else '', 
                    original_text
                )
                
                for target in self.target_channels:
                    try:
                        if binance_links:
                            qr_buffer = self.generate_qr_code(binance_links[0])
                            await self.client.send_file(
                                entity=target,
                                file=qr_buffer,
                                caption=cleaned_text,
                                parse_mode='md',
                                link_preview=True
                            )
                        else:
                            await self.client.send_message(
                                entity=target,
                                message=cleaned_text,
                                parse_mode='md',
                                link_preview=True
                            )
                        
                        self.forwarded_messages.add(message_id)
                        logger.info(f"Forwarded to {target}")
                        
                        # Rate limiting protection
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Forward failed to {target}: {e}")
            else:
                logger.debug("Message doesn't meet criteria")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def run(self):
        """Main bot loop"""
        try:
            # Connection with retries
            for attempt in range(3):
                try:
                    await self.client.start(bot_token=os.getenv('BOT_TOKEN'))
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(5)
            
            me = await self.client.get_me()
            logger.info(f"Bot started as @{me.username}")

            await self.initialize()
            
            @self.client.on(events.NewMessage(chats=self.resolved_sources))
            async def handler(event):
                await self.handle_message(event)

            logger.info("Bot is monitoring channels")
            
            # Keep-alive for Railway
            while True:
                await asyncio.sleep(3600)
                
        except Exception as e:
            logger.critical(f"Bot crashed: {e}")
            await self.client.disconnect()
            raise

# Health check endpoints
@app.route('/')
def home():
    return "Telegram Forwarder Bot - Operational"

@app.route('/health')
def health():
    if bot.client.is_connected():
        return Response("OK", status=200)
    return Response("Service Unavailable", status=503)

@app.route('/status')
def status():
    return {
        'status': 'running',
        'connected': bot.client.is_connected(),
        'sources': len(bot.resolved_sources),
        'targets': len(bot.target_channels)
    }

def run_web_server():
    port = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    bot = ForwarderBot()
    Thread(target=run_web_server, daemon=True).start()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
