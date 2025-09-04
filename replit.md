# Bot Trading Indodax

Bot Telegram untuk trading cryptocurrency di platform Indodax dengan fitur keamanan dan tracking PnL.

## Overview
- **Tujuan**: Bot trading otomatis untuk Indodax dengan interface Telegram
- **Status**: ✅ Running dan siap digunakan
- **Keamanan**: Owner-only access dengan auto-delete messages

## Fitur Utama
- 📊 Cek harga real-time dari API Indodax
- 💰 Monitoring saldo dengan konversi IDR
- 🛒 Buy/Sell orders dengan harga market
- 🪙 Jual semua koin ke IDR otomatis
- 📜 Management order aktif
- 📈 Tracking keuntungan/rugi (PnL)
- 🔒 Auto-delete messages untuk kebersihan chat

## Cara Penggunaan
1. Start bot dengan `/start` di Telegram
2. Gunakan keyboard menu untuk navigasi
3. Format commands:
   - `/buy btc_idr 1000000` - Beli BTC senilai 1 juta IDR
   - `/sell btc_idr 0.01` - Jual 0.01 BTC
   - `/sellall btc` - Jual semua BTC ke IDR
   - `/cancel btc_idr 12345 buy` - Cancel order

## Project Architecture
- **main.py**: Core bot dengan class IndodaxAPI dan TradingBot
- **IndodaxAPI**: Handle semua API calls ke Indodax dengan HMAC-SHA512
- **TradingBot**: Interface Telegram dengan keamanan dan auto-cleanup
- **Dependencies**: pyTelegramBotAPI, requests, python-dotenv

## Recent Changes (2025-09-04)
- ✅ Setup complete project structure
- ✅ Implementasi semua fitur trading
- ✅ Added PnL tracking system
- ✅ Security dengan owner-only access
- ✅ Auto-delete messages untuk chat cleanup
- ✅ Bot running dan ready untuk live trading

## Environment Variables
- BOT_TOKEN: Token dari @BotFather
- OWNER_ID: User ID Telegram owner
- INDODAX_API_KEY: API key Indodax
- INDODAX_SECRET_KEY: Secret key Indodax

Bot stabil, aman, dan siap untuk live trading di Indodax! 🚀