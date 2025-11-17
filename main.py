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
FORBIDDEN_WORDS = ['@', 'big', 'box', '#square', '#slot', 'thxbox', 'thx', 'angelia', '@GeniusCryptoFamily', '#binance']
VALID_NUMBERS = ['USDT', 'Answer:', '#square', '𝑩𝒊𝒏𝒂𝒏𝒄𝒆 𝑭𝒆𝒆𝒅', '𝑨𝒏𝒔𝒘𝒆𝒓 :']
BINANCE_LINK_PATTERN = re.compile(r'(https://app\.binance\.com/uni-qr/(?:cpos|cart)/\d+)')

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
            os.getenv('SOURCE_CHANNELS', '-1003073283086,-1002327293945').split(',') 
            if ch.strip()
        ]
        self.target_channels = [
            int(ch.strip()) for ch in 
            os.getenv('TARGET_CHANNELS', '-1003046911261').split(',') 
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

    def extract_answer(self, message_text: str) -> str:
        """Extract the answer from monospace text or specific patterns"""
        # First try to find monospace text (between backticks)
        if '`' in message_text:
            parts = message_text.split('`')
            if len(parts) >= 3:
                return parts[1].strip()
        
        # Fallback: Look for specific answer patterns
        answer_patterns = [
            r'Answer[:：]\s*([^\n]+)',
            r'𝑨𝒏𝒔𝒘𝒆𝒓[:：]\s*([^\n]+)',
            r'answer[:：]\s*([^\n]+)'
        ]
        
        for pattern in answer_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "[Answer not found in original message]"

    async def handle_message(self, event):
        """Process incoming messages with custom formatting"""
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
                answer_text = self.extract_answer(original_text)

                # Create the formatted message
                formatted_message = ""
                if binance_links:
                    formatted_message += f"[𝑩𝒊𝒏𝒂𝒏𝒄𝒆 𝑭𝒆𝒆𝒅]({binance_links[0]})\n"
                    
                formatted_message += f"        ⇣\n"
                    
                formatted_message += f"✓𝑨𝒏𝒔𝒘𝒆𝒓 : `{answer_text}`\n\n"
            
                                    
                formatted_message += f"#Binance #BinanceSquare"
                
                for target in self.target_channels:
                    try:
                        await self.client.send_message(
                            entity=target,
                            message=formatted_message,
                            parse_mode='md',
                            link_preview=False
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
