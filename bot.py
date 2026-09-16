import os
import time
import requests
import telebot
from datetime import datetime

BOT_TOKEN = "8949808593:AAEXTRsl8Nu6X1x3CjXJLNDyb71zKVKCGWY"
CMC_API_KEY = os.environ.get("CMC_API_KEY", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()

bot = telebot.TeleBot(BOT_TOKEN)

COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOT", "LINK", "MATIC", "AVAX"]

def get_coin_data(symbol):
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}
        params = {"symbol": symbol, "convert": "USD"}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data.get("status", {}).get("error_code") != 0:
            return None
        quote = data["data"][symbol]["quote"]["USD"]
        return {
            "symbol": symbol,
            "price": quote["price"],
            "change_1h": quote["percent_change_1h"],
            "change_24h": quote["percent_change_24h"],
            "change_7d": quote["percent_change_7d"],
            "volume_24h": quote["volume_24h"],
            "market_cap": quote["market_cap"]
        }
    except Exception:
        return None

def analyze(coin):
    data = get_coin_data(coin)
    if not data:
        return None
    ch = data["change_24h"]
    if ch > 5:
        signal = "🟢 BUY (Strong)"
    elif ch > 1:
        signal = "🟢 BUY"
    elif ch < -5:
        signal = "🔴 SELL (Strong)"
    elif ch < -1:
        signal = "🔴 SELL"
    else:
        signal = "⚪️ NEUTRAL"
    data["signal"] = signal
    return data

def send_report():
    msg = "📊 *Crypto Market Report*\n"
    msg += "🕐 " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n"
    msg += "━━━━━━━━━━━━━━\n\n"
    for coin in COINS:
        data = analyze(coin)
        if data:
            msg += f"💠 *{data['symbol']}*\n"
            msg += f"💰 Price: ${data['price']:.4f}\n"
            msg += f"📈 1h: {data['change_1h']:+.2f}%\n"
            msg += f"📊 24h: {data['change_24h']:+.2f}%\n"
            msg += f"📅 7d: {data['change_7d']:+.2f}%\n"
            msg += f"💡 {data['signal']}\n"
            msg += "━━━━━━━━━━━━━━\n\n"
        time.sleep(0.3)
    try:
        bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
        print("Report sent at", datetime.now())
    except Exception as e:
        print("Error:", e)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Crypto Bot is running")

@bot.message_handler(commands=['report'])
def manual(message):
    bot.reply_to(message, "⏳ Generating report...")
    send_report()

# إرسال تقرير كل 4 ساعات
if  __name__ == "__main__":
    print("=== BOT STARTED ===")
    send_report()
    while True:
        time.sleep(4 * 60 * 60)
        send_report()
