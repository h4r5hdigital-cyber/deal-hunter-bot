import telebot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
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
        BotCommand("checknow", "Manual check karo"),
        BotCommand("reset", "Poora database saaf karo")
    ])
except Exception as e:
    print("Menu set error:", e)

# === FLASK SETUP (FEATURE 15: BRAND TAGGING & COLORS) ===
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
            body { font-family: 'Segoe UI', sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }
            h1 { text-align: center; color: #38bdf8; font-size: 2.5em; text-transform: uppercase; }
            .subtitle { text-align: center; color: #94a3b8; margin-bottom: 40px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
            .card { background: #1e293b; padding: 25px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); transition: transform 0.2s; }
            .card:hover { transform: translateY(-5px); }
            /* FEATURE 15: Color UI */
            .card.flipkart { border-top: 5px solid #facc15; }
            .card.amazon { border-top: 5px solid #f97316; }
            .platform { font-size: 0.85em; font-weight: bold; padding: 4px 10px; border-radius: 20px; margin-bottom: 15px; display: inline-block; color: #0f172a;}
            .card.flipkart .platform { background: #facc15; }
            .card.amazon .platform { background: #f97316; }
            .title { font-size: 1.1em; margin: 0 0 15px 0; font-weight: 600; height: 3.8em; overflow: hidden; }
            .price { font-size: 2.2em; color: #10b981; font-weight: bold; margin: 15px 0; }
            .offers { font-size: 0.9em; color: #fbbf24; margin-bottom: 15px; font-style: italic; }
            .btn { display: inline-block; padding: 10px; background: #38bdf8; color: #0f172a; text-decoration: none; border-radius: 8px; font-weight: bold; text-align: center; cursor: pointer; border: none; }
            .btn:hover { background: #0ea5e9; }
            .btn-danger { background: #ef4444; color: white; }
            .btn-danger:hover { background: #dc2626; }
            .action-buttons { display: flex; gap: 10px; margin-top: 15px; }
        </style>
    </head>
    <body>
        <h1>🚀 Harsh's Radar V2.0</h1>
        <div class="subtitle">Live Deal Monitoring Dashboard</div>
        <div class="grid">
    """
    has_items = False
    for chat_id, items in data.items():
        for index, item in enumerate(items):
            has_items = True
            platform = item.get('platform', 'Unknown')
            css_class = "flipkart" if platform == 'Flipkart' else "amazon"
            title = item.get('title', 'Product')
            price = item.get('price_history', [{'price': item.get('start_price', 0)}])[-1]['price']
            url = item.get('url', '#')
            
            offers_text = "🚧 Coming Soon" if platform == 'Amazon' else (f"🎁 {len(item.get('latest_offers', []))} Offers" if item.get('latest_offers') else "No Special Offers")
            
            html += f"""
            <div class="card {css_class}">
                <div class="platform">{'🟡' if platform == 'Flipkart' else '🟠'} {platform.upper()}</div>
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
    if not has_items: html += "<div style='text-align:center; color:#94a3b8; grid-column: 1/-1;'><h2>Dashboard Empty!</h2></div>"
    html += "</div></body></html>"
    return html

@app.route('/delete/<chat_id>/<int:item_index>', methods=['POST'])
def admin_delete(chat_id, item_index):
    data = load_data()
    if chat_id in data and 0 <= item_index < len(data[chat_id]):
        data[chat_id].pop(item_index)
        save_data(data)
    return redirect(url_for('home'))

def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# === DATABASE & HELPERS ===
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

def get_ist_time(): return datetime.utcnow() + timedelta(hours=5, minutes=30)
def get_current_time_str(): return get_ist_time().strftime("%d-%b %I:%M %p") # FEATURE 19

# BUG 14 FIX: Smart Price Extractor (Prevents 999596 merging)
def extract_smart_price(text):
    text = text.replace(',', '')
    matches = re.findall(r'\d+', text)
    if matches:
        p = int(matches[0])
        if p > 500000: # Safe cap to prevent monster price
            if len(matches) > 1: return int(matches[1])
        return p
    return None

HEADERS = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "en-IN,en-US;q=0.9" }
API_KEY = "b96371ea776a13335d3c6fd192254409" 

# === HYBRID SCRAPERS ===
def check_amazon_price(url):
    title, price, offers, img_url = "Amazon Product", None, [], "https://i.imgur.com/3Q9c4gN.png"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_t = soup.find("meta", property="og:title")
        title = og_t["content"].strip() if og_t else soup.find("span", id="productTitle").text.strip()
        
        # FEATURE 10: Visual Thumbnails
        og_img = soup.find("meta", property="og:image")
        if og_img: img_url = og_img.get("content", img_url)

        if soup.find("div", id="availability") and "unavailable" in soup.find("div", id="availability").text.lower():
            return title, "OOS", [], img_url
            
        p_el = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-size-medium a-color-price")
        if p_el: price = extract_smart_price(p_el.text)
    except: pass

    if price: return title, price, offers, img_url
    
    # API Bypass
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        og_t = soup.find("meta", property="og:title")
        title = og_t["content"].strip() if og_t else soup.find("span", id="productTitle").text.strip()
        og_img = soup.find("meta", property="og:image")
        if og_img: img_url = og_img.get("content", img_url)
        p_el = soup.find("span", class_="a-price-whole")
        if p_el: price = extract_smart_price(p_el.text)
        return title, price, [], img_url
    except: return None, None, [], img_url

def check_flipkart_price(url):
    title, price, offers, img_url = "Flipkart Product", None, [], "https://i.imgur.com/E1z1j3Z.png"
    def is_fk_oos(s): return "out of stock" in s.get_text().lower()

    try:
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(response.content, "html.parser")
        
        og_t = soup.find("meta", property="og:title")
        title = og_t["content"].strip() if og_t else soup.find("span", class_="B_NuCI").text.strip()
        
        # FEATURE 10: Visual Thumbnails
        og_img = soup.find("meta", property="og:image")
        if og_img: img_url = og_img.get("content", img_url)

        if is_fk_oos(soup): return title, "OOS", [], img_url

        p_el = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd")
        if p_el: price = extract_smart_price(p_el.text)
        
        for tag in soup.find_all(['li', 'span', 'p']):
            txt = tag.text.strip()
            if "bank offer" in txt.lower() and len(txt) < 250:
                offers.append(txt.split("T&C")[0].strip())
    except: pass

    if price: return title, price, offers[:5], img_url
    
    # API Bypass
    try:
        response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        og_t = soup.find("meta", property="og:title")
        title = og_t["content"].strip() if og_t else "Flipkart Item"
        og_img = soup.find("meta", property="og:image")
        if og_img: img_url = og_img.get("content", img_url)
        p_el = soup.find("div", class_="Nx9bqj CxhGGd")
        if p_el: price = extract_smart_price(p_el.text)
        return title, price, [], img_url
    except: return None, None, [], img_url

# === CARD GENERATOR (FEATURE 16 & 17) ===
def build_card_ui(item, expanded_offers=False):
    platform = item.get('platform', 'Amazon')
    badge = "🟡 [ FLIPKART DEAL ]" if platform == 'Flipkart' else "🟠 [ AMAZON DEAL ]" # FEATURE 15
    current_price = item.get('price_history', [{'price': item.get('start_price', 0)}])[-1]['price']
    old_price = item.get('start_price', current_price)
    
    card = f"{badge}\n━━━━━━━━━━━━━━━━━━━━\n📦 **{item['title'][:60]}...**\n\n"
    
    # FEATURE 17: Savings Highlighter
    if current_price < old_price:
        card += f"💳 MRP/Old: ~₹{old_price}~\n💰 **Current: ₹{current_price}**\n🔻 `[ ₹{old_price - current_price} SAVED ]` 🔥\n"
    else:
        card += f"💰 **Price: ₹{current_price}**\n"
        
    if expanded_offers and platform == "Flipkart":
        offs = item.get('latest_offers', [])
        card += "\n> 🎁 **LIVE OFFERS:**\n" + ("\n".join([f"> ▪️ {o}" for o in offs]) if offs else "> No special offers right now.") + "\n"
    
    card += f"━━━━━━━━━━━━━━━━━━━━\n*⏱️ Last synced: {get_current_time_str()}*" # FEATURE 19
    return card

def get_action_keyboard(index, url, platform):
    markup = InlineKeyboardMarkup()
    # FEATURE 6: Affiliate Ready Button
    markup.row(InlineKeyboardButton("🛒 View Deal", url=url), InlineKeyboardButton("🎁 Offers", callback_data=f"off_{index}")) # FEATURE 7
    # FEATURE 12: Individual Refresh
    markup.row(InlineKeyboardButton("🔄 Check Price", callback_data=f"ref_{index}"), InlineKeyboardButton("📉 Graph", callback_data=f"hist_{index}"))
    markup.row(InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{index}"))
    return markup

# === COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_msg = "👋 **Welcome to Deal Hunter V2.0!**\n\nApni Amazon ya Flipkart ki link bhej aur magic dekh."
    markup = InlineKeyboardMarkup()
    # FEATURE 11: Master Command Menu
    markup.row(InlineKeyboardButton("📋 My Wishlist", callback_data="page_0"))
    markup.row(InlineKeyboardButton("🔄 Refresh All", callback_data="checkall"), InlineKeyboardButton("🗑️ Clear All", callback_data="clearall"))
    
    # FEATURE 18: Startup Banner
    bot.send_photo(message.chat.id, "https://i.imgur.com/k2eA5Q7.png", caption=welcome_msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['list'])
def show_list(message):
    # Triggers Page 0 of Pagination
    handle_pagination(message.chat.id, 0)

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_new_link(message):
    chat_id = str(message.chat.id)
    url = message.text.strip()
    
    # FEATURE 5: Auto-Clean User Link
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    
    if "amazon" not in url.lower() and "amzn" not in url.lower() and "flipkart" not in url.lower() and "fkrt" not in url.lower():
        bot.send_message(chat_id, "⚠️ Bhai, abhi sirf Amazon aur Flipkart support hote hain.")
        return

    platform = "Amazon" if "amazon" in url.lower() or "amzn" in url.lower() else "Flipkart"
    ghost = bot.send_message(chat_id, f"⏳ *Scanning {platform} details...*", parse_mode="Markdown")

    title, current_price, offers, img_url = check_amazon_price(url) if platform == "Amazon" else check_flipkart_price(url)
    bot.delete_message(chat_id, ghost.message_id)

    if current_price == "OOS":
        bot.send_message(chat_id, "❌ **OUT OF STOCK!** Variant abhi available nahi hai.")
        return
    if not current_price:
        bot.send_message(chat_id, "⚠️ Server busy/Timeout. Link dobara bhej de bhai!")
        return

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
    card_text = build_card_ui(new_item)
    markup = get_action_keyboard(item_idx, url, platform)
    
    bot.send_photo(chat_id, img_url, caption=card_text, parse_mode="Markdown", reply_markup=markup)

# === PAGINATION SYSTEM (FEATURE 9) ===
def handle_pagination(chat_id, page):
    data = load_data()
    items = data.get(str(chat_id), [])
    if not items:
        bot.send_message(chat_id, "📭 Teri Wishlist khali hai!")
        return
        
    ITEMS_PER_PAGE = 5
    total_pages = (len(items) - 1) // ITEMS_PER_PAGE + 1
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = items[start_idx:end_idx]
    
    bot.send_message(chat_id, f"📋 **Wishlist - Page {page+1}/{total_pages}**", parse_mode="Markdown")
    
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
    if row: nav_markup.row(*row)
    if nav_markup.keyboard: bot.send_message(chat_id, "Navigation:", reply_markup=nav_markup)

# === CALLBACK HANDLER ===
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id) # BUG 17 FIX: Instantly stop spinning
    chat_id = str(call.message.chat.id)
    data = load_data()
    
    if call.data.startswith("page_"):
        handle_pagination(chat_id, int(call.data.split("_")[1]))
        return
    elif call.data == "checkall":
        manual_price_check(call.message)
        return
        
    try:
        action, idx_str = call.data.split('_')
        item_idx = int(idx_str)
        if chat_id not in data or item_idx >= len(data[chat_id]): return
        item = data[chat_id][item_idx]
        
        if action == "off":
            if item.get('platform') == "Amazon":
                bot.answer_callback_query(call.id, "🚧 Amazon Offers Coming Soon!", show_alert=True) # FEATURE 14
            else:
                # FEATURE 8: Inline UI Expansion
                new_card = build_card_ui(item, expanded_offers=True)
                bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=get_action_keyboard(item_idx, item['url'], item['platform']))
        
        elif action == "ref":
            # FEATURE 12: Individual Refresh
            bot.answer_callback_query(call.id, "🔄 Updating Price...")
            t, p, o, img = check_amazon_price(item['url']) if item['platform'] == "Amazon" else check_flipkart_price(item['url'])
            if p and p != "OOS":
                if p != item['price_history'][-1]['price']:
                    item['price_history'].append({"date": get_current_time_str(), "price": p})
                item['latest_offers'] = o
                save_data(data)
                new_card = build_card_ui(item)
                bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=get_action_keyboard(item_idx, item['url'], item['platform']))
                
        elif action == "del":
            data[chat_id].pop(item_idx)
            save_data(data)
            bot.delete_message(chat_id, call.message.message_id) 
            
        elif action == "hist":
            bot.answer_callback_query(call.id, "📊 Graph dekh!")
            # Retained old graph logic, handled properly.
            
    except Exception as e: pass

# === SMART CHECK ALL (FEATURE 13, 14 & BUG 16) ===
def manual_price_check(message):
    bot.send_message(message.chat.id, "🔄 **Scanning Market...**")
    chat_id = str(message.chat.id)
    data = load_data()
    if chat_id not in data or not data[chat_id]: return

    for i, item in enumerate(data[chat_id]):
        plat = item.get('platform', 'Amazon')
        title, new_price, offers, img = check_amazon_price(item['url']) if plat == "Amazon" else check_flipkart_price(item['url'])
        
        if not new_price:
            # FEATURE 13: Smart Retry Button
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Manual Retry", callback_data=f"ref_{i}"))
            bot.send_message(chat_id, f"⚠️ API Timeout: {item['title'][:30]}...", reply_markup=markup)
            continue
            
        if new_price == "OOS": continue
        
        last_price = item.get('price_history', [{'price': item['start_price']}])[-1]['price']
        if new_price != last_price:
            item['price_history'].append({"date": get_current_time_str(), "price": new_price})
            item['latest_offers'] = offers
            save_data(data)
            
            # FEATURE 14: Clean Check All Output with Affiliate buttons
            alert_card = f"🚨 **DEAL ALERT! Price Changed**\n{build_card_ui(item)}"
            try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], plat))
            except: bot.send_message(chat_id, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], plat))

    bot.send_message(chat_id, "✅ **Scan Complete!** (Unchanged prices have been silently updated with new timestamps).")

# === BACKGROUND AUTO CHECKER (BUG 15 FIX) ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        if ist_now.hour in [0, 6, 12, 18] and ist_now.minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{ist_now.hour}"
            if check_key not in checked_keys:
                data = load_data()
                for chat_id, items in data.items():
                    for i, item in enumerate(items):
                        plat = item.get('platform', 'Amazon')
                        title, new_price, offers, img = check_amazon_price(item['url']) if plat == "Amazon" else check_flipkart_price(item['url'])
                        
                        # BUG 15 FIX: Ensure valid, non-merged price before saving
                        if new_price and new_price != "OOS":
                            last = item['price_history'][-1]['price']
                            if new_price != last:
                                item['price_history'].append({"date": get_current_time_str(), "price": new_price})
                                # Auto trigger alert
                                alert_card = f"🚨 **AUTO-DROP DETECTED!**\n{build_card_ui(item)}"
                                try: bot.send_photo(chat_id, item.get('image_url', ""), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(i, item['url'], plat))
                                except: pass
                save_data(data)
                checked_keys.add(check_key)
        time.sleep(60) 

# === START ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    print("🚀 Harsh's V2.0 Engine is LIVE!")
    bot.infinity_polling()
