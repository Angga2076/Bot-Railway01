import os
import time
import hashlib
import hmac
import json
import requests
from typing import Dict, Any, Optional
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class IndodaxAPI:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://indodax.com"
        
    def _get_signature(self, params: str) -> str:
        """Generate HMAC-SHA512 signature for private API calls"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
    
    def _private_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make private API request with authentication"""
        if params is None:
            params = {}
            
        params['method'] = method
        params['timestamp'] = str(int(time.time() * 1000))
        params['recvWindow'] = '5000'
        
        # Create query string
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        
        # Generate signature
        signature = self._get_signature(query_string)
        
        headers = {
            'Key': self.api_key,
            'Sign': signature,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/tapi",
                headers=headers,
                data=query_string,
                timeout=30
            )
            return response.json()
        except Exception as e:
            return {'success': 0, 'error': str(e)}
    
    def get_ticker(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """Get ticker prices (public API)"""
        try:
            if pair:
                url = f"{self.base_url}/api/ticker/{pair}"
            else:
                url = f"{self.base_url}/api/ticker_all"
            
            response = requests.get(url, timeout=30)
            return response.json()
        except Exception as e:
            return {'error': str(e)}
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        return self._private_request('getInfo')
    
    def create_order(self, pair: str, order_type: str, price: float, amount: float, amount_type: str = 'idr') -> Dict[str, Any]:
        """Create buy/sell order sesuai dokumentasi Indodax"""
        params = {
            'pair': pair,
            'type': order_type,
            'price': str(price)
        }
        
        # Berdasarkan dokumentasi Indodax:
        # - Untuk buy: gunakan 'idr' (IDR amount) atau nama coin (coin amount)
        # - Untuk sell: gunakan nama coin (coin amount)
        coin_name = pair.split('_')[0]  # Extract coin name from pair (e.g., 'btc' from 'btc_idr')
        
        if order_type == 'buy':
            if amount_type == 'idr':
                params['idr'] = str(amount)  # Amount in IDR
            else:
                params[coin_name] = str(amount)  # Amount in coin
        else:  # sell
            params[coin_name] = str(amount)  # Amount in coin for selling
        
        return self._private_request('trade', params)
    
    def get_open_orders(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """Get open orders"""
        params = {}
        if pair:
            params['pair'] = pair
        return self._private_request('openOrders', params)
    
    def cancel_order(self, pair: str, order_id: str, order_type: str) -> Dict[str, Any]:
        """Cancel order"""
        params = {
            'pair': pair,
            'order_id': order_id,
            'type': order_type
        }
        return self._private_request('cancelOrder', params)
    
    def get_trade_history(self, pair: Optional[str] = None, count: int = 100) -> Dict[str, Any]:
        """Get trade history"""
        params = {'count': str(count)}
        if pair:
            params['pair'] = pair
        return self._private_request('tradeHistory', params)

class TradingBot:
    def __init__(self):
        # Initialize bot token and API credentials
        self.bot_token = os.getenv('BOT_TOKEN') or ''
        self.owner_id = int(os.getenv('OWNER_ID', '0'))
        self.api_key = os.getenv('INDODAX_API_KEY') or ''
        self.secret_key = os.getenv('INDODAX_SECRET_KEY') or ''
        
        if not all([self.bot_token, self.owner_id, self.api_key, self.secret_key]):
            raise ValueError("Missing required environment variables")
        
        self.bot = telebot.TeleBot(self.bot_token)
        self.indodax = IndodaxAPI(self.api_key, self.secret_key)
        
        # PnL tracking storage (in production, use database)
        self.pnl_data = {}
        
        self.setup_handlers()
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is the owner"""
        return user_id == self.owner_id
    
    def delete_message_safe(self, chat_id: int, message_id: int):
        """Safely delete message"""
        try:
            self.bot.delete_message(chat_id, message_id)
        except:
            pass
    
    def create_coin_keyboard(self) -> ReplyKeyboardMarkup:
        """Create coin selection keyboard"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        
        # Top coins berdasarkan volume
        coins = [
            KeyboardButton("💎 USDT"), KeyboardButton("⚡ ETH"), KeyboardButton("₿ BTC"),
            KeyboardButton("🚀 SOL"), KeyboardButton("💧 XRP"), KeyboardButton("🐕 DOGE"),
            KeyboardButton("🔗 LINK"), KeyboardButton("🎴 ADA"), KeyboardButton("🟡 BNB"),
            KeyboardButton("💵 USDC"), KeyboardButton("⚡ TRX"), KeyboardButton("🪙 LTC")
        ]
        
        # Add coins in rows of 3
        for i in range(0, len(coins), 3):
            keyboard.row(*coins[i:i+3])
        
        # Back button
        keyboard.row(KeyboardButton("🔙 Kembali"))
        
        return keyboard
    
    def create_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        # Row 1: Info
        keyboard.row(
            KeyboardButton("📊 Harga Koin"),
            KeyboardButton("💰 Cek Saldo")
        )
        
        # Row 2: SOL Trading Cepat
        keyboard.row(
            KeyboardButton("🚀 Beli SOL"),
            KeyboardButton("💸 Jual SOL")
        )
        
        # Row 3: All Trading
        keyboard.row(
            KeyboardButton("💰 Beli All IDR"),
            KeyboardButton("🪙 Jual All ke IDR")
        )
        
        # Row 4: Manual Trading
        keyboard.row(
            KeyboardButton("🛒 Beli Manual"),
            KeyboardButton("💵 Jual Manual")
        )
        
        # Row 5: Orders & PnL
        keyboard.row(
            KeyboardButton("📜 Order Aktif"),
            KeyboardButton("📈 PnL")
        )
        
        # Row 6: Cancel
        keyboard.row(
            KeyboardButton("❌ Cancel Order")
        )
        
        return keyboard
    
    def format_number(self, num: float) -> str:
        """Format number with proper decimal places"""
        if num >= 1:
            return f"{num:,.2f}"
        else:
            return f"{num:.8f}".rstrip('0').rstrip('.')
    
    def get_harga_koin(self) -> str:
        """Get coin prices from Indodax"""
        try:
            ticker_data = self.indodax.get_ticker()
            
            if 'tickers' not in ticker_data:
                return "❌ Gagal mengambil data harga"
            
            message = "📊 *Harga Koin Terkini*\n\n"
            
            # Main coins berdasarkan data Indodax aktual (volume terbesar)
            main_pairs = ['usdt_idr', 'eth_idr', 'btc_idr', 'sol_idr', 'xrp_idr', 'doge_idr', 'link_idr', 'ada_idr', 'bnb_idr', 'usdc_idr']
            
            for pair in main_pairs:
                if pair in ticker_data['tickers']:
                    data = ticker_data['tickers'][pair]
                    last_price = float(data['last'])
                    
                    coin = pair.split('_')[0].upper()
                    message += f"*{coin}/IDR*: Rp {self.format_number(last_price)}\n"
            
            message += f"\n🕐 Update: {time.strftime('%H:%M:%S')}"
            return message
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def cek_saldo_detail(self) -> str:
        """Get detailed balance with IDR conversion"""
        try:
            balance_data = self.indodax.get_balance()
            
            if balance_data.get('success') != 1:
                return f"❌ Gagal cek saldo: {balance_data.get('error', 'Unknown error')}"
            
            balances = balance_data['return']['balance']
            
            # Get current prices for conversion
            ticker_data = self.indodax.get_ticker()
            
            message = "💰 *Saldo Akun*\n\n"
            
            # IDR balance
            idr_balance = float(balances.get('idr', 0))
            message += f"💵 *IDR*: Rp {self.format_number(idr_balance)}\n\n"
            
            total_idr_value = idr_balance
            
            # Crypto balances berdasarkan data Indodax aktual
            crypto_coins = ['usdt', 'eth', 'btc', 'sol', 'xrp', 'doge', 'link', 'ada', 'bnb', 'usdc', 'trx', 'ltc', 'avax', 'dot', 'bch', 'sui', 'hbar', 'arb', 'pol', 'xlm']
            
            for coin in crypto_coins:
                balance = float(balances.get(coin, 0))
                if balance > 0:
                    message += f"₿ *{coin.upper()}*: {self.format_number(balance)}\n"
                    
                    # Convert to IDR
                    pair = f"{coin}_idr"
                    if 'tickers' in ticker_data and pair in ticker_data['tickers']:
                        price = float(ticker_data['tickers'][pair]['last'])
                        idr_value = balance * price
                        total_idr_value += idr_value
                        message += f"   └ ≈ Rp {self.format_number(idr_value)}\n"
                    
                    message += "\n"
            
            message += f"💎 *Total Aset*: Rp {self.format_number(total_idr_value)}"
            return message
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def jual_semua(self, coin: str) -> str:
        """Sell all coins to IDR"""
        try:
            # Get balance
            balance_data = self.indodax.get_balance()
            if balance_data.get('success') != 1:
                return f"❌ Gagal cek saldo: {balance_data.get('error', 'Unknown error')}"
            
            balances = balance_data['return']['balance']
            coin_balance = float(balances.get(coin.lower(), 0))
            
            if coin_balance <= 0:
                return f"❌ Tidak ada saldo {coin.upper()}"
            
            # Get current market price
            pair = f"{coin.lower()}_idr"
            ticker_data = self.indodax.get_ticker(pair)
            
            if 'ticker' not in ticker_data:
                return f"❌ Gagal get harga {pair}"
            
            # Use bid price for selling (market sell price)
            bid_price = float(ticker_data['ticker']['buy'])
            
            # Create sell order dengan harga market
            result = self.indodax.create_order(pair, 'sell', bid_price, coin_balance, 'coin')
            
            if result.get('success') == 1:
                estimated_idr = coin_balance * bid_price
                return (f"✅ *Jual Semua {coin.upper()} Berhasil*\n\n"
                       f"🪙 Jumlah: {self.format_number(coin_balance)} {coin.upper()}\n"
                       f"💰 Harga Market: Rp {self.format_number(bid_price)}\n"
                       f"💵 Estimasi IDR: Rp {self.format_number(estimated_idr)}\n"
                       f"📋 Order ID: {result['return']['order_id']}")
            else:
                return f"❌ Gagal jual: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def beli_semua_idr(self, coin: str) -> str:
        """Buy coin using all available IDR balance"""
        try:
            # Get balance
            balance_data = self.indodax.get_balance()
            if balance_data.get('success') != 1:
                return f"❌ Gagal cek saldo: {balance_data.get('error', 'Unknown error')}"
            
            balances = balance_data['return']['balance']
            idr_balance = float(balances.get('idr', 0))
            
            if idr_balance <= 10000:  # Minimum 10k IDR
                return f"❌ Saldo IDR tidak mencukupi. Minimum Rp 10,000\nSaldo saat ini: Rp {self.format_number(idr_balance)}"
            
            # Get current market price
            pair = f"{coin.lower()}_idr"
            ticker_data = self.indodax.get_ticker(pair)
            
            if 'ticker' not in ticker_data:
                return f"❌ Gagal get harga {pair}"
            
            # Use ask price for buying (market buy price)
            ask_price = float(ticker_data['ticker']['sell'])
            
            # Calculate estimated coin amount (with small buffer for fees)
            estimated_coin = (idr_balance * 0.998) / ask_price  # 0.2% buffer for fees
            
            # Create buy order dengan semua saldo IDR
            result = self.indodax.create_order(pair, 'buy', ask_price, idr_balance, 'idr')
            
            if result.get('success') == 1:
                return (f"✅ *Beli {coin.upper()} dengan Semua IDR Berhasil*\n\n"
                       f"💵 Total IDR: Rp {self.format_number(idr_balance)}\n"
                       f"💰 Harga Market: Rp {self.format_number(ask_price)}\n"
                       f"🪙 Estimasi {coin.upper()}: {self.format_number(estimated_coin)}\n"
                       f"📋 Order ID: {result['return']['order_id']}")
            else:
                return f"❌ Gagal beli: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def hitung_pnl(self) -> str:
        """Calculate PnL from trade history"""
        try:
            trade_history = self.indodax.get_trade_history()
            
            if trade_history.get('success') != 1:
                return f"❌ Gagal get trade history: {trade_history.get('error', 'Unknown error')}"
            
            trades = trade_history['return']['trades']
            
            if not trades:
                return "📈 Belum ada transaksi"
            
            message = "📈 *Analisis PnL*\n\n"
            
            # Group trades by pair
            pair_trades = {}
            for trade in trades:
                pair = trade['pair']
                if pair not in pair_trades:
                    pair_trades[pair] = {'buys': [], 'sells': []}
                
                trade_data = {
                    'price': float(trade['price']),
                    'amount': float(trade['amount']),
                    'fee': float(trade['fee']),
                    'date': trade['trade_time']
                }
                
                if trade['type'] == 'buy':
                    pair_trades[pair]['buys'].append(trade_data)
                else:
                    pair_trades[pair]['sells'].append(trade_data)
            
            total_pnl = 0
            
            for pair, data in pair_trades.items():
                buys = data['buys']
                sells = data['sells']
                
                if not buys and not sells:
                    continue
                
                coin = pair.split('_')[0].upper()
                
                # Calculate average buy price
                total_buy_amount = sum(t['amount'] for t in buys)
                total_buy_cost = sum(t['price'] * t['amount'] + t['fee'] for t in buys)
                avg_buy_price = total_buy_cost / total_buy_amount if total_buy_amount > 0 else 0
                
                # Calculate average sell price
                total_sell_amount = sum(t['amount'] for t in sells)
                total_sell_value = sum(t['price'] * t['amount'] - t['fee'] for t in sells)
                avg_sell_price = total_sell_value / total_sell_amount if total_sell_amount > 0 else 0
                
                if total_sell_amount > 0 and avg_buy_price > 0:
                    pnl_per_unit = avg_sell_price - avg_buy_price
                    total_pnl_pair = pnl_per_unit * total_sell_amount
                    pnl_percentage = (pnl_per_unit / avg_buy_price) * 100
                    
                    total_pnl += total_pnl_pair
                    
                    status = "📈" if total_pnl_pair > 0 else "📉"
                    
                    message += f"{status} *{coin}*\n"
                    message += f"   Buy: Rp {self.format_number(avg_buy_price)}\n"
                    message += f"   Sell: Rp {self.format_number(avg_sell_price)}\n"
                    message += f"   PnL: {pnl_percentage:+.2f}% (Rp {self.format_number(total_pnl_pair)})\n\n"
            
            status_icon = "📈" if total_pnl > 0 else "📉"
            message += f"{status_icon} *Total PnL*: Rp {self.format_number(total_pnl)}"
            
            return message
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def setup_handlers(self):
        """Setup bot message handlers"""
        
        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            # Delete user's command
            self.delete_message_safe(message.chat.id, message.message_id)
            
            if not self.is_owner(message.from_user.id):
                msg = self.bot.send_message(message.chat.id, "❌ Kamu tidak punya akses ke bot ini")
                time.sleep(2)
                self.delete_message_safe(message.chat.id, msg.message_id)
                return
            
            welcome_text = (
                f"🤖 *Bot Trading Indodax*\n\n"
                f"Selamat datang, {message.from_user.first_name}!\n"
                f"Pilih menu di bawah untuk mulai trading:"
            )
            
            self.bot.send_message(
                message.chat.id,
                welcome_text,
                parse_mode='Markdown',
                reply_markup=self.create_main_keyboard()
            )
        
        @self.bot.message_handler(func=lambda message: True)
        def message_handler(message):
            # Initialize last_action if not exists
            if not hasattr(self, 'last_action'):
                self.last_action = None
            # Delete user's message
            self.delete_message_safe(message.chat.id, message.message_id)
            
            if not self.is_owner(message.from_user.id):
                msg = self.bot.send_message(message.chat.id, "❌ Kamu tidak punya akses ke bot ini")
                time.sleep(2)
                self.delete_message_safe(message.chat.id, msg.message_id)
                return
            
            text = message.text
            response = ""
            
            if text == "📊 Harga Koin":
                response = self.get_harga_koin()
                
            elif text == "🚀 Beli SOL":
                response = self.beli_semua_idr('sol')
                
            elif text == "💸 Jual SOL":
                response = self.jual_semua('sol')
                
            elif text == "💰 Beli All IDR":
                self.last_action = 'buy_all'
                msg = self.bot.send_message(
                    message.chat.id,
                    "💰 *Pilih Koin untuk Beli dengan Semua IDR:*",
                    parse_mode='Markdown',
                    reply_markup=self.create_coin_keyboard()
                )
                return
                
            elif text == "🪙 Jual All ke IDR":
                self.last_action = 'sell_all'
                msg = self.bot.send_message(
                    message.chat.id,
                    "🪙 *Pilih Koin untuk Jual Semua ke IDR:*",
                    parse_mode='Markdown',
                    reply_markup=self.create_coin_keyboard()
                )
                return
                
            elif text == "🛒 Beli Manual":
                response = ("🛒 *Beli Koin Manual*\n\n"
                           "Format: /buy [pair] [jumlah_idr]\n"
                           "Contoh: /buy btc_idr 1000000\n\n"
                           "Top pairs: usdt_idr, eth_idr, btc_idr, sol_idr, xrp_idr")
                
            elif text == "💵 Jual Manual":
                response = ("💵 *Jual Koin Manual*\n\n"
                           "Format: /sell [pair] [jumlah_koin]\n"
                           "Contoh: /sell btc_idr 0.01\n\n"
                           "Top pairs: usdt_idr, eth_idr, btc_idr, sol_idr, xrp_idr")
                
            elif text == "📈 PnL":
                response = self.hitung_pnl()
                
            # Handle coin selection buttons
            elif text in ["💎 USDT", "⚡ ETH", "₿ BTC", "🚀 SOL", "💧 XRP", "🐕 DOGE", "🔗 LINK", "🎴 ADA", "🟡 BNB", "💵 USDC", "⚡ TRX", "🪙 LTC"]:
                # Extract coin name from emoji text
                coin_map = {
                    "💎 USDT": "usdt", "⚡ ETH": "eth", "₿ BTC": "btc", "🚀 SOL": "sol",
                    "💧 XRP": "xrp", "🐕 DOGE": "doge", "🔗 LINK": "link", "🎴 ADA": "ada",
                    "🟡 BNB": "bnb", "💵 USDC": "usdc", "⚡ TRX": "trx", "🪙 LTC": "ltc"
                }
                
                coin = coin_map.get(text, "sol")
                
                # Check context from last action
                if hasattr(self, 'last_action') and self.last_action == 'buy_all':
                    response = self.beli_semua_idr(coin)
                    self.last_action = None
                elif hasattr(self, 'last_action') and self.last_action == 'sell_all':
                    response = self.jual_semua(coin)
                    self.last_action = None
                else:
                    # Default to show coin info
                    ticker_data = self.indodax.get_ticker(f"{coin}_idr")
                    if 'ticker' in ticker_data:
                        price = float(ticker_data['ticker']['last'])
                        response = f"💰 *{coin.upper()}/IDR*: Rp {self.format_number(price)}\n\nGunakan tombol menu untuk trading!"
                    else:
                        response = f"❌ Gagal get harga {coin.upper()}"
                        
            elif text == "🔙 Kembali":
                response = "🔙 Kembali ke menu utama"
                
            elif text == "💰 Cek Saldo":
                response = self.cek_saldo_detail()
                
            elif text.startswith('/sol'):
                # Shortcut commands untuk Solana
                if text == '/solbuy':
                    response = ("🚀 *Beli Solana (SOL)*\n\n"
                               "Format cepat:\n"
                               "/solbuy [jumlah_idr] - Beli SOL dengan IDR\n"
                               "/solbuyall - Beli SOL dengan semua saldo IDR\n\n"
                               "Contoh: /solbuy 1000000")
                elif text == '/solsell':
                    response = ("🚀 *Jual Solana (SOL)*\n\n"
                               "Format cepat:\n"
                               "/solsell [jumlah_sol] - Jual SOL ke IDR\n"
                               "/solsellall - Jual semua SOL ke IDR\n\n"
                               "Contoh: /solsell 1.5")
                elif text == '/solbuyall':
                    response = self.beli_semua_idr('sol')
                elif text == '/solsellall':
                    response = self.jual_semua('sol')
                elif text.startswith('/solbuy '):
                    try:
                        parts = text.split()
                        if len(parts) != 2:
                            response = "❌ Format salah. Gunakan: /solbuy [jumlah_idr]"
                        else:
                            amount_idr = float(parts[1])
                            ticker_data = self.indodax.get_ticker('sol_idr')
                            if 'ticker' in ticker_data:
                                ask_price = float(ticker_data['ticker']['sell'])
                                result = self.indodax.create_order('sol_idr', 'buy', ask_price, amount_idr, 'idr')
                                if result.get('success') == 1:
                                    coin_amount = amount_idr / ask_price
                                    response = (f"✅ *Beli SOL Berhasil*\n\n"
                                              f"🪙 Pair: SOL/IDR\n"
                                              f"💰 Harga: Rp {self.format_number(ask_price)}\n"
                                              f"💵 Total IDR: Rp {self.format_number(amount_idr)}\n"
                                              f"🎯 Estimasi SOL: {self.format_number(coin_amount)}\n"
                                              f"📋 Order ID: {result['return']['order_id']}")
                                else:
                                    response = f"❌ Gagal beli SOL: {result.get('error', 'Unknown error')}"
                            else:
                                response = "❌ Gagal get harga SOL"
                    except ValueError:
                        response = "❌ Jumlah harus berupa angka"
                    except Exception as e:
                        response = f"❌ Error: {str(e)}"
                elif text.startswith('/solsell '):
                    try:
                        parts = text.split()
                        if len(parts) != 2:
                            response = "❌ Format salah. Gunakan: /solsell [jumlah_sol]"
                        else:
                            amount_sol = float(parts[1])
                            ticker_data = self.indodax.get_ticker('sol_idr')
                            if 'ticker' in ticker_data:
                                bid_price = float(ticker_data['ticker']['buy'])
                                result = self.indodax.create_order('sol_idr', 'sell', bid_price, amount_sol, 'coin')
                                if result.get('success') == 1:
                                    idr_amount = amount_sol * bid_price
                                    response = (f"✅ *Jual SOL Berhasil*\n\n"
                                              f"🪙 Pair: SOL/IDR\n"
                                              f"💰 Harga: Rp {self.format_number(bid_price)}\n"
                                              f"🎯 Jumlah SOL: {self.format_number(amount_sol)}\n"
                                              f"💵 Estimasi IDR: Rp {self.format_number(idr_amount)}\n"
                                              f"📋 Order ID: {result['return']['order_id']}")
                                else:
                                    response = f"❌ Gagal jual SOL: {result.get('error', 'Unknown error')}"
                            else:
                                response = "❌ Gagal get harga SOL"
                    except ValueError:
                        response = "❌ Jumlah harus berupa angka"
                    except Exception as e:
                        response = f"❌ Error: {str(e)}"
                else:
                    response = ("🚀 *Solana (SOL) Trading*\n\n"
                               "Commands cepat:\n"
                               "/solbuy [idr] - Beli SOL\n"
                               "/solsell [sol] - Jual SOL\n"
                               "/solbuyall - Beli dengan semua IDR\n"
                               "/solsellall - Jual semua SOL\n\n"
                               "Contoh:\n"
                               "/solbuy 1000000\n"
                               "/solsell 2.5\n"
                               "/solbuyall\n"
                               "/solsellall")
                
            elif text == "🛒 Beli Koin":
                response = ("🛒 *Beli Koin*\n\n"
                           "Format: /buy [pair] [jumlah_idr]\n"
                           "Contoh: /buy btc_idr 1000000\n\n"
                           "Top pairs: usdt_idr, eth_idr, btc_idr, sol_idr, xrp_idr\n"
                           "Shortcut: /solbuy, /buyall [coin]")
                
            elif text == "💵 Jual Koin":
                response = ("💵 *Jual Koin*\n\n"
                           "Format: /sell [pair] [jumlah_koin]\n"
                           "Contoh: /sell btc_idr 0.01\n\n"
                           "Top pairs: usdt_idr, eth_idr, btc_idr, sol_idr, xrp_idr\n"
                           "Shortcut: /solsell, /sellall [coin]")
                
            elif text == "🪙 Jual Semua ke IDR":
                response = ("🪙 *Trading Cepat*\n\n"
                           "📤 *Jual Semua:*\n"
                           "Format: /sellall [koin]\n"
                           "Contoh: /sellall sol\n\n"
                           "📥 *Beli dengan Semua IDR:*\n"
                           "Format: /buyall [koin]\n"
                           "Contoh: /buyall sol\n\n"
                           "🪙 Top coins: usdt, eth, btc, sol, xrp, doge, link, ada, bnb, usdc")
                
            elif text == "📜 Order Aktif":
                try:
                    orders = self.indodax.get_open_orders()
                    if orders.get('success') == 1:
                        open_orders = orders['return']['orders']
                        if not open_orders:
                            response = "📜 Tidak ada order aktif"
                        else:
                            response = "📜 *Order Aktif*\n\n"
                            for order in open_orders:
                                response += (f"🔸 {order['pair'].upper()}\n"
                                           f"   Type: {order['type']}\n"
                                           f"   Price: Rp {self.format_number(float(order['price']))}\n"
                                           f"   Amount: {self.format_number(float(order['remain_amount']))}\n"
                                           f"   ID: {order['order_id']}\n\n")
                    else:
                        response = f"❌ Gagal get orders: {orders.get('error', 'Unknown error')}"
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                
            elif text == "❌ Cancel Order":
                response = ("❌ *Cancel Order*\n\n"
                           "Format: /cancel [pair] [order_id] [type]\n"
                           "Contoh: /cancel btc_idr 12345 buy")
                
            elif text == "📈 Keuntungan/Rugi (PnL)":
                response = self.hitung_pnl()
                
            elif text.startswith('/buy '):
                try:
                    parts = text.split()
                    if len(parts) != 3:
                        response = "❌ Format salah. Gunakan: /buy [pair] [jumlah_idr]"
                    else:
                        pair = parts[1].lower()
                        amount_idr = float(parts[2])
                        
                        # Get current price
                        ticker_data = self.indodax.get_ticker(pair)
                        if 'ticker' not in ticker_data:
                            response = f"❌ Pair {pair} tidak valid"
                        else:
                            ask_price = float(ticker_data['ticker']['sell'])
                            
                            result = self.indodax.create_order(pair, 'buy', ask_price, amount_idr, 'idr')
                            
                            if result.get('success') == 1:
                                coin_amount = amount_idr / ask_price
                                response = (f"✅ *Order Buy Berhasil*\n\n"
                                          f"🪙 Pair: {pair.upper()}\n"
                                          f"💰 Harga: Rp {self.format_number(ask_price)}\n"
                                          f"💵 Total IDR: Rp {self.format_number(amount_idr)}\n"
                                          f"🎯 Estimasi Koin: {self.format_number(coin_amount)}")
                            else:
                                response = f"❌ Gagal buy: {result.get('error', 'Unknown error')}"
                                
                except ValueError:
                    response = "❌ Jumlah harus berupa angka"
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                    
            elif text.startswith('/sell '):
                try:
                    parts = text.split()
                    if len(parts) != 3:
                        response = "❌ Format salah. Gunakan: /sell [pair] [jumlah_koin]"
                    else:
                        pair = parts[1].lower()
                        amount_coin = float(parts[2])
                        
                        # Get current price
                        ticker_data = self.indodax.get_ticker(pair)
                        if 'ticker' not in ticker_data:
                            response = f"❌ Pair {pair} tidak valid"
                        else:
                            bid_price = float(ticker_data['ticker']['buy'])
                            
                            result = self.indodax.create_order(pair, 'sell', bid_price, amount_coin, 'coin')
                            
                            if result.get('success') == 1:
                                idr_amount = amount_coin * bid_price
                                response = (f"✅ *Order Sell Berhasil*\n\n"
                                          f"🪙 Pair: {pair.upper()}\n"
                                          f"💰 Harga: Rp {self.format_number(bid_price)}\n"
                                          f"🎯 Jumlah Koin: {self.format_number(amount_coin)}\n"
                                          f"💵 Estimasi IDR: Rp {self.format_number(idr_amount)}")
                            else:
                                response = f"❌ Gagal sell: {result.get('error', 'Unknown error')}"
                                
                except ValueError:
                    response = "❌ Jumlah harus berupa angka"
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                    
            elif text.startswith('/sellall '):
                try:
                    parts = text.split()
                    if len(parts) != 2:
                        response = "❌ Format salah. Gunakan: /sellall [koin]"
                    else:
                        coin = parts[1].lower()
                        supported_coins = ['usdt', 'eth', 'btc', 'sol', 'xrp', 'doge', 'link', 'ada', 'bnb', 'usdc', 'trx', 'ltc', 'avax', 'dot', 'bch', 'sui', 'hbar', 'arb', 'pol', 'xlm']
                        if coin in supported_coins:
                            response = self.jual_semua(coin)
                        else:
                            response = f"❌ Koin tidak didukung. Top coins: {', '.join(supported_coins[:10])}..."
                        
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                    
            elif text.startswith('/buyall '):
                try:
                    parts = text.split()
                    if len(parts) != 2:
                        response = "❌ Format salah. Gunakan: /buyall [koin]"
                    else:
                        coin = parts[1].lower()
                        supported_coins = ['usdt', 'eth', 'btc', 'sol', 'xrp', 'doge', 'link', 'ada', 'bnb', 'usdc', 'trx', 'ltc', 'avax', 'dot', 'bch', 'sui', 'hbar', 'arb', 'pol', 'xlm']
                        if coin in supported_coins:
                            response = self.beli_semua_idr(coin)
                        else:
                            response = f"❌ Koin tidak didukung. Top coins: {', '.join(supported_coins[:10])}..."
                        
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                    
            elif text.startswith('/cancel '):
                try:
                    parts = text.split()
                    if len(parts) != 4:
                        response = "❌ Format salah. Gunakan: /cancel [pair] [order_id] [type]"
                    else:
                        pair = parts[1].lower()
                        order_id = parts[2]
                        order_type = parts[3].lower()
                        
                        result = self.indodax.cancel_order(pair, order_id, order_type)
                        
                        if result.get('success') == 1:
                            response = f"✅ Order {order_id} berhasil dibatalkan"
                        else:
                            response = f"❌ Gagal cancel order: {result.get('error', 'Unknown error')}"
                            
                except Exception as e:
                    response = f"❌ Error: {str(e)}"
                    
            else:
                response = "❌ Menu tidak dikenal. Gunakan keyboard di bawah."
            
            if response:
                msg = self.bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=self.create_main_keyboard()
                )
                
                # Auto delete after 30 seconds for price/balance updates
                if text in ["📊 Harga Koin", "💰 Cek Saldo"]:
                    time.sleep(30)
                    self.delete_message_safe(message.chat.id, msg.message_id)
    
    def run(self):
        """Start the bot"""
        print("🤖 Bot Trading Indodax started...")
        self.bot.infinity_polling(none_stop=True)

if __name__ == "__main__":
    try:
        bot = TradingBot()
        bot.run()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please set all required environment variables:")
        print("- BOT_TOKEN")
        print("- OWNER_ID") 
        print("- INDODAX_API_KEY")
        print("- INDODAX_SECRET_KEY")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")