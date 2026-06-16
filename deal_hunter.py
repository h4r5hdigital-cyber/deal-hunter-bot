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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
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
        <title>Harsh's Admin Dashboard V2</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }
            h1 { text-align: center; color: #38bdf8; font-size: 2.5em; text-transform: uppercase; letter-spacing: 2px;}
            .subtitle { text-align: center; color: #94a3b8; margin-bottom: 40px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
            .card { background: #1e293b; padding: 25px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); transition: transform 0.2s; }
            .card.flipkart { border-top: 5px solid #facc15; }
            .card.amazon { border-top: 5px solid #f97316; }
            .card:hover { transform: translateY(-5px); }
            .platform { font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; color: #0f172a; font-weight: bold; display: inline-block; padding: 4px 10px; border-radius: 20px; margin-bottom: 15px;}
            .card.flipkart .platform { background: #facc15; }
            .card.amazon .platform { background: #f97316; }
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
            css_class = "flipkart" if platform == 'Flipkart' else "amazon"
            
            if 'price_history' in item and len(item['price_history']) > 0:
                price = item['price_history'][-1]['price']
            else:
                price = item.get('start_price', 0)
            url = item.get('url', '#')
            
            if platform == 'Amazon':
                offers_text = "🚧 Offers Coming Soon"
            else:
                offers_count = len(item.get('latest_offers', []))
                offers_text = f"🎁 {offers_count} Offers Available" if offers_count > 0 else "No Special Offers"
            
            html += f"""
            <div class="card {css_class}">
                <div class="platform">{'🟡 ' if platform == 'Flipkart' else '🟠 '}{platform}</div>
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

def get_current_time_str():
    return get_ist_time().strftime("%d-%b %I:%M %p")

def extract_smart_price(text):
    text = text.replace(',', '')
    matches = re.findall(r'\d+', text)
    if matches:
        p = int(matches[0])
        if p > 500000:
            if len(matches) > 1: return int(matches[1])
        return p
    return None

# === HEADERS & API KEY ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-IN,en-US;q=0.9",
    "Connection": "keep-alive"
}
API_KEY = "b96371ea776a13335d3c6fd192254409" 

# === AMAZON HYBRID SCRAPER ===
def check_amazon_price(url):
    title, price, offers, img_url = "Amazon Product", None, [], "https://i.imgur.com/3Q9c4gN.png"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", id="productTitle")
            if t_el: title = t_el.text.strip()

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"): img_url = og_img.get("content")
        
        availability = soup.find("div", id="availability")
        if availability and re.search(r'currently unavailable|out of stock', availability.text, re.I):
            return title, "OOS", [], img_url
            
        p_el = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-size-medium a-color-price") or soup.find("span", class_="a-button-text")
        if p_el: price = extract_smart_price(p_el.text)
    except: pass

    if price: return title, price, offers, img_url
        
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", id="productTitle")
            if t_el: title = t_el.text.strip()
            
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"): img_url = og_img.get("content")
        
        availability = soup.find("div", id="availability")
        if availability and re.search(r'currently unavailable|out of stock', availability.text, re.I):
            return title, "OOS", [], img_url
            
        p_el = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-size-medium a-color-price")
        if p_el: price = extract_smart_price(p_el.text)
                
        return title, price, [], img_url
    except: return None, None, [], img_url

# === FLIPKART DOUBLE HYBRID SCRAPER ===
def check_flipkart_price(url):
    title, price, offers, img_url = "Flipkart Product", None, [], "https://i.imgur.com/E1z1j3Z.png"
    
    def is_flipkart_oos(soup_obj):
        page_text = soup_obj.get_text(separator=' ', strip=True).lower()
        if "this item is currently out of stock" in page_text: return True
        for btn in soup_obj.find_all('button'):
            if "notify me" in btn.get_text(strip=True).lower(): return True
        return False

    keywords = ["bank offer", "cashback", "special price", "partner offer", "discount"]
    exclude_words = ["exchange", "sign up"]

    try:
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
            if t_el: title = t_el.text.strip()

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"): img_url = og_img.get("content")

        if is_flipkart_oos(soup): return title, "OOS", [], img_url

        p_el = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if p_el: price = extract_smart_price(p_el.text)
        else:
            for tag in soup.find_all(['div', 'span']):
                text = tag.text.strip()
                if text.startswith('₹') and len(text) < 15:
                    val = extract_smart_price(text)
                    if val and val > 500:
                        price = val
                        break
                        
        for tag in soup.find_all(['li', 'span', 'div', 'p']):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords) and not any(ex in txt_lower for ex in exclude_words):
                if "T&C" in txt: txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers: offers.append(clean_txt)
    except: pass

    if price: return title, price, offers[:5], img_url
    
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"): title = og_title["content"].strip()
        else:
            t_el = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
            if t_el: title = t_el.text.strip()

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"): img_url = og_img.get("content")
        
        if is_flipkart_oos(soup): return title, "OOS", [], img_url

        p_el = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if p_el: price = extract_smart_price(p_el.text)
        else:
            for tag in soup.find_all(['div', 'span']):
                text = tag.text.strip()
                if text.startswith('₹') and len(text) < 15:
                    val = extract_smart_price(text)
                    if val and val > 500:
                        price = val
                        break
                            
        for tag in soup.find_all(['li', 'span', 'div', 'p']):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords) and not any(ex in txt_lower for ex in exclude_words):
                if "T&C" in txt: txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers: offers.append(clean_txt)
                        
        return title, price, offers[:5], img_url
    except: return None, None, [], img_url

# === CHART GENERATOR ENGINE ===
def generate_chart_url(price_history, title):
    labels = [h['date'].split()[0] for h in price_history]  
    data_points = [h['price'] for h in price_history]
    chart_config = {
        "type": "line",
        "data": { "labels": labels, "datasets": [{ "label": "Price (₹)", "data": data_points, "borderColor": "rgb(255, 99, 132)", "backgroundColor": "rgba(255, 99, 132, 0.2)", "fill": True, "tension": 0.4, "pointBackgroundColor": "blue", "pointRadius": 5 }] },
        "options": { "title": {"display": True, "text": title[:40] + "..."}, "scales": {"yAxes": [{"ticks": {"beginAtZero": False}}]} }
    }
    return f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(chart_config))}&w=600&h=400&bkg=white"

# === V2.0 UI HELPERS ===
def build_card_ui(item, expanded_offers=False):
    platform = item.get('platform', 'Amazon')
    badge = "🟡 [ FLIPKART DEAL ]" if platform == 'Flipkart' else "🟠 [ AMAZON DEAL ]"
    
    current_price = item['price_history'][-1]['price'] if 'price_history' in item and item['price_history'] else item.get('start_price', 0)
    old_price = item.get('start_price', current_price)
    
    card = f"{badge}\n━━━━━━━━━━━━━━━━━━━━\n📦 **{item['title'][:60]}...**\n\n"
    
    if current_price < old_price:
        card += f"💳 MRP/Old: ~₹{old_price}~\n💰 **Current: ₹{current_price}**\n🔻 `[ ₹{old_price - current_price} SAVED ]` 🔥\n"
    else:
        card += f"💰 **Price: ₹{current_price}**\n"
        
    if expanded_offers and platform == "Flipkart":
        offs = item.get('latest_offers', [])
        card += "\n> 🎁 **LIVE OFFERS:**\n" + ("\n".join([f"> ▪️ {o}" for o in offs]) if offs else "> No special offers right now.") + "\n"
    
    card += f"━━━━━━━━━━━━━━━━━━━━\n*⏱️ Last synced: {get_current_time_str()}*"
    return card

def get_action_keyboard(index, url, platform):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🛒 View Deal", url=url), InlineKeyboardButton("🎁 Offers", callback_data=f"off_{index}"))
    markup.row(InlineKeyboardButton("🔄 Check Price", callback_data=f"ref_{index}"), InlineKeyboardButton("📉 Graph", callback_data=f"hist_{index}"))
    markup.row(InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{index}"))
    return markup

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_msg = "👋 **Welcome to Deal Hunter V2.0!**\n\nApni Amazon ya Flipkart ki link bhej aur price drop track kar."
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 My Wishlist", callback_data="page_0"))
    markup.row(InlineKeyboardButton("🔄 Refresh All", callback_data="checkall"), InlineKeyboardButton("🗑️ Clear All", callback_data="clearall"))
    try: bot.send_photo(message.chat.id, "https://i.imgur.com/k2eA5Q7.png", caption=welcome_msg, parse_mode="Markdown", reply_markup=markup)
    except: bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['reset'])
def reset_data(message):
    chat_id = str(message.chat.id)
    data = load_data()
    data[chat_id] = []
    save_data(data)
    bot.reply_to(message, "🔥 Database clear! Ab naye links bhej kar check kar.")

@bot.message_handler(commands=['checknow'])
def show_checknow_handler(message):
    manual_price_check(message.chat.id)

@bot.message_handler(commands=['list'])
def show_list(message):
    handle_pagination(message.chat.id, 0)

# === PAGINATION SYSTEM (FIXED BUG 2) ===
def handle_pagination(chat_id_raw, page):
    chat_id = str(chat_id_raw)
    data = load_data()
    items = data.get(chat_id, [])
    if not items:
        bot.send_message(chat_id, "📭 Teri Wishlist khali hai! Koi link bhej.")
        return
        
    ITEMS_PER_PAGE = 5
    total_pages = max(1, (len(items) - 1) // ITEMS_PER_PAGE + 1)
    
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = items[start_idx:end_idx]
    
    bot.send_message(chat_id, f"📋 **Teri Wishlist & Tracking List (Page {page+1}/{total_pages})**", parse_mode="Markdown")
    
    for i, item in enumerate(page_items):
        actual_idx = start_idx + i
        card_text = build_card_ui(item)
        markup = get_action_keyboard(actual_idx, item['url'], item['platform'])
        try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)

    nav_markup = InlineKeyboardMarkup()
    row = []
    if page > 0: row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    if page < total_pages - 1: row.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    if row: # FIX 2: Correct navigation condition check
        nav_markup.row(*row)
        bot.send_message(chat_id, "Navigation:", reply_markup=nav_markup)

# === CALLBACK HANDLER (FIXED BUG 3) ===
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id)
    chat_id = str(call.message.chat.id)
    data = load_data()
    
    if call.data.startswith("page_"):
        handle_pagination(chat_id, int(call.data.split("_")[1]))
        return
    elif call.data == "checkall":
        manual_price_check(chat_id)
        return
    elif call.data == "clearall":
        data[chat_id] = []
        save_data(data)
        bot.send_message(chat_id, "🔥 Wishlist clear ho gayi!")
        return
        
    try:
        action, idx_str = call.data.split('_')
        item_number = int(idx_str)
        
        if chat_id not in data or item_number >= len(data[chat_id]):
            bot.send_message(chat_id, "❌ Ye item ab list mein nahi hai.")
            return
            
        item = data[chat_id][item_number]
        platform = item.get('platform', 'Unknown')
        
        if action == "hist":
            bot.send_message(chat_id, "📊 Graph laa raha hoon...")
            chart_url = generate_chart_url(item['price_history'], item['title'])
            prices = [h['price'] for h in item['price_history']]
            res = f"📉 **PRICE HISTORY REPORT**\n📦 {item['title'][:50]}...\n----------------------------------------\n"
            res += f"🔥 **Lowest:** ₹{min(prices)} | 📈 **Highest:** ₹{max(prices)}\n"
            bot.send_photo(chat_id, chart_url, caption=res, parse_mode='Markdown')
            
        elif action == "off":
            if platform == "Amazon": bot.send_message(chat_id, "🚧 Amazon Offers feature is Coming Soon!")
            else:
                new_card = build_card_ui(item, expanded_offers=True)
                try: bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=get_action_keyboard(item_number, item['url'], item['platform']))
                except: pass
                
        elif action == "ref":
            loading_msg = bot.send_message(chat_id, f"🔄 API se daam nikal raha hoon: {item['title'][:20]}...")
            t, p, o, img = check_amazon_price(item['url']) if platform == "Amazon" else check_flipkart_price(item['url'])
            
            try: bot.delete_message(chat_id, loading_msg.message_id)
            except: pass
            
            if p and p != "OOS":
                last_price = item['price_history'][-1]['price']
                if p != last_price:
                    item['price_history'].append({"date": get_current_time_str(), "price": p})
                item['latest_offers'] = o
                save_data(data)
                new_card = build_card_ui(item)
                
                # FIX 3: Exception handling for "Message is not modified"
                try:
                    bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=get_action_keyboard(item_number, item['url'], platform))
                    bot.send_message(chat_id, f"✅ **Update Success!**")
                except Exception as e:
                    bot.send_message(chat_id, f"✅ Daam abhi bhi **₹{p}** hi hai, koi naya badlaav nahi!")
            else:
                bot.send_message(chat_id, "⚠️ API Timeout ho gaya ya item OOS hai. Thodi der baad try kar!")
                
        elif action == "del":
            deleted_item = data[chat_id].pop(item_number)
            save_data(data)
            try: bot.delete_message(chat_id, call.message.message_id) 
            except: pass
            bot.send_message(chat_id, f"🗑️ Maine **{deleted_item['title'][:30]}...** ko hata diya.")
            
    except Exception as e: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    chat_id = str(message.chat.id)
    
    if "amazon" in url.lower() or "amzn" in url.lower(): platform = "Amazon"
    elif "flipkart" in url.lower() or "fkrt" in url.lower() or "fktr" in url.lower() or "dl.flipkart" in url.lower(): platform = "Flipkart"
    else:
        bot.reply_to(message, "⚠️ Bhai, abhi sirf Amazon aur Flipkart ke links bhej.")
        return

    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    ghost = bot.send_message(message.chat.id, f"🔍 {platform} par data check kar raha hoon... (Heavy page loading, thoda wait kar)")
    
    current_price, offers, title, img_url = None, [], "", ""
    for attempt in range(2): 
        if platform == "Amazon": title, current_price, offers, img_url = check_amazon_price(url)
        else: title, current_price, offers, img_url = check_flipkart_price(url)
        if current_price: break 
        else: time.sleep(3) 

    try: bot.delete_message(chat_id, ghost.message_id)
    except: pass

    if current_price == "OOS":
        bot.send_message(chat_id, "❌ **Bhai, tera bheja hua variant/color abhi OUT OF STOCK hai!**")
        return

    if current_price:
        data = load_data()
        if chat_id not in data: data[chat_id] = []
        new_item = {
            "url": url, "title": title, "start_price": current_price, "platform": platform,
            "price_history": [{"date": get_current_time_str(), "price": current_price}],
            "latest_offers": offers, "image_url": img_url, "error_count": 0 
        }
        data[chat_id].append(new_item)
        save_data(data)
        
        item_idx = len(data[chat_id]) - 1
        card_text = f"✅ **TRACKING ACTIVATED**\n{build_card_ui(new_item)}"
        markup = get_action_keyboard(item_idx, url, platform)
        
        try: bot.send_photo(chat_id, img_url, caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)
    else: bot.send_message(chat_id, "⚠️ Bhai lagta hai server thoda busy hai ya timeout ho gaya. Ek baar fir se link bhej de!")

# === CHECK ALL (FIXED BUG 1) ===
def manual_price_check(chat_id_raw):
    chat_id_str = str(chat_id_raw) # FIX 1: Type mismatch error fix
    bot.send_message(chat_id_str, "⚙️ Backend check shuru kar diya! Prices scrape kar raha hoon, thoda wait kar...")
    data = load_data()
    
    if chat_id_str not in data or not data[chat_id_str]:
        bot.send_message(chat_id_str, "❌ Teri list khali hai. Pehle koi Flipkart ya Amazon ka link toh bhej!")
        return
        
    for i, item in enumerate(data[chat_id_str]):
        platform = item.get('platform', 'Amazon')
        if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item['url'])
        elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item['url'])
            
        if new_price == "OOS":
             bot.send_message(chat_id_str, f"🚫 **OUT OF STOCK ALERT**\n{item['title'][:30]}...")
             continue
             
        if not new_price:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Manual Retry", callback_data=f"ref_{i}"))
            bot.send_message(chat_id_str, f"⚠️ API Timeout: {item['title'][:30]}...", reply_markup=markup)
            continue
             
        if new_price:
            last_recorded_price = item['price_history'][-1]['price'] if 'price_history' in item and item['price_history'] else item.get('start_price', 0)
            if platform == "Flipkart" and offers: item['latest_offers'] = offers
            
            if new_price != last_recorded_price:
                item['price_history'].append({"date": get_current_time_str(), "price": new_price})
                save_data(data)
                alert_card = f"🚨 **DEAL ALERT! Price Changed**\n{build_card_ui(item)}"
                try: bot.send_photo(chat_id_str, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], platform))
                except: bot.send_message(chat_id_str, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], platform))
    
    bot.send_message(chat_id_str, "✅ Manual check poora ho gaya, report de di maine!")

# === SCHEDULED ROUTINE CHECKER ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        if ist_now.hour in [0, 6, 12, 18] and ist_now.minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{ist_now.hour}"
            if check_key not in checked_keys:
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
                                    added_date = datetime.strptime(f"{first_date_str} {ist_now.year}", "%d-%b %I:%M %p %Y")
                                    if (ist_now - added_date).days >= 30: is_expired = True
                                except: pass
                        if is_expired:
                            changes_made = True
                            try: bot.send_message(chat_id, f"⏳ **Tracking Expired!**\n30 din poore ho gaye, maine yeh item hata diya hai:\n🗑️ {item['title'][:40]}...")
                            except: pass
                        else: valid_items.append(item) 
                    data[chat_id] = valid_items 
                
                for chat_id, items in data.items():
                    for i, item in enumerate(items):
                        try:
                            platform = item.get('platform', 'Amazon')
                            if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item['url'])
                            elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item['url'])
                            else: continue
                                
                            if new_price == "OOS": continue
                                
                            if new_price is None:
                                item['error_count'] = item.get('error_count', 0) + 1
                                if item['error_count'] == 3:
                                    try: bot.send_message(chat_id, f"⚠️ *Maintenance Alert:*\nTere product '{item['title'][:30]}...' ka link check nahi ho pa raha.", parse_mode="Markdown")
                                    except: pass
                                    if ADMIN_CHAT_ID:
                                        try: bot.send_message(ADMIN_CHAT_ID, f"🚨 *ADMIN ALERT: API FAILED 3 TIMES*\nLink: {item['url']}\nUser: {chat_id}", parse_mode="Markdown")
                                        except: pass
                                changes_made = True
                                continue
                            
                            item['error_count'] = 0
                                
                            if new_price:
                                if platform == "Flipkart" and offers: item['latest_offers'] = offers
                                if 'price_history' not in item: item['price_history'] = [{"date": "Old Data", "price": item.get('start_price', new_price)}]
                                last_recorded_price = item['price_history'][-1]['price']
                                
                                if new_price != last_recorded_price:
                                    item['price_history'].append({"date": get_current_time_str(), "price": new_price})
                                    changes_made = True
                                    alert_card = f"🚨 **AUTO-DROP DETECTED!**\n{build_card_ui(item)}"
                                    try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], platform))
                                    except: bot.send_message(chat_id, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], platform))
                        except Exception as e: pass
                            
                if changes_made: save_data(data)
                checked_keys.add(check_key)
        time.sleep(60) 

# === START ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    print("🚀 Harsh's Bot Online: FULL V2.0 EDITION!")
    bot.infinity_polling()
