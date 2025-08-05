# Telegram Message Forwarder Bot

Forwards messages containing Binance QR links while applying strict filters.

## Features
- Only forwards messages with Binance QR links (`https://app.binance.com/uni-qr/cart/`)
- Removes all media attachments (photos, videos, QR codes)
- Applies word filters and pattern matching
- Rate limiting and queue management

## Setup
1. Get API credentials from [my.telegram.org](https://my.telegram.org)
2. Create bot via [@BotFather](https://t.me/BotFather)
3. Add environment variables (see `.env.example`)

## Deployment
### Railway
```bash
# Required environment variables:
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
SOURCE_CHANNELS=-100123,-100456
TARGET_CHANNELS=-100789,-100987
