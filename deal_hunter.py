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
import uuid 

# === TOKENS & SETUP ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "TERA_CHAT_ID_YAHAN_DAAL") 
bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# === THREAD SAFETY LOCK ===
db_lock = threading.Lock()

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
        <title>Harsh's Admin Dashboard V2.4</title>
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
        for item in items:
            has_items = True
            item_id = item.get('id', '')
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
                    <form action="/delete/{chat_id}/{item_id}" method="POST" style="flex: 1; margin: 0; display: flex;">
                        <button type="submit" class="btn btn-danger" style="width: 100%;">🗑️ Delete</button>
                    </form>
                </div>
            </div>
            """
    if not has_items:
        html += "<div class='empty'><h2>Dashboard is empty! Add links via Telegram bot.</h2></div>"
    html += "</div></body></html>"
    return html

@app.route('/delete/<chat_id>/<item_id>', methods=['POST'])
def admin_delete(chat_id, item_id):
    fresh_data = load_data()
    if chat_id in fresh_data:
        for i, item in enumerate(fresh_data[chat_id]):
            if item.get('id') == item_id:
                deleted_item = fresh_data[chat_id].pop(i)
                save_data(fresh_data)
                try:
                    bot.send_message(chat_id, f"⚠️ **Admin Action:** Tera item '{deleted_item['title'][:30]}...' list se hata diya gaya hai.")
                except: pass
                break
    return redirect(url_for('home'))

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# === DATABASE FUNCTIONS WITH LOCKS ===
def load_data():
    with db_lock:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                try: 
                    data = json.load(f)
                    modified = False
                    for cid in data:
                        for itm in data[cid]:
                            if 'id' not in itm:
                                itm['id'] = str(uuid.uuid4())[:8]
                                modified = True
                    if modified:
                        with open(DATA_FILE, "w") as fw:
                            json.dump(data, fw, indent=4)
                    return data
                except: return {}
        return {}

def save_data(data):
    with db_lock:
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

def resolve_url(url):
    try:
        if "dl.flipkart" in url or "amzn.to" in url or "flipkart.com/s/" in url:
            res = requests.head(url, allow_redirects=True, timeout=7)
            url = res.url
            
        parsed = urllib.parse.urlparse(url)
        if "flipkart" in url.lower():
            qs = urllib.parse.parse_qs(parsed.query)
            pid = qs.get('pid')
            if pid:
                return f"https://www.flipkart.com{parsed.path}?pid={pid[0]}"
            return f"https://www.flipkart.com{parsed.path}"
        elif "amazon" in url.lower() or "amzn" in url.lower():
            return f"https://www.amazon.in{parsed.path}"
        return url
    except:
        return url

# === HEADERS & API KEY ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en-US;q=0.9",
    "Connection": "keep-alive"
}
API_KEY = "b96371ea776a13335d3c6fd192254409" 

# === AMAZON HYBRID SCRAPER (SUPERCHARGED) ===
def check_amazon_price(url):
    title, price, offers, img_url = "Amazon Product", None, [], "https://i.imgur.com/3Q9c4gN.png"
    
    def extract_amz_data(soup_obj):
        t, p, img = "Amazon Product", None, "https://i.imgur.com/3Q9c4gN.png"
        t_el = soup_obj.find("span", id="productTitle")
        if t_el: t = t_el.text.strip()
            
        img_el = soup_obj.find("img", id="landingImage")
        if img_el and img_el.get("src"): img = img_el.get("src")
            
        avail = soup_obj.find("div", id="availability")
        if avail and re.search(r'currently unavailable|out of stock', avail.text, re.I):
            return t, "OOS", img
            
        price_selectors = [
            soup_obj.find("span", class_="a-price-whole"),
            soup_obj.find("span", class_="a-offscreen"),
            soup_obj.find("span", id="priceblock_ourprice"),
            soup_obj.find("span", id="priceblock_dealprice"),
            soup_obj.find("span", class_="a-size-medium a-color-price"),
            soup_obj.find("div", id="corePriceDisplay_desktop_feature_div")
        ]
        
        for selector in price_selectors:
            if selector and selector.text.strip():
                val = extract_smart_price(selector.text)
                if val and val > 0:
                    p = val
                    break
                    
        return t, p, img

    try:
        amz_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        response = requests.get(url, headers=amz_headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        if "captcha" in soup.text.lower() and "type the characters" in soup.text.lower():
            price = None 
        else:
            title, price, img_url = extract_amz_data(soup)
    except: pass

    if price and price != "OOS": return title, price, offers, img_url
        
    try:
        params = {'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}
        response = requests.get('http://api.scraperapi.com', params=params, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        title, price, img_url = extract_amz_data(soup)
    except: pass

    return title, price, offers, img_url

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
    
    if item.get('is_oos'):
        card += "🚫 **STATUS: OUT OF STOCK**\n"
    elif current_price < old_price:
        card += f"💳 MRP/Old: ~₹{old_price}~\n💰 **Current: ₹{current_price}**\n🔻 `[ ₹{old_price - current_price} SAVED ]` 🔥\n"
    else:
        card += f"💰 **Price: ₹{current_price}**\n"
        
    if expanded_offers and platform == "Flipkart":
        offs = item.get('latest_offers', [])
        card += "\n> 🎁 **LIVE OFFERS:**\n" + ("\n".join([f"> ▪️ {o}" for o in offs]) if offs else "> No special offers right now.") + "\n"
    
    card += f"━━━━━━━━━━━━━━━━━━━━\n*⏱️ Last synced: {get_current_time_str()}*"
    return card

def get_action_keyboard(item_id, url, platform, expanded_offers=False):
    markup = InlineKeyboardMarkup()
    offer_text = "🫣 Hide Offers" if expanded_offers else "🎁 Show Offers"
    markup.row(InlineKeyboardButton("🛒 View Deal", url=url), InlineKeyboardButton(offer_text, callback_data=f"off_{item_id}"))
    markup.row(InlineKeyboardButton("🔄 Check Price", callback_data=f"ref_{item_id}"), InlineKeyboardButton("📉 Graph", callback_data=f"hist_{item_id}"))
    markup.row(InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{item_id}"))
    return markup

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_msg = "👋 **Welcome to Deal Hunter V2.4!**\n\nApni Amazon ya Flipkart ki link bhej aur price drop track kar."
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 My Wishlist", callback_data="page_0"))
    markup.row(InlineKeyboardButton("🔄 Refresh All", callback_data="checkall"), InlineKeyboardButton("🗑️ Clear All", callback_data="clearall"))
    try: bot.send_photo(message.chat.id, "https://i.imgur.com/k2eA5Q7.png", caption=welcome_msg, parse_mode="Markdown", reply_markup=markup)
    except: bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['reset'])
def reset_data(message):
    chat_id = str(message.chat.id)
    fresh_data = load_data()
    fresh_data[chat_id] = []
    save_data(fresh_data)
    bot.reply_to(message, "🔥 Database clear! Ab naye links bhej kar check kar.")

@bot.message_handler(commands=['checknow'])
def show_checknow_handler(message):
    threading.Thread(target=manual_price_check, args=(message.chat.id,), daemon=True).start()

@bot.message_handler(commands=['list'])
def show_list(message):
    handle_pagination(message.chat.id, 0)

def handle_pagination(chat_id_raw, page, call=None):
    chat_id = str(chat_id_raw)
    data = load_data()
    items = data.get(chat_id, [])
    if not items:
        if call:
            bot.send_message(chat_id, "📭 Teri Wishlist khali hai!")
        else:
            bot.send_message(chat_id, "📭 Teri Wishlist khali hai! Koi link bhej.")
        return
        
    total_pages = len(items)
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    item = items[page]
    card_text = f"📋 **Teri Wishlist ({page+1}/{total_pages})**\n\n{build_card_ui(item)}"
    markup = get_action_keyboard(item['id'], item['url'], item['platform'])

    nav_buttons = []
    if page > 0: 
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    if page < total_pages - 1: 
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    if call:
        try:
            bot.edit_message_media(
                chat_id=chat_id,
                message_id=call.message.message_id,
                media=InputMediaPhoto(media=item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown"),
                reply_markup=markup
            )
        except:
            try: bot.delete_message(chat_id, call.message.message_id)
            except: pass
            try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown", reply_markup=markup)
            except: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)
    else:
        try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)

# === CALLBACK HANDLER ===
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id)
    chat_id = str(call.message.chat.id)
    data = load_data()
    
    if call.data.startswith("page_"):
        handle_pagination(chat_id, int(call.data.split("_")[1]), call=call)
        return
    elif call.data == "checkall":
        threading.Thread(target=manual_price_check, args=(chat_id,), daemon=True).start()
        return
    elif call.data == "clearall":
        fresh_data = load_data()
        fresh_data[chat_id] = []
        save_data(fresh_data)
        bot.send_message(chat_id, "🔥 Wishlist clear ho gayi!")
        return
        
    try:
        action, item_id = call.data.split('_')
        
        item = None
        item_index = -1
        if chat_id in data:
            for i, itm in enumerate(data[chat_id]):
                if itm.get('id') == item_id:
                    item = itm
                    item_index = i
                    break
                    
        if not item:
            bot.send_message(chat_id, "❌ Ye item ab list mein nahi hai.")
            return
            
        platform = item.get('platform', 'Unknown')
        
        if action == "hist":
            bot.send_message(chat_id, "📊 Graph laa raha hoon...")
            chart_url = generate_chart_url(item['price_history'], item['title'])
            prices = [h['price'] for h in item['price_history']]
            res = f"📉 **PRICE HISTORY REPORT**\n📦 {item['title'][:50]}...\n----------------------------------------\n"
            res += f"🔥 **Lowest:** ₹{min(prices)} | 📈 **Highest:** ₹{max(prices)}\n"
            bot.send_photo(chat_id, chart_url, caption=res, parse_mode='Markdown')
            time.sleep(1.5)
            
        elif action == "off":
            if platform == "Amazon": bot.send_message(chat_id, "🚧 Amazon Offers feature is Coming Soon!")
            else:
                is_currently_expanded = "LIVE OFFERS:" in (call.message.caption or "")
                new_expanded_state = not is_currently_expanded
                
                new_card = f"📋 **Teri Wishlist ({item_index+1}/{len(data[chat_id])})**\n\n{build_card_ui(item, expanded_offers=new_expanded_state)}"
                markup = get_action_keyboard(item_id, item['url'], item['platform'], expanded_offers=new_expanded_state)
                
                nav_buttons = []
                if item_index > 0: 
                    nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{item_index-1}"))
                if item_index < len(data[chat_id]) - 1: 
                    nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{item_index+1}"))
                if nav_buttons: markup.row(*nav_buttons)
                
                try: bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=markup)
                except: pass
                
        elif action == "ref":
            loading_msg = bot.send_message(chat_id, f"🔄 API se daam nikal raha hoon: {item['title'][:20]}...")
            t, p, o, img = check_amazon_price(item['url']) if platform == "Amazon" else check_flipkart_price(item['url'])
            
            try: bot.delete_message(chat_id, loading_msg.message_id)
            except: pass
            
            fresh_data = load_data()
            if p == "OOS":
                if chat_id in fresh_data:
                    for i, f_item in enumerate(fresh_data[chat_id]):
                        if f_item['id'] == item_id:
                            fresh_data[chat_id][i]['is_oos'] = True
                            save_data(fresh_data)
                            item = fresh_data[chat_id][i]
                            break
                bot.send_message(chat_id, f"🚫 **OUT OF STOCK ALERT**\nBhai tera item OOS ho chuka hai.")
                time.sleep(1.5)
            elif p:
                if chat_id in fresh_data:
                    for i, f_item in enumerate(fresh_data[chat_id]):
                        if f_item['id'] == item_id:
                            last_price = f_item['price_history'][-1]['price'] if 'price_history' in f_item and f_item['price_history'] else f_item.get('start_price', 0)
                            if p != last_price:
                                f_item['price_history'].append({"date": get_current_time_str(), "price": p})
                            f_item['latest_offers'] = o
                            
                            if f_item.get('is_oos'):
                                f_item['is_oos'] = False
                                try: bot.send_message(chat_id, f"🎉 **BACK IN STOCK!**\n📦 {f_item['title'][:40]}... ab wapas available hai!")
                                except: pass
                                time.sleep(1.5)
                                
                            save_data(fresh_data)
                            item = f_item 
                            break
                            
                new_card = f"📋 **Teri Wishlist ({item_index+1}/{len(fresh_data[chat_id])})**\n\n{build_card_ui(item)}"
                markup = get_action_keyboard(item_id, item['url'], platform)
                nav_buttons = []
                if item_index > 0: nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{item_index-1}"))
                if item_index < len(fresh_data[chat_id]) - 1: nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{item_index+1}"))
                if nav_buttons: markup.row(*nav_buttons)
                
                try:
                    bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=markup)
                    bot.send_message(chat_id, f"✅ **Update Success!**")
                except Exception as e:
                    bot.send_message(chat_id, f"✅ Daam abhi bhi **₹{p}** hi hai, koi naya badlaav nahi!")
            else:
                bot.send_message(chat_id, "⚠️ API Timeout ho gaya. Thodi der baad try kar!")
                
        elif action == "del":
            fresh_data = load_data()
            if chat_id in fresh_data:
                for i, f_item in enumerate(fresh_data[chat_id]):
                    if f_item['id'] == item_id:
                        fresh_data[chat_id].pop(i)
                        save_data(fresh_data)
                        break
            try: bot.delete_message(chat_id, call.message.message_id) 
            except: pass
            bot.send_message(chat_id, f"🗑️ Maine product ko wishlist se hata diya.")
            handle_pagination(chat_id, max(0, item_index - 1))
            
    except Exception as e: pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    chat_id = str(message.chat.id)
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ Bhai, proper website ka link bhej (http/https hona zaroori hai).")
        return
    
    if "amazon" in url.lower() or "amzn" in url.lower(): platform = "Amazon"
    elif "flipkart" in url.lower() or "fkrt" in url.lower() or "fktr" in url.lower() or "dl.flipkart" in url.lower(): platform = "Flipkart"
    else:
        bot.reply_to(message, "⚠️ Bhai, abhi sirf Amazon aur Flipkart ke links bhej.")
        return

    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    url = resolve_url(url)
    
    data = load_data()
    if chat_id in data:
        for item in data[chat_id]:
            if url == item['url']:
                bot.send_message(chat_id, "⚠️ **Arey bhai!** Ye product/variant teri wishlist mein pehle se hi hai.")
                return

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
        fresh_data = load_data()
        if chat_id not in fresh_data: fresh_data[chat_id] = []
        new_id = str(uuid.uuid4())[:8] 
        
        new_item = {
            "id": new_id,  
            "url": url, "title": title, "start_price": current_price, "platform": platform,
            "price_history": [{"date": get_current_time_str(), "price": current_price}],
            "latest_offers": offers, "image_url": img_url, "error_count": 0, "is_oos": False
        }
        fresh_data[chat_id].append(new_item)
        save_data(fresh_data)
        
        card_text = f"✅ **TRACKING ACTIVATED**\n{build_card_ui(new_item)}"
        markup = get_action_keyboard(new_id, url, platform) 
        
        try: bot.send_photo(chat_id, img_url, caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)
    else: bot.send_message(chat_id, "⚠️ Bhai lagta hai server thoda busy hai ya timeout ho gaya. Ek baar fir se link bhej de!")

# === CHECK ALL ===
def manual_price_check(chat_id_raw):
    chat_id_str = str(chat_id_raw) 
    bot.send_message(chat_id_str, "⚙️ Backend check shuru kar diya! Prices scrape kar raha hoon, thoda wait kar...")
    data_snapshot = load_data()
    
    if chat_id_str not in data_snapshot or not data_snapshot[chat_id_str]:
        bot.send_message(chat_id_str, "❌ Teri list khali hai. Pehle koi Flipkart ya Amazon ka link toh bhej!")
        return
        
    for item in data_snapshot[chat_id_str]:
        platform = item.get('platform', 'Amazon')
        item_id = item.get('id', '')
        
        if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item['url'])
        elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item['url'])
            
        if new_price == "OOS":
             fresh_data = load_data()
             if chat_id_str in fresh_data:
                 for i, f_item in enumerate(fresh_data[chat_id_str]):
                     if f_item['id'] == item_id:
                         if not f_item.get('is_oos'):
                             fresh_data[chat_id_str][i]['is_oos'] = True
                             save_data(fresh_data)
                             bot.send_message(chat_id_str, f"🚫 **OUT OF STOCK ALERT**\n{item['title'][:30]}...")
                             time.sleep(1.5) 
                         break
             continue
             
        if not new_price:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Manual Retry", callback_data=f"ref_{item_id}"))
            bot.send_message(chat_id_str, f"⚠️ API Timeout: {item['title'][:30]}...", reply_markup=markup)
            time.sleep(1.5)
            continue
             
        if new_price:
            last_recorded_price = item['price_history'][-1]['price'] if 'price_history' in item and item['price_history'] else item.get('start_price', 0)
            
            fresh_data = load_data()
            if chat_id_str in fresh_data:
                for i, f_item in enumerate(fresh_data[chat_id_str]):
                    if f_item['id'] == item_id:
                        if f_item.get('is_oos'):
                            fresh_data[chat_id_str][i]['is_oos'] = False
                            bot.send_message(chat_id_str, f"🎉 **BACK IN STOCK!**\n📦 {item['title'][:40]}... ab wapas stock mein hai!")
                            time.sleep(1.5)
                        
                        if new_price != last_recorded_price:
                            fresh_data[chat_id_str][i]['price_history'].append({"date": get_current_time_str(), "price": new_price})
                            if platform == "Flipkart" and offers: 
                                fresh_data[chat_id_str][i]['latest_offers'] = offers
                            item = fresh_data[chat_id_str][i]
                            
                            alert_card = f"🚨 **DEAL ALERT! Price Changed**\n{build_card_ui(item)}"
                            try: bot.send_photo(chat_id_str, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, item['url'], platform))
                            except: bot.send_message(chat_id_str, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, item['url'], platform))
                            time.sleep(1.5) 
                            
                        save_data(fresh_data)
                        break
    
    bot.send_message(chat_id_str, "✅ Manual check poora ho gaya, report de di maine!")

# === SCHEDULED ROUTINE CHECKER ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        if ist_now.hour in [0, 6, 12, 18] and ist_now.minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{ist_now.hour}"
            if check_key not in checked_keys:
                
                fresh_data = load_data()
                changes_made = False
                for chat_id in list(fresh_data.keys()):
                    valid_items = []
                    for item in fresh_data[chat_id]:
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
                            try: 
                                bot.send_message(chat_id, f"⏳ **Tracking Expired!**\n30 din poore ho gaye, maine yeh item hata diya hai:\n🗑️ {item['title'][:40]}...")
                                time.sleep(1.5)
                            except: pass
                        else: valid_items.append(item) 
                    fresh_data[chat_id] = valid_items 
                if changes_made: save_data(fresh_data)
                
                data_snapshot = load_data()
                for chat_id, items in data_snapshot.items():
                    for item_snap in items:
                        try:
                            item_id = item_snap.get('id', '')
                            platform = item_snap.get('platform', 'Amazon')
                            if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item_snap['url'])
                            elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item_snap['url'])
                            else: continue
                                
                            if new_price == "OOS":
                                c_data = load_data()
                                if chat_id in c_data:
                                    for i, ci in enumerate(c_data[chat_id]):
                                        if ci['id'] == item_id:
                                            if not ci.get('is_oos'):
                                                c_data[chat_id][i]['is_oos'] = True
                                                save_data(c_data)
                                                try:
                                                    bot.send_message(chat_id, f"🚫 **OUT OF STOCK ALERT**\nBhai tera ye item out of stock ho gaya hai:\n📦 {ci['title'][:40]}...")
                                                    time.sleep(1.5)
                                                except: pass
                                            break
                                continue
                                
                            if new_price is None:
                                c_data = load_data()
                                if chat_id in c_data:
                                    for i, ci in enumerate(c_data[chat_id]):
                                        if ci['id'] == item_id:
                                            c_data[chat_id][i]['error_count'] = c_data[chat_id][i].get('error_count', 0) + 1
                                            if c_data[chat_id][i]['error_count'] == 3:
                                                try: bot.send_message(chat_id, f"⚠️ *Maintenance Alert:*\nTere product '{ci['title'][:30]}...' ka link check nahi ho pa raha.", parse_mode="Markdown")
                                                except: pass
                                                time.sleep(1.5)
                                            save_data(c_data)
                                            break
                                continue
                                
                            if new_price:
                                last_recorded_price = item_snap['price_history'][-1]['price'] if 'price_history' in item_snap and item_snap['price_history'] else item_snap.get('start_price', 0)
                                
                                c_data = load_data()
                                if chat_id in c_data:
                                    for i, ci in enumerate(c_data[chat_id]):
                                        if ci['id'] == item_id:
                                            c_data[chat_id][i]['error_count'] = 0
                                            
                                            if c_data[chat_id][i].get('is_oos'):
                                                c_data[chat_id][i]['is_oos'] = False
                                                try:
                                                    bot.send_message(chat_id, f"🎉 **BACK IN STOCK!**\n📦 {ci['title'][:40]}... wapas stock mein aa gaya!")
                                                    time.sleep(1.5)
                                                except: pass
                                                
                                            if new_price != last_recorded_price:
                                                c_data[chat_id][i]['price_history'].append({"date": get_current_time_str(), "price": new_price})
                                                if platform == "Flipkart" and offers: c_data[chat_id][i]['latest_offers'] = offers
                                                
                                                alert_card = f"🚨 **AUTO-DROP DETECTED!**\n{build_card_ui(c_data[chat_id][i])}"
                                                try: bot.send_photo(chat_id, ci.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, ci['url'], platform))
                                                except: bot.send_message(chat_id, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, ci['url'], platform))
                                                time.sleep(1.5)
                                                
                                            save_data(c_data)
                                            break
                        except Exception as e: pass
                            
                checked_keys.add(check_key)
        time.sleep(60) 

# === START ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    print("🚀 Harsh's Bot Online: FULL V2.4 FINAL EDITION!")
    bot.infinity_polling()
