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
        self.resolved_sources = []

    async def initialize(self):
        """Initialize channel entities with better error handling"""
        self.resolved_sources = []
        for chat_id in self.source_channels:
            try:
                entity = await self.client.get_entity(chat_id)
                self.resolved_sources.append(entity)
                logger.info(f"Successfully resolved source channel: {chat_id} (Title: {entity.title})")
            except Exception as e:
                logger.error(f"Failed to resolve channel {chat_id}: {str(e)}")
                raise

        # Verify target channels
        for chat_id in self.target_channels:
            try:
                entity = await self.client.get_entity(chat_id)
                logger.info(f"Verified target channel: {chat_id} (Title: {entity.title})")
            except Exception as e:
                logger.error(f"Failed to verify target channel {chat_id}: {str(e)}")
                raise

    def should_forward(self, message_text: str) -> bool:
        """Enhanced forwarding criteria check with logging"""
        if not message_text:
            return False

        has_binance_link = bool(BINANCE_LINK_PATTERN.search(message_text))
        has_valid_number = any(num in message_text for num in VALID_NUMBERS)
        
        logger.debug(
            f"Forwarding check:\n"
            f"Binance Link: {has_binance_link}\n"
            f"Valid Number: {has_valid_number}\n"
            f"Message Preview: {message_text[:100]}..."
        )
        
        return has_binance_link and has_valid_number

    def clean_message(self, message_text: str) -> str:
        """Preserve original message without removing any words"""
        return message_text

    def generate_qr_code(self, url: str) -> BytesIO:
        """Generate QR code with RedPacketHub centered"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="red", back_color="white").convert('RGB')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        text = "RedPacketHub"
        text_width, text_height = draw.textsize(text, font=font)
        position = ((img.size[0] - text_width) // 2, (img.size[1] - text_height) // 2)
        
        # Draw background rectangle
        draw.rectangle(
            [position[0] - 5, position[1] - 5, 
             position[0] + text_width + 5, position[1] + text_height + 5],
            fill="white"
        )
        draw.text(position, text, fill="red", font=font)
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    async def handle_message(self, event):
        """Enhanced message handler with detailed logging"""
        try:
            logger.info(f"New message detected in chat {event.chat_id}")

            if not event.message.text:
                logger.debug("Message contains no text, skipping")
                return

            message_id = event.message.id
            if message_id in self.forwarded_messages:
                logger.debug(f"Message {message_id} already forwarded")
                return

            if self.should_forward(event.message.text):
                logger.info("Message meets forwarding criteria")
                original_text = event.message.text
                binance_links = BINANCE_LINK_PATTERN.findall(original_text)
                
                if binance_links:
                    logger.info(f"Found {len(binance_links)} Binance links")
                    cleaned_text = BINANCE_LINK_PATTERN.sub(binance_links[0], original_text)
                else:
                    logger.warning("No Binance links found but passed should_forward check")
                    cleaned_text = original_text
                
                for target in self.target_channels:
                    try:
                        logger.info(f"Attempting to forward to target {target}")
                        
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
                        logger.info(f"Successfully forwarded to {target}")
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Failed to forward to {target}: {str(e)}")
            else:
                logger.debug("Message does not meet forwarding criteria")
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)

    async def run(self):
        """Main bot loop with initialization checks"""
        try:
            await self.client.start(bot_token=os.getenv('BOT_TOKEN'))
            me = await self.client.get_me()
            logger.info(f"Bot started as @{me.username} (ID: {me.id})")

            await self.initialize()
            
            @self.client.on(events.NewMessage(chats=self.resolved_sources))
            async def handler(event):
                await self.handle_message(event)

            logger.info("Bot is now actively monitoring channels")
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.critical(f"Fatal error in bot run: {str(e)}")
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
        logger.critical(f"Fatal error: {str(e)}")
