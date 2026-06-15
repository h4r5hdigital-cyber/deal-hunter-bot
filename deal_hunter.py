import telebot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import threading
from flask import Flask, redirect, url_for, request
from datetime import datetime, timedelta
import urllib.parse
import re

# === TOKENS & SETUP ===
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "TERA_CHAT_ID_YAHAN_DAAL") 
bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# === BOT MENU SETUP ===
try:
    bot.set_my_commands([
        BotCommand("start", "Bot ko zinda karo"),
        BotCommand("list", "Apni Wishlist dekho"),
        BotCommand("checknow", "Manual check karo (Test)"),
        BotCommand("reset", "Poora database saaf karo")
    ])
except Exception as e:
    print("Menu set karne mein error:", e)

# === FLASK SETUP ===
app = Flask(__name__)
@app.route('/')
def home():
    data = load_data()
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Harsh's Admin Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }
            h1 { text-align: center; color: #38bdf8; font-size: 2.5em; text-transform: uppercase; letter-spacing: 2px;}
            .subtitle { text-align: center; color: #94a3b8; margin-bottom: 40px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
            .card { background: #1e293b; padding: 25px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); border-top: 5px solid #38bdf8; transition: transform 0.2s; }
            .card:hover { transform: translateY(-5px); }
            .platform { font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; color: #cbd5e1; font-weight: bold; background: #334155; display: inline-block; padding: 4px 10px; border-radius: 20px; margin-bottom: 15px;}
            .title { font-size: 1.2em; margin: 0 0 15px 0; font-weight: 600; line-height: 1.4; height: 3.8em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
            .price { font-size: 2.2em; color: #10b981; font-weight: bold; margin: 15px 0; }
            .offers { font-size: 0.9em; color: #fbbf24; margin-bottom: 15px; font-style: italic; }
            .btn { display: inline-block; padding: 10px; background: #38bdf8; color: #0f172a; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 1em; text-align: center; cursor: pointer; border: none; }
            .btn:hover { background: #0ea5e9; }
            .btn-danger { background: #ef4444; color: white; }
            .btn-danger:hover { background: #dc2626; }
            .empty {text-align: center; color: #94a3b8; margin-top: 50px; font-size: 1.2em;}
            .action-buttons { display: flex; gap: 10px; margin-top: 15px; }
        </style>
    </head>
    <body>
        <h1>🚀 Harsh's Admin Radar</h1>
        <div class="subtitle">Live Monitoring & Control Panel</div>
        <div class="grid">
    """
    has_items = False
    for chat_id, items in data.items():
        for index, item in enumerate(items):
            has_items = True
            title = item.get('title', 'Product')
            platform = item.get('platform', 'Unknown')
            if 'price_history' in item and len(item['price_history']) > 0:
                price = item['price_history'][-1]['price']
            else:
                price = item.get('start_price', 0)
            url = item.get('url', '#')
            offers_count = len(item.get('latest_offers', []))
            offers_text = f"🎁 {offers_count} Offers Available" if offers_count > 0 else "No Special Offers"
            
            html += f"""
            <div class="card">
                <div class="platform">{'🛒 ' if platform == 'Flipkart' else '📦 '}{platform}</div>
                <div class="title" title="{title}">{title}</div>
                <div class="price">₹{price}</div>
                <div class="offers">{offers_text}</div>
                <div class="action-buttons">
                    <a href="{url}" target="_blank" class="btn" style="flex: 1;">View Deal</a>
                    <form action="/delete/{chat_id}/{index}" method="POST" style="flex: 1; margin: 0; display: flex;">
                        <button type="submit" class="btn btn-danger" style="width: 100%;">🗑️ Delete</button>
                    </form>
                </div>
            </div>
            """
    if not has_items:
        html += "<div class='empty'><h2>Dashboard is empty! Add links via Telegram bot.</h2></div>"
    html += "</div></body></html>"
    return html

@app.route('/delete/<chat_id>/<int:item_index>', methods=['POST'])
def admin_delete(chat_id, item_index):
    data = load_data()
    if chat_id in data and 0 <= item_index < len(data[chat_id]):
        deleted_item = data[chat_id].pop(item_index)
        save_data(data)
        try:
            bot.send_message(chat_id, f"⚠️ **Admin Action:** Tera item '{deleted_item['title'][:30]}...' list se hata diya gaya hai.")
        except: pass
    return redirect(url_for('home'))

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# === DATABASE FUNCTIONS ===
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# === HEADERS & API KEY ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
    "Connection": "keep-alive"
}
API_KEY = "b96371ea776a13335d3c6fd192254409" 

# === AMAZON HYBRID SCRAPER ===
def check_amazon_price(url):
    title, price, offers = "Amazon Product", None, []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", id="productTitle")
            if t_el: title = t_el.text.strip()
        
        availability = soup.find("div", id="availability")
        if availability and re.search(r'currently unavailable|out of stock', availability.text, re.I):
            return title, "OOS", []
            
        p_el = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-size-medium a-color-price") or soup.find("span", class_="a-button-text")
        if p_el: 
            clean_price = re.sub(r'[^\d]', '', p_el.text)
            if clean_price: price = int(clean_price)
            
        keywords = ["discount", "card", "cashback", "bank offer", "emi"]
        for tag in soup.find_all(["span", "li", "div"]):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords) and 20 < len(txt) < 250 and "see all" not in txt_lower:
                clean_txt = " ".join(txt.split())
                if clean_txt not in offers: offers.append(clean_txt)
    except: pass

    if price: return title, price, offers[:5]
        
    print("Amazon Direct Blocked! Using API Bypass with render=true...")
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", id="productTitle")
            if t_el: title = t_el.text.strip()
        
        availability = soup.find("div", id="availability")
        if availability and re.search(r'currently unavailable|out of stock', availability.text, re.I):
            return title, "OOS", []
            
        p_el = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-size-medium a-color-price")
        if p_el: 
            clean_price = re.sub(r'[^\d]', '', p_el.text)
            if clean_price: price = int(clean_price)
            
        keywords = ["discount", "card", "cashback", "bank offer", "emi"]
        for tag in soup.find_all(["span", "li", "div"]):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords) and 20 < len(txt) < 250 and "see all" not in txt_lower:
                clean_txt = " ".join(txt.split())
                if clean_txt not in offers: offers.append(clean_txt)
                
        return title, price, offers[:5]
    except: return None, None, []

# === FLIPKART DOUBLE HYBRID SCRAPER (UPGRADED OFFER DETECTOR) ===
def check_flipkart_price(url):
    title, price, offers = "Flipkart Product", None, []
    
    def is_flipkart_oos(soup_obj):
        for tag in soup_obj.find_all(['div', 'span', 'button']):
            text = tag.get_text(strip=True).lower()
            if text in ["sold out", "currently out of stock", "notify me", "coming soon", "this item is currently out of stock"]:
                return True
        return False

    try:
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
            if t_el: title = t_el.text.strip()

        if is_flipkart_oos(soup): return title, "OOS", []

        p_el = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if p_el:
            clean_price = re.sub(r'[^\d]', '', p_el.text)
            if clean_price: price = int(clean_price)
        else:
            for tag in soup.find_all(['div', 'span']):
                text = tag.text.strip()
                if text.startswith('₹') and len(text) < 15:
                    clean_text = re.sub(r'[^\d]', '', text)
                    if clean_text: 
                        val = int(clean_text)
                        if val > 500:
                            price = val
                            break
                        
        # 🚨 FLIPKART AGGRESSIVE OFFER SCRAPER 🚨
        keywords = ["bank offer", "cashback", "special price", "partner offer", "discount"]
        for tag in soup.find_all(['li', 'span', 'div', 'p']):
            txt = tag.text.strip()
            txt_lower = txt.lower() # Case insensitive match
            if any(kw in txt_lower for kw in keywords):
                if "T&C" in txt: txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers: offers.append(clean_txt)
    except: pass

    if price: return title, price, offers[:5]
    
    print("Flipkart Direct Blocked! Using API Bypass with render=true...")
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
            if t_el: title = t_el.text.strip()
        
        if is_flipkart_oos(soup): return title, "OOS", []

        p_el = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if p_el:
            clean_price = re.sub(r'[^\d]', '', p_el.text)
            if clean_price: price = int(clean_price)
        else:
            for tag in soup.find_all(['div', 'span']):
                text = tag.text.strip()
                if text.startswith('₹') and len(text) < 15:
                    clean_text = re.sub(r'[^\d]', '', text)
                    if clean_text: 
                        val = int(clean_text)
                        if val > 500:
                            price = val
                            break
                            
        # 🚨 FLIPKART API AGGRESSIVE SCRAPER 🚨
        keywords = ["bank offer", "cashback", "special price", "partner offer", "discount"]
        for tag in soup.find_all(['li', 'span', 'div', 'p']):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords):
                if "T&C" in txt: txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers: offers.append(clean_txt)
                        
        return title, price, offers[:5]
    except: return None, None, []

# === CHART GENERATOR ENGINE ===
def generate_chart_url(price_history, title):
    labels = [h['date'].split()[0] for h in price_history]  
    data_points = [h['price'] for h in price_history]
    
    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Price (₹)",
                "data": data_points,
                "borderColor": "rgb(255, 99, 132)", 
                "backgroundColor": "rgba(255, 99, 132, 0.2)",
                "fill": True,
                "tension": 0.4,
                "pointBackgroundColor": "blue",
                "pointRadius": 5
            }]
        },
        "options": {
            "title": {"display": True, "text": title[:40] + "..."},
            "scales": {"yAxes": [{"ticks": {"beginAtZero": False}}]}
        }
    }
    encoded_config = urllib.parse.quote(json.dumps(chart_config))
    return f"https://quickchart.io/chart?c={encoded_config}&w=600&h=400&bkg=white"

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Welcome to Harsh's Deal Hunter!\nAmazon ya Flipkart ka link bhej aur price drop track kar.\n\n🛠️ **Commands:**\n/list - Apni Wishlist dekh\n/checknow - Manual price update check kar\n/reset - Sab kuch delete")

@bot.message_handler(commands=['reset'])
def reset_data(message):
    chat_id = str(message.chat.id)
    data = load_data()
    data[chat_id] = []
    save_data(data)
    bot.reply_to(message, "🔥 Database clear! Ab naye links bhej kar check kar.")

@bot.message_handler(commands=['checknow'])
def manual_price_check(message):
    bot.reply_to(message, "⚙️ Backend check shuru kar diya! Prices scrape kar raha hoon, thoda wait kar...")
    data = load_data()
    chat_id = str(message.chat.id)
    
    if chat_id not in data or not data[chat_id]:
        bot.reply_to(message, "❌ Teri list khali hai. Pehle koi Flipkart ya Amazon ka link toh bhej!")
        return
        
    for item in data[chat_id]:
        platform = item.get('platform', 'Amazon')
        if platform == "Amazon":
            title, new_price, offers = check_amazon_price(item['url'])
        elif platform == "Flipkart":
            title, new_price, offers = check_flipkart_price(item['url'])
            
        if new_price == "OOS":
             bot.send_message(chat_id, f"🚫 **OUT OF STOCK ALERT**\n{item['title'][:30]}...\nYeh item abhi stock se bahar hai.")
             continue
             
        if new_price:
            last_recorded_price = item.get('price_history', [{'price': item['start_price']}])[-1]['price']
            
            if offers: item['latest_offers'] = offers
            
            if new_price == last_recorded_price:
                 bot.send_message(chat_id, f"✅ Check Done! {platform}: {item['title'][:30]}...\nPrice abhi bhi **₹{new_price}** hi hai.")
            elif new_price < last_recorded_price:
                 bot.send_message(chat_id, f"🚨 MEGA DEAL ALERT!\n{item['title'][:30]}...\nPrice Gira: ₹{last_recorded_price} ➡️ **₹{new_price}**")
            elif new_price > last_recorded_price:
                 bot.send_message(chat_id, f"⚠️ PRICE HIKE!\n{item['title'][:30]}...\nPrice Badh Gaya: ₹{last_recorded_price} ➡️ **₹{new_price}**")
    
    save_data(data)
    bot.reply_to(message, "✅ Manual check poora ho gaya, report de di maine!")

# 🏆 NEW UI: THE 3 BUTTON LAYOUT (Graph | Offers | Delete)
@bot.message_handler(commands=['list'])
def show_list(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Teri Wishlist khali hai! Koi link bhej.")
        return
    
    bot.reply_to(message, f"📋 **Teri Wishlist & Tracking List:** ({len(data[chat_id])} items)\nNeeche har item ke buttons check kar 👇", parse_mode='Markdown')
    
    for index, item in enumerate(data[chat_id]):
        short_title = item['title'][:50] + "..." if len(item['title']) > 50 else item['title']
        platform_icon = "🛒" if item.get('platform') == "Flipkart" else "📦"
        
        if 'price_history' in item and len(item['price_history']) > 0:
            current_price = item['price_history'][-1]['price']
        else:
            current_price = item['start_price']
            
        res = f"{platform_icon} *{short_title}*\n💰 Current: ₹{current_price}"
        
        markup = InlineKeyboardMarkup()
        # 3 Buttons in a single row
        markup.row(
            InlineKeyboardButton(f"📈 Graph", callback_data=f"hist_{index}"),
            InlineKeyboardButton(f"🎁 Offers", callback_data=f"off_{index}"),
            InlineKeyboardButton(f"🗑️ Delete", callback_data=f"del_{index}")
        )
        
        bot.send_message(chat_id, res, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = str(call.message.chat.id)
    data = load_data()
    
    try:
        action, idx_str = call.data.split('_')
        item_number = int(idx_str)
        
        if chat_id not in data or item_number >= len(data[chat_id]):
            bot.answer_callback_query(call.id, "❌ Ye item ab list mein nahi hai.")
            return
            
        item = data[chat_id][item_number]
        
        if action == "hist":
            bot.answer_callback_query(call.id, "📊 Graph laa raha hoon...")
            chart_url = generate_chart_url(item['price_history'], item['title'])
            prices = [h['price'] for h in item['price_history']]
            
            res = f"📉 **PRICE HISTORY REPORT**\n📦 {item['title'][:50]}...\n----------------------------------------\n"
            res += f"🔥 **Lowest:** ₹{min(prices)} | 📈 **Highest:** ₹{max(prices)}\n"
            bot.send_photo(chat_id, chart_url, caption=res, parse_mode='Markdown')
            
        # 🎁 NEW: OFFERS BUTTON ACTION
        elif action == "off":
            offers_list = item.get('latest_offers', [])
            if offers_list:
                bot.answer_callback_query(call.id, "🎁 Offers nikal raha hoon...")
                offers_text = "\n\n".join([f"▪️ {o}" for o in offers_list])
                msg = f"🎁 **Top Offers For:**\n📦 {item['title'][:40]}...\n\n{offers_text}"
                bot.send_message(chat_id, msg, parse_mode='Markdown')
            else:
                # Agar offer blank hai toh screen pe chhota sa alert aayega
                bot.answer_callback_query(call.id, "Abhi is par koi khaas Bank Offer nahi dikh raha bhai!", show_alert=True)
            
        elif action == "del":
            deleted_item = data[chat_id].pop(item_number)
            save_data(data)
            bot.answer_callback_query(call.id, "🗑️ Item deleted!")
            bot.delete_message(chat_id, call.message.message_id) 
            bot.send_message(chat_id, f"🗑️ Maine **{deleted_item['title'][:30]}...** ko hata diya.")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Kuch error aa gaya.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "amazon" in url.lower() or "amzn" in url.lower():
        platform = "Amazon"
    elif "flipkart" in url.lower() or "fkrt" in url.lower() or "fktr" in url.lower() or "dl.flipkart" in url.lower():
        platform = "Flipkart"
    else:
        bot.reply_to(message, "⚠️ Bhai, abhi sirf Amazon aur Flipkart ke links bhej.")
        return

    bot.reply_to(message, f"🔍 {platform} par data check kar raha hoon... (Heavy page loading, thoda wait kar)")
    
    current_price = None
    offers = []
    title = ""
    for attempt in range(2): 
        if platform == "Amazon":
            title, current_price, offers = check_amazon_price(url)
        else:
            title, current_price, offers = check_flipkart_price(url)
            
        if current_price: 
            break 
        else:
            time.sleep(3) 

    if current_price == "OOS":
        bot.reply_to(message, "❌ **Bhai, tera bheja hua variant/color abhi OUT OF STOCK hai!**\nMain galat in-stock variant ka price nahi uthaunga, isliye maine isko list mein add nahi kiya.")
        return

    if current_price:
        data = load_data()
        chat_id = str(message.chat.id)
        if chat_id not in data:
            data[chat_id] = []
            
        current_time_str = get_ist_time().strftime("%d-%b %I:%M %p")
        
        data[chat_id].append({
            "url": url,
            "title": title, 
            "start_price": current_price,
            "platform": platform,
            "price_history": [{"date": current_time_str, "price": current_price}],
            "latest_offers": offers,
            "error_count": 0 
        })
        save_data(data)
        
        icon = "🛒" if platform == "Flipkart" else "📦"
        response = f"✅ **{platform.upper()} TRACKING ON**\n{icon} {title[:50]}...\n💰 Price: ₹{current_price}\n\n*💡 Bank Offers dekhne ke liye /list daba aur '🎁 Offers' button click kar.*"
        bot.reply_to(message, response, parse_mode='Markdown')
    else:
        bot.reply_to(message, "⚠️ Bhai lagta hai server thoda busy hai ya timeout ho gaya. Ek baar fir se link bhej de!")

# === SCHEDULED ROUTINE CHECKER ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        current_hour = ist_now.hour
        current_minute = ist_now.minute
        current_year = ist_now.year 
        
        if current_hour in [0, 6, 12, 18] and current_minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{current_hour}"
            if check_key not in checked_keys:
                print(f"🔄 Auto-Check start hua (Hour: {current_hour})")
                data = load_data()
                changes_made = False
                
                for chat_id in list(data.keys()):
                    valid_items = []
                    for item in data[chat_id]:
                        is_expired = False
                        if 'price_history' in item and len(item['price_history']) > 0:
                            first_date_str = item['price_history'][0]['date']
                            if first_date_str != "Old Data":
                                try:
                                    added_date = datetime.strptime(f"{first_date_str} {current_year}", "%d-%b %I:%M %p %Y")
                                    if (ist_now - added_date).days >= 30:
                                        is_expired = True
                                except: pass
                                
                        if is_expired:
                            changes_made = True
                            try:
                                bot.send_message(chat_id, f"⏳ **Tracking Expired!**\n30 din poore ho gaye, maine yeh item hata diya hai:\n🗑️ {item['title'][:40]}...")
                            except: pass
                        else:
                            valid_items.append(item) 
                            
                    data[chat_id] = valid_items 
                
                for chat_id, items in data.items():
                    for item in items:
                        try:
                            platform = item.get('platform', 'Amazon')
                            if platform == "Amazon":
                                title, new_price, offers = check_amazon_price(item['url'])
                            elif platform == "Flipkart":
                                title, new_price, offers = check_flipkart_price(item['url'])
                            else:
                                continue
                                
                            if new_price == "OOS":
                                continue
                                
                            if new_price is None:
                                item['error_count'] = item.get('error_count', 0) + 1
                                if item['error_count'] == 3:
                                    try: bot.send_message(chat_id, f"⚠️ *Maintenance Alert:*\nTere product '{item['title'][:30]}...' ka link theek se check nahi ho pa raha. Humari team isko dekh rahi hai.", parse_mode="Markdown")
                                    except: pass
                                    
                                    if ADMIN_CHAT_ID:
                                        try: bot.send_message(ADMIN_CHAT_ID, f"🚨 *ADMIN ALERT: API FAILED 3 TIMES*\nLink: {item['url']}\nUser: {chat_id}", parse_mode="Markdown")
                                        except: pass
                                changes_made = True
                                continue
                            
                            item['error_count'] = 0
                                
                            if new_price:
                                if offers: item['latest_offers'] = offers
                                
                                if 'price_history' not in item:
                                    item['price_history'] = [{"date": "Old Data", "price": item['start_price']}]
                                    
                                last_recorded_price = item['price_history'][-1]['price']
                                
                                if new_price != last_recorded_price:
                                    current_time_str = get_ist_time().strftime("%d-%b %I:%M %p")
                                    item['price_history'].append({"date": current_time_str, "price": new_price})
                                    changes_made = True
                                    
                                    icon = "🛒" if platform == "Flipkart" else "📦"
                                    
                                    if new_price < last_recorded_price:
                                        bot.send_message(
                                            chat_id,
                                            f"🚨🚨 {platform.upper()} MEGA DEAL ALERT! 🚨🚨\n{icon} {item['title'][:40]}...\n💰 Old: ₹{last_recorded_price}\n🔥 NEW: ₹{new_price}\n🔗 {item['url']}"
                                        )
                                    elif new_price > last_recorded_price:
                                        bot.send_message(
                                            chat_id,
                                            f"⚠️⚠️ {platform.upper()} PRICE HIKE ALERT! ⚠️⚠️\n{icon} {item['title'][:40]}...\n📈 Price badh gaya hai!\n💰 Old: ₹{last_recorded_price}\n🔺 NEW: ₹{new_price}\n🔗 {item['url']}"
                                        )
                        except Exception as e:
                            print(f"Auto checker error on item: {e}")
                            pass
                            
                if changes_made:
                    save_data(data)
                checked_keys.add(check_key)
                
        time.sleep(60) 

# === START ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    print("🚀 Harsh's Bot Online: Offers Button Edition!")
    bot.infinity_polling()
