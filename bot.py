import os
import requests
import telebot
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = 7002618091

bot = telebot.TeleBot(BOT_TOKEN)

LANG = {
    "ar": {"report":"📊 تقرير التحليل الفني","frame":"⏰ فريم: يومي","buy":"🟢 شراء","sell":"🔴 بيع","entry":"💰 الدخول","tp":"🎯 الهدف","tp4":"🚀 الهدف 3","sl":"🔴 الستوب","rsi":"📈 RSI","ask":"أرسل عملة مثل BTC","error":"⚠️ ما لقيت العملة","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 نسخة تجريبية. للاشتراك في VIP (كل الأهداف + إشارات أقوى)، تواصل معنا."},
    "en": {"report":"📊 Technical Analysis","frame":"⏰ Timeframe: Daily","buy":"🟢 BUY","sell":"🔴 SELL","entry":"💰 Entry","tp":"🎯 Target","tp4":"🚀 Target 3","sl":"🔴 Stop Loss","rsi":"📈 RSI","ask":"Send a coin like BTC","error":"⚠️ Coin not found","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 Trial version. For VIP, contact us."},
}

def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    return "en"

# ============ جلب البيانات من CoinGecko ============
def get_data(symbol):
    try:
        base = symbol.replace("USDT", "").replace("USDC", "").lower()
        url = "https://api.coingecko.com/api/v3/coins/" + base + "/ohlc"
        params = {"vs_currency": "usd", "days": "365"}
        resp = requests.get(url, params=params, timeout=15).json()
        if not resp or len(resp) < 100:
            return None
        df = pd.DataFrame(resp, columns=["time", "open", "high", "low", "close"])
        df["volume"] = 0
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)
        # فريم يومي: نحوّل كل 6 شموع 4 ساعات -> يوم
        df = df.resample("1D").agg({
            "open":"first","high":"max","low":"min","close":"last","volume":"sum"
        }).dropna()
        return df
    except Exception:
        return None

# ============ المؤشرات ============
def calc_ichimoku(df):
    high = df["high"]
    low = df["low"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    chikou = df["close"].shift(-26)
    return tenkan, kijun, senkou_a, senkou_b, chikou

def calc_bollinger(df, period=20):
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return ma + 2*sd, ma, ma - 2*sd

def calc_stoch_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
    return stoch_rsi

def calc_adx(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)
    dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.ewm(alpha=1/period).mean(), atr
def calc_fibonacci(df, period=50):
    high = df["high"].tail(period).max()
    low = df["low"].tail(period).min()
    diff = high - low
    return {
        "0": low,
        "23.6": low + diff * 0.236,
        "38.2": low + diff * 0.382,
        "50": low + diff * 0.5,
        "61.8": low + diff * 0.618,
        "78.6": low + diff * 0.786,
        "100": high,
        "161.8": low + diff * 1.618
    }

def calc_volume_profile(df, period=50):
    prices = df["close"].tail(period)
    volumes = df["volume"].tail(period)
    if volumes.sum() == 0:
        return None, None
    poc = prices.iloc[volumes.argmax()]
    return poc, volumes.max()

# ============ التحليل ============
def analyze(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 100:
        return None

    # المؤشرات
    tenkan, kijun, senkou_a, senkou_b, chikou = calc_ichimoku(df)
    bb_upper, bb_mid, bb_lower = calc_bollinger(df)
    stoch_rsi = calc_stoch_rsi(df)
    adx, atr = calc_adx(df)
    fib = calc_fibonacci(df)
    poc, poc_vol = calc_volume_profile(df)

    # القيم الأخيرة
    price = df["close"].iloc[-1]
    ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = df["close"].ewm(span=200, adjust=False).mean().iloc[-1]
    adx_val = adx.iloc[-1]
    atr_val = atr.iloc[-1]
    stoch_val = stoch_rsi.iloc[-1]
    tenkan_val = tenkan.iloc[-1]
    kijun_val = kijun.iloc[-1]

    # كشف الإشارة
    trend_up = ema20 > ema50 and price > ema50
    trend_down = ema20 < ema50 and price < ema50
    strong = adx_val > 20

    if trend_up and strong and stoch_val < 80:
        side_key = "buy"
        entry = price
        sl = entry - (atr_val * 2)
        tp1 = fib["61.8"]
        tp2 = fib["78.6"]
        tp3 = fib["161.8"]
    elif trend_down and strong and stoch_val > 20:
        side_key = "sell"
        entry = price
        sl = entry + (atr_val * 2)
        tp1 = fib["38.2"]
        tp2 = fib["23.6"]
        tp3 = fib["0"]
    else:
        return None

    return {
        "symbol": symbol,
        "side": side_key,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rsi": stoch_val,
        "adx": adx_val,
        "atr": atr_val,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "df": df,
        "tenkan": tenkan_val,
        "kijun": kijun_val,
        "bb_upper": bb_upper.iloc[-1],
        "bb_lower": bb_lower.iloc[-1],
        "poc": poc
    }

# ============ البوت ============
@bot.message_handler(commands=['start'])
def start(message):
    lang = detect_lang(message.from_user.language_code or "en")
    if lang not in LANG:
        lang = "en"
    bot.reply_to(message, LANG[lang]["ask"])

@bot.message_handler(func=lambda m: True)
def reply(message):
    if message.text and message.text.lower().strip() in ['/start', 'start', 'help', 'بدأ']:
        lang = detect_lang(message.from_user.language_code or "en")
        bot.reply_to(message, LANG[lang]["ask"])
        return
    lang = detect_lang(message.text)
    if lang not in LANG:
        lang = "en"
    t = LANG[lang]

    symbol = message.text.upper().strip()
    if not symbol.endswith("USDT"):
        symbol = symbol + "USDT"

    try:
        result = analyze(symbol)
        if result is None:
            bot.reply_to(message, "⚠️ " + symbol + " not available or no clear signal")
            return

        df = result["df"]
        price = result["entry"]
        high = df["high"].tail(50).max()
        low = df["low"].tail(50).min()

        # رسم الشارت
        df_plot = df.tail(100).copy()
        df_plot["ema20"] = df["close"].ewm(span=20, adjust=False).mean().tail(100)
        df_plot["ema50"] = df["close"].ewm(span=50, adjust=False).mean().tail(100)
        df_plot["bb_upper"] = calc_bollinger(df)[0].tail(100)
        df_plot["bb_lower"] = calc_bollinger(df)[2].tail(100)
        apds = [
            mpf.make_addplot(df_plot["ema20"], color="#1f77b4", width=1.5),
            mpf.make_addplot(df_plot["ema50"], color="#ff7f0e", width=1.5),
            mpf.make_addplot(df_plot["bb_upper"], color="#999999", width=0.8, linestyle="--"),
            mpf.make_addplot(df_plot["bb_lower"], color="#999999", width=0.8, linestyle="--"),
        ]

        hlines = dict(
            hlines=[result["entry"], result["tp1"], result["tp2"], result["tp3"], result["sl"]],
            colors=["#1f77b4","#2ca02c","#2ca02c","#9467bd","#d62728"],
            linestyle="dashed",
            linewidths=[1.2,1.2,1.2,1.2,1.5]
        )

        safe_name = symbol.replace("/", "_")
        filename = "chart_" + safe_name + ".png"

        mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="in")
        style = mpf.make_mpf_style(
            marketcolors=mc, gridstyle=":", gridcolor="#dddddd",
            facecolor="white", figcolor="white", edgecolor="#cccccc",
            rc={"font.size":9,"axes.labelcolor":"black","xtick.color":"black","ytick.color":"black","text.color":"black","axes.titlecolor":"black"}
        )

        fig, axes = mpf.plot(
            df_plot, type="candle", style=style, addplot=apds,
            hlines=hlines, volume=False, figsize=(13,8),
            title=safe_name + " - Daily", returnfig=True,
            tight_layout=True
        )

        ax = axes[0]
        ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
                fontsize=70, color="gray", alpha=0.15, ha="center",
                va="center", fontweight="bold", zorder=0)

        labels = [
            ("Resistance: " + str(round(high, 6)), "#00008B", high),
            ("TP3: " + str(round(result["tp3"], 6)), "#9467bd", result["tp3"]),
            ("TP2: " + str(round(result["tp2"], 6)), "#2ca02c", result["tp2"]),
            ("TP1: " + str(round(result["tp1"], 6)), "#2ca02c", result["tp1"]),
            ("Entry: " + str(round(result["entry"], 6)), "#1f77b4", result["entry"]),
            ("SL: " + str(round(result["sl"], 6)), "#d62728", result["sl"]),
            ("Support: " + str(round(low, 6)), "#8B0000", low),
        ]
        for i, (label, color, _) in enumerate(labels):
            y_pos = 0.97 - (i * 0.045)
            ax.text(0.5, y_pos, label, transform=ax.transAxes,
                    color=color, fontsize=9, va="top", ha="left",
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor=color, linewidth=1))

        fig.savefig(filename, dpi=110, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        txt = t["report"] + " - " + symbol + "\n"
        txt += t["frame"] + "\n"
        txt += t[result["side"]] + "\n\n"
        txt += t["entry"] + ": " + str(round(result["entry"], 6)) + "\n"
        txt += t["tp"] + " 1: " + str(round(result["tp1"], 6)) + "\n"
        txt += t["tp"] + " 2: " + str(round(result["tp2"], 6)) + "\n"
        txt += t["tp4"] + ": " + str(round(result["tp3"], 6)) + "\n"
        txt += t["sl"] + ": " + str(round(result["sl"], 6)) + "\n\n"
        txt += t["rsi"] + ": " + str(round(result["rsi"], 2)) + "\n"
        txt += "📊 ADX: " + str(round(result["adx"], 2)) + "\n"
        txt += "📉 ATR: " + str(round(result["atr"], 6))

        if message.from_user.id != ADMIN_ID:
            txt += t["vip_msg"]

        with open(filename, "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=txt)
    except Exception as e:
        bot.reply_to(message, "Error: " + str(e)[:200])

bot.infinity_polling()
