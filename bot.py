import os
import asyncio
import requests
import json
from ohlcv_router import fetch
import telebot
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ضع_التوكن_هنا").strip()
bot = telebot.TeleBot(BOT_TOKEN)
ADMIN_ID = 7002618091

LANG = {
    "ar": {"report":"📊 تقرير التحليل الفني","frame":"⏰ فريم: 4 ساعات","buy":"🟢 شراء","sell":"🔴 بيع","entry":"💰 الدخول","tp":"🎯 الهدف","tp4":"🚀 الهدف 4","sl":"🔴 الستوب","rsi":"📈 RSI","ask":"أرسل عملة مثل BTC","error":"⚠️ ما لقيت العملة","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 نسخة تجريبية. للاشتراك في VIP (كل الأهداف + إشارات أقوى)، تواصل معنا."},
    "en": {"report":"📊 Technical Analysis","frame":"⏰ Timeframe: 4H","buy":"🟢 BUY","sell":"🔴 SELL","entry":"💰 Entry","tp":"🎯 Target","tp4":"🚀 Target 4","sl":"🔴 Stop Loss","rsi":"📈 RSI","ask":"Send a coin like BTC","error":"⚠️ Coin not found","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 Trial version. For VIP, contact us."},
    "zh": {"report":"📊 技术分析报告","frame":"⏰ 时间框架: 4小时","buy":"🟢 买入","sell":"🔴 卖出","entry":"💰 入场","tp":"🎯 目标","tp4":"🚀 目标 4","sl":"🔴 止损","rsi":"📈 RSI","ask":"发送币种名称","error":"⚠️ 未找到该币种","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 试用版。VIP可获得所有目标。"},
    "hi": {"report":"📊 तकनीकी विश्लेषण","frame":"⏰ समय सीमा: 4 घंटे","buy":"🟢 खरीदें","sell":"🔴 बेचें","entry":"💰 प्रवेश","tp":"🎯 लक्ष्य","tp4":"🚀 लक्ष्य 4","sl":"🔴 स्टॉप लॉस","rsi":"📈 RSI","ask":"सिक्का नाम भेजें","error":"⚠️ सिक्का नहीं मिला","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 ट्रायल। VIP के लिए संपर्क करें।"},
    "tr": {"report":"📊 Teknik Analiz","frame":"⏰ Zaman: 4H","buy":"🟢 ALIŞ","sell":"🔴 SATIŞ","entry":"💰 Giriş","tp":"🎯 Hedef","tp4":"🚀 Hedef 4","sl":"🔴 Stop Loss","rsi":"📈 RSI","ask":"BTC gibi coin gönderin","error":"⚠️ Coin bulunamadı","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 Deneme sürümü. VIP için iletişime geçin."},
    "es": {"report":"📊 Análisis Técnico","frame":"⏰ Marco: 4H","buy":"🟢 COMPRA","sell":"🔴 VENTA","entry":"💰 Entrada","tp":"🎯 Objetivo","tp4":"🚀 Objetivo 4","sl":"🔴 Stop Loss","rsi":"📈 RSI","ask":"Envía una moneda como BTC","error":"⚠️ Moneda no encontrada","entry_lbl":"Entry","tp_lbl":"Target","sl_lbl":"Stop Loss","res_lbl":"Resistance","sup_lbl":"Support","vip_msg":"\n\n🔒 Versión de prueba. Para VIP, contáctanos."},
}

def detect_lang(text):
    for ch in text:
        if ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            return "ar"
    for ch in text:
        if ch in "你好中文":
            return "zh"
    for ch in text:
        if ch in "हिन्दी":
            return "hi"
    for ch in text:
        if ch in "çğıöşüÇĞİÖŞÜ":
            return "tr"
    for ch in text:
        if ch in "áéíóúñÁÉÍÓÚÑ":
            return "es"
    return "en"

def get_alpha_tokens():
    try:
        url = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
        resp = requests.get(url, timeout=10)
        return resp.json().get("data", [])
    except Exception:
        return []

def find_alpha_symbol(user_input):
    user_input = user_input.upper().strip()
    base = user_input.replace("USDT", "").strip()
    tokens = get_alpha_tokens()
    for token in tokens:
        sym = token.get("symbol", "").upper()
        if sym == base:
            alpha_id = str(token.get("alphaId", ""))
            if alpha_id:
                return alpha_id + "USDT"
    return None
def dex_search_symbol(query):
    try:
        url = "https://api.dexpaprika.com/search"
        params = {"query": query}
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        pools = data.get("pools", [])
        if not pools:
            return None
        pools.sort(key=lambda p: p.get("liquidity_usd", 0), reverse=True)
        best = pools[0]
        return {"network": best.get("network"), "pool": best.get("id")}
    except Exception:
        return None

def dex_get_ohlcv(network, pool, hours=200):
    try:
        url = "https://api.dexpaprika.com/networks/" + network + "/pools/" + pool + "/ohlcv"
        params = {"interval": "1h", "limit": hours * 4}
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json().get("data", [])
        if not data:
            return None
        df = pd.DataFrame(data, columns=["time","open","high","low","close","volume"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        df4 = df.resample("4h").agg({
            "open":"first","high":"max","low":"min","close":"last","volume":"sum"
        }).dropna()
        return df4
    except Exception:
        return None

def find_symbol(user_input):
    user_input = user_input.upper().strip()
    base = user_input.replace("USDT", "").strip()

    try:
        alpha_sym = find_alpha_symbol(user_input)
        if alpha_sym:
            return ("ALPHA", alpha_sym)
    except:
        pass

    try:
        dex_info = dex_search_symbol(base)
        if dex_info and dex_info.get("network") and dex_info.get("pool"):
            return ("DEX", dex_info)
    except:
        pass

    return ("CEX", base + "USDT")

def get_data(symbol_info, interval="4h", limit=200):
    source, sym = symbol_info

    if source == "ALPHA" or source == "DEX":
        # البحث في CoinGecko On-Chain باستخدام الرمز
        try:
            # 1. البحث عن العملة في CoinGecko On-Chain
            search_url = "https://api.geckoterminal.com/api/v2/search/pools"
            search_params = {"query": sym.replace("USDT", ""), "page": 1}
            search_resp = requests.get(search_url, params=search_params, timeout=15).json()
            
            pools = search_resp.get("data", [])
            if not pools:
                return None
            
            # 2. اختيار التجمع الأكثر سيولة
            best_pool = max(pools, key=lambda p: p.get("attributes", {}).get("reserve_in_usd", 0) or 0)
            network = best_pool["relationships"]["network"]["data"]["id"]
            pool_address = best_pool["attributes"]["address"]
            
            # 3. جلب شموع 4 ساعات (hourly مع aggregate=4)
            ohlcv_url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/hour"
            ohlcv_params = {"aggregate": "4", "limit": str(limit), "currency": "usd"}
            ohlcv_resp = requests.get(ohlcv_url, params=ohlcv_params, timeout=15).json()
            
            ohlcv_list = ohlcv_resp.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
            if not ohlcv_list:
                return None
            
            # 4. تحويل البيانات إلى DataFrame
            df = pd.DataFrame(ohlcv_list, columns=["time", "open", "high", "low", "close", "volume"])
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = df[c].astype(float)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.set_index("time", inplace=True)
            return df
        except Exception:
            return None

    # ============ للعملات العادية (CEX) ============
    try:
        import yfinance as yf
        base = sym.replace("USDT", "").replace("USDC", "")
        yf_sym = base + "-USD"
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period="60d", interval="1h")
        if len(hist) >= 20:
            df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df = df.resample("4h").agg({
                "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
            }).dropna()
            if len(df) >= 20:
                return df
    except Exception:
        pass

    # CoinGecko العادي (احتياطي)
    try:
        base = sym.replace("USDT", "").replace("USDC", "")
        url = "https://api.coingecko.com/api/v3/coins/" + base.lower() + "/ohlc"
        params = {"vs_currency": "usd", "days": "30"}
        resp = requests.get(url, params=params, timeout=10).json()
        if resp and len(resp) >= 20:
            df = pd.DataFrame(resp, columns=["time", "open", "high", "low", "close"])
            df["volume"] = 0
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df.set_index("time", inplace=True)
            return df
    except Exception:
        pass

    return Non
def calc_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def calc_bollinger(df, period=20):
    ma = df["close"].rolling(period).mean()
    sd = df["close"].rolling(period).std()
    return ma + 2*sd, ma, ma - 2*sd

def calc_macd(df):
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def calc_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_adx(df, period=14):
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = calc_atr(df, period)
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / tr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / tr)
    dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.ewm(alpha=1/period).mean()

@bot.message_handler(commands=['start'])
def start(message):
    lang = detect_lang(message.from_user.language_code or "en")
    if lang not in LANG:
        lang = "en"
    bot.reply_to(message, LANG[lang]["ask"])

@bot.message_handler(func=lambda m: True)
def reply(message):
    if message.text and message.text.lower().strip() in ['/start', 'start', 'help', 'بدأ', '/help']:
        lang = detect_lang(message.from_user.language_code or "en")
        if lang not in LANG:
            lang = "en"
        bot.reply_to(message, LANG[lang]["ask"])
        return
    lang = detect_lang(message.text)
    if lang not in LANG:
        lang = "en"
    t = LANG[lang]

    symbol_info = find_symbol(message.text)
    if symbol_info is None:
        bot.reply_to(message, t["error"])
        return

    try:
        df = get_data(symbol_info, limit=200)
        if df is None or len(df) < 20:
            bot.reply_to(message, "⚠️ " + str(symbol_info[1]) + " not available")
            return

        rsi_series = calc_rsi(df)
        rsi = rsi_series.iloc[-1]
        ema20_series = calc_ema(df, 20)
        ema50_series = calc_ema(df, 50)
        ema20 = ema20_series.iloc[-1]
        ema50 = ema50_series.iloc[-1]
        bb_upper, bb_mid, bb_lower = calc_bollinger(df)
        macd_series, signal_series, hist_series = calc_macd(df)
        macd = macd_series.iloc[-1]
        signal = signal_series.iloc[-1]
        atr = calc_atr(df).iloc[-1]
        adx = calc_adx(df).iloc[-1]
        price = df["close"].iloc[-1]
        high = df["high"].tail(50).max()
        low = df["low"].tail(50).min()

        trend_up = ema20 > ema50
        trend_down = ema20 < ema50
        macd_bull = macd > signal
        macd_bear = macd < signal
        strong = adx > 25

        if trend_up and macd_bull:
            side_key = "buy"
        elif trend_down and macd_bear:
            side_key = "sell"
        elif trend_up:
            side_key = "buy"
        elif trend_down:
            side_key = "sell"
        else:
            side_key = "buy" if rsi < 50 else "sell"

        entry = price

        if strong:
            if side_key == "buy":
                sl = entry - (atr * 1.5)
                tp1 = entry + (atr * 1.5)
                tp2 = entry + (atr * 2.5)
                tp3 = entry + (atr * 4.0)
                tp4 = entry + (atr * 6.0)
        else:
                sl = entry + (atr * 1.5)
                tp1 = entry - (atr * 1.5)
                tp2 = entry - (atr * 2.5)
                tp3 = entry - (atr * 4.0)
                tp4 = entry - (atr * 6.0)
        if not strong:
            if side_key == "buy":
                sl = entry - (atr * 1.2)
                tp1 = entry + (atr * 1.2)
                tp2 = entry + (atr * 2.0)
                tp3 = entry + (atr * 3.0)
                tp4 = entry + (atr * 4.5)
            else:
                sl = entry + (atr * 1.2)
                tp1 = entry - (atr * 1.2)
                tp2 = entry - (atr * 2.0)
                tp3 = entry - (atr * 3.0)
                tp4 = entry - (atr * 4.5)

        df_plot = df.tail(80).copy()
        df_plot["ema20"] = ema20_series.tail(80)
        df_plot["ema50"] = ema50_series.tail(80)
        df_plot["bb_upper"] = bb_upper.tail(80)
        df_plot["bb_lower"] = bb_lower.tail(80)
        df_plot["rsi"] = rsi_series.tail(80)

        apds = [
            mpf.make_addplot(df_plot["ema20"], color="#1f77b4", width=1.5, panel=0),
            mpf.make_addplot(df_plot["ema50"], color="#ff7f0e", width=1.5, panel=0),
            mpf.make_addplot(df_plot["bb_upper"], color="#999999", width=0.8, panel=0, linestyle="--"),
            mpf.make_addplot(df_plot["bb_lower"], color="#999999", width=0.8, panel=0, linestyle="--"),
            mpf.make_addplot(df_plot["rsi"], panel=1, color="#e91e63", width=1.2, ylabel="RSI"),
        ]

        hlines = dict(
            hlines=[entry, tp1, tp2, tp3, tp4, sl, low, high],
            colors=["#1f77b4","#2ca02c","#2ca02c","#2ca02c","#9467bd","#d62728","#8B0000","#00008B"],
            linestyle="dashed",
            linewidths=[1.2,1.2,1.2,1.2,1.2,1.5,2.0,2.0]
        )

        safe_name = str(symbol_info[1]).replace("/", "_").replace(":", "_")
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
            title=safe_name + " - 4H", returnfig=True,
            tight_layout=True, panel_ratios=(3,1)
        )

        ax = axes[0]
        ax.text(0.5, 0.5, "Crypto Analyse", transform=ax.transAxes,
                fontsize=70, color="gray", alpha=0.15, ha="center",
                va="center", fontweight="bold", zorder=0)

        x_left = 0.5
        y_top = 0.97
        y_step = 0.045
        labels = [
            (t["res_lbl"] + ": " + str(round(high, 6)), "#00008B"),
            (t["tp_lbl"] + " 4: " + str(round(tp4, 6)), "#9467bd"),
            (t["tp_lbl"] + " 3: " + str(round(tp3, 6)), "#2ca02c"),
            (t["tp_lbl"] + " 2: " + str(round(tp2, 6)), "#2ca02c"),
            (t["tp_lbl"] + " 1: " + str(round(tp1, 6)), "#2ca02c"),
            (t["entry_lbl"] + ": " + str(round(entry, 6)), "#1f77b4"),
            (t["sl_lbl"] + ": " + str(round(sl, 6)), "#d62728"),
            (t["sup_lbl"] + ": " + str(round(low, 6)), "#8B0000"),
        ]
        for i, (label, color) in enumerate(labels):
            y_pos = y_top - (i * y_step)
            ax.text(x_left, y_pos, label, transform=ax.transAxes,
                    color=color, fontsize=9, va="top", ha="left",
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor=color, linewidth=1))

        fig.savefig(filename, dpi=110, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        txt = t["report"] + " - " + safe_name + "\n"
        txt += t["frame"] + "\n"
        txt += t[side_key] + "\n\n"
        txt += t["entry"] + ": " + str(round(entry, 6)) + "\n"

        if message.from_user.id != ADMIN_ID:
            txt += t["tp"] + " 1: " + str(round(tp1, 6)) + "\n"
            txt += t["tp"] + " 2: " + str(round(tp2, 6)) + "\n"
            txt += t["sl"] + ": " + str(round(sl, 6)) + "\n"
            txt += t["rsi"] + ": " + str(round(rsi, 2)) + "\n"
            txt += "\n📊 ADX: " + str(round(adx, 2)) + " | MACD: " + str(round(macd, 6)) + "\n"
            txt += t["vip_msg"]
        else:
            txt += t["tp"] + " 1: " + str(round(tp1, 6)) + "\n"
            txt += t["tp"] + " 2: " + str(round(tp2, 6)) + "\n"
            txt += t["tp"] + " 3: " + str(round(tp3, 6)) + "\n"
            txt += t["tp4"] + ": " + str(round(tp4, 6)) + "\n"
            txt += t["sl"] + ": " + str(round(sl, 6)) + "\n"
            txt += t["res_lbl"] + ": " + str(round(high, 6)) + "\n"
            txt += t["sup_lbl"] + ": " + str(round(low, 6)) + "\n\n"
            txt += t["rsi"] + ": " + str(round(rsi, 2)) + "\n"
            txt += "📊 ADX: " + str(round(adx, 2)) + "\n"
            txt += "📈 MACD: " + str(round(macd, 6)) + " | Signal: " + str(round(signal, 6)) + "\n"
            txt += "📉 ATR: " + str(round(atr, 6)) + "\n"

            if rsi < 30:
                success = 85
            elif rsi > 70:
                success = 80
            elif strong:
                success = 90
            else:
                success = 70

            txt += "\n\n━━━━━━━━━━━━━━\n"
            txt += "🔒 ADMIN ONLY\n"
            txt += "━━━━━━━━━━━━━━\n"
            txt += "📊 نسبة النجاح: " + str(success) + "%\n"
            txt += "💰 السيولة (24h): N/A\n"
            txt += "🐋 رادار الحيتان: N/A"

        with open(filename, "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=txt)
    except Exception as e:
        bot.reply_to(message, "Error: " + str(e)[:200])

bot.infinity_polling()
