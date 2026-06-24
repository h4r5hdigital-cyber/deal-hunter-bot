import telebot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import threading
import sqlite3
import logging
from flask import Flask, redirect, url_for, request
from datetime import datetime, timedelta
import urllib.parse
import re
import uuid 

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === TOKENS & SETUP ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN") 
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "TERA_CHAT_ID_YAHAN_DAAL") 
bot = telebot.TeleBot(BOT_TOKEN)
DB_PATH = "database.db"

# === DATABASE INITIALIZATION ===
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                id TEXT PRIMARY KEY,
                chat_id TEXT,
                url TEXT,
                title TEXT,
                platform TEXT,
                start_price INTEGER,
                latest_offers TEXT, -- Saved as JSON Array String
                image_url TEXT,
                error_count INTEGER DEFAULT 0,
                is_oos INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT,
                date TEXT,
                price INTEGER,
                FOREIGN KEY (item_id) REFERENCES wishlist(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    logging.info("SQLite Database initialized.")

# === DATABASE UTILITY FUNCTIONS ===
def db_add_item(chat_id, item_id, url, title, platform, start_price, offers, image_url, date_str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO wishlist (id, chat_id, url, title, platform, start_price, latest_offers, image_url, error_count, is_oos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (item_id, str(chat_id), url, title, platform, start_price, json.dumps(offers), image_url))
        cursor.execute("""
            INSERT INTO price_history (item_id, date, price)
            VALUES (?, ?, ?)
        """, (item_id, date_str, start_price))
        conn.commit()

def db_get_wishlist_items(chat_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wishlist WHERE chat_id = ?", (str(chat_id),))
        return [dict(row) for row in cursor.fetchall()]

def db_get_all_wishlist_items():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wishlist")
        return [dict(row) for row in cursor.fetchall()]

def db_get_item(item_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wishlist WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def db_delete_item(chat_id, item_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wishlist WHERE id = ? AND chat_id = ?", (item_id, str(chat_id)))
        cursor.execute("DELETE FROM price_history WHERE item_id = ?", (item_id,))
        conn.commit()

def db_clear_wishlist(chat_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM wishlist WHERE chat_id = ?", (str(chat_id),))
        ids = [row[0] for row in cursor.fetchall()]
        for item_id in ids:
            cursor.execute("DELETE FROM price_history WHERE item_id = ?", (item_id,))
        cursor.execute("DELETE FROM wishlist WHERE chat_id = ?", (str(chat_id),))
        conn.commit()

def db_get_price_history(item_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT date, price FROM price_history WHERE item_id = ? ORDER BY id ASC", (item_id,))
        return [{"date": row[0], "price": row[1]} for row in cursor.fetchall()]

def db_add_price_history(item_id, date_str, price):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO price_history (item_id, date, price) VALUES (?, ?, ?)", (item_id, date_str, price))
        conn.commit()

def db_update_item_state(item_id, error_count=None, is_oos=None, offers=None, title=None, image_url=None):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if error_count is not None:
            cursor.execute("UPDATE wishlist SET error_count = ? WHERE id = ?", (error_count, item_id))
        if is_oos is not None:
            cursor.execute("UPDATE wishlist SET is_oos = ? WHERE id = ?", (int(is_oos), item_id))
        if offers is not None:
            cursor.execute("UPDATE wishlist SET latest_offers = ? WHERE id = ?", (json.dumps(offers), item_id))
        if title is not None:
            cursor.execute("UPDATE wishlist SET title = ? WHERE id = ?", (title, item_id))
        if image_url is not None:
            cursor.execute("UPDATE wishlist SET image_url = ? WHERE id = ?", (image_url, item_id))
        conn.commit()

# === BOT MENU SETUP ===
try:
    bot.set_my_commands([
        BotCommand("start", "Bot ko zinda karo"),
        BotCommand("list", "Apni Wishlist dekho"),
        BotCommand("checknow", "Manual check karo (Test)"),
        BotCommand("reset", "Poora database saaf karo")
    ])
except Exception as e:
    logging.error(f"Menu set karne mein error: {e}")

# === FLASK SETUP ===
app = Flask(__name__)
@app.route('/')
def home():
    items = db_get_all_wishlist_items()
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Harsh's Admin Dashboard V2.6</title>
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
        <div class="subtitle">Live Monitoring & Control Panel (SQLite Powered)</div>
        <div class="grid">
    """
    has_items = False
    for item in items:
        has_items = True
        item_id = item['id']
        chat_id = item['chat_id']
        title = item.get('title', 'Product')
        platform = item.get('platform', 'Unknown')
        css_class = "flipkart" if platform == 'Flipkart' else "amazon"
        
        history = db_get_price_history(item_id)
        price = history[-1]['price'] if history else item.get('start_price', 0)
        url = item.get('url', '#')
        
        if platform == 'Amazon':
            offers_text = "🚧 Offers Coming Soon"
        else:
            try:
                offers_count = len(json.loads(item.get('latest_offers', '[]')))
            except Exception:
                offers_count = 0
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
    item = db_get_item(item_id)
    if item:
        db_delete_item(chat_id, item_id)
        try: 
            bot.send_message(chat_id, f"⚠️ **Admin Action:** Tera item '{item['title'][:30]}...' list se hata diya gaya hai.")
        except Exception as e: 
            logging.error(f"Failed to send admin action message: {e}")
    return redirect(url_for('home'))

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# === HELPERS ===
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

# 🚀 BUG FIX 1: Canonical Redirect Resolver for Amazon & Flipkart
def resolve_url(url):
    try:
        if any(domain in url.lower() for domain in ["amzn.", "a.co", "dl.flipkart", "flipkart.com/s/"]):
            res = requests.head(url, allow_redirects=True, headers=HEADERS, timeout=10)
            url = res.url

        parsed = urllib.parse.urlparse(url)
        # Amazon Link formatting
        if "amazon" in parsed.netloc.lower():
            asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', parsed.path)
            if asin_match:
                return f"https://www.amazon.in/dp/{asin_match.group(1)}"
            
        # Flipkart Link formatting
        elif "flipkart" in parsed.netloc.lower():
            qs = urllib.parse.parse_qs(parsed.query)
            pid = qs.get('pid')
            if pid:
                return f"https://www.flipkart.com{parsed.path}?pid={pid[0]}"
            return f"https://www.flipkart.com{parsed.path}"
        return url
    except Exception as e:
        logging.warning(f"URL Resolve failed for {url}: {e}")
        return url

# === HEADERS & API KEY ===
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en-US;q=0.9",
    "Connection": "keep-alive"
}
API_KEY = "b96371ea776a13335d3c6fd192254409" 

# Dynamic Selectors for fallback DOM checking
AMAZON_PRICE_SELECTORS = [
    ("span", {"class_": "a-price-whole"}),
    ("span", {"id": "priceblock_ourprice"}),
    ("span", {"id": "priceblock_dealprice"}),
    ("span", {"class_": "a-offscreen"})
]
FLIPKART_PRICE_SELECTORS = [
    ("div", {"class_": "Nx9bqj CxhGGd"}),
    ("div", {"class_": "_30jeq3 _16Jk6d"}),
    ("div", {"class_": "HLz_71"}),
    ("div", {"class_": "Nx9bqj"})
]

def parse_json_ld(soup):
    """Structured Metadata Parser (Google Search Standard Schema)"""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            if isinstance(data, list):
                data = data[0]
            if isinstance(data, dict) and data.get("@type") == "Product":
                title = data.get("name")
                offers = data.get("offers", {})
                price = None
                is_oos = False
                if isinstance(offers, dict):
                    price = offers.get("price")
                    availability = offers.get("availability", "")
                    if "OutOfStock" in availability or "InStoreOnly" in availability:
                        is_oos = True
                elif isinstance(offers, list) and len(offers) > 0:
                    price = offers[0].get("price")
                
                if price:
                    price = int(float(str(price).replace(",", "")))
                return title, price, is_oos
        except Exception:
            continue
    return None, None, False

def extract_price_from_soup(soup, selectors):
    for tag_name, attrs in selectors:
        bs4_attrs = {}
        for k, v in attrs.items():
            if k == 'class_': bs4_attrs['class'] = v
            else: bs4_attrs[k] = v
        el = soup.find(tag_name, **bs4_attrs)
        if el:
            val = extract_smart_price(el.text)
            if val and val > 10:
                return val
    return None

# === AMAZON PARSER ENGINE ===
def check_amazon_price(url):
    title, price, offers, img_url, is_oos = "Amazon Product", None, [], "https://i.imgur.com/3Q9c4gN.png", False
    
    def process_soup(soup):
        nonlocal title, price, img_url, is_oos
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        else:
            t_el = soup.find("span", id="productTitle")
            if t_el: title = t_el.text.strip()

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            img_url = og_img.get("content")
            
        avail_div = soup.find("div", id="availability")
        if avail_div and re.search(r'currently unavailable|out of stock', avail_div.text, re.I):
            is_oos = True
            
        # 1st preference Schema parsing
        ld_title, ld_price, ld_oos = parse_json_ld(soup)
        if ld_price:
            price = ld_price
            if ld_title: title = ld_title
            if ld_oos: is_oos = True
                
        # 2nd preference Tag Selector
        if not price:
            price = extract_price_from_soup(soup, AMAZON_PRICE_SELECTORS)

    try:
        response = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if response.status_code == 200:
            process_soup(BeautifulSoup(response.content, "html.parser"))
    except Exception as e:
        logging.error(f"Amazon direct parser error: {e}")

    # Fallback to ScraperAPI only if direct parsing fails
    if not price and not is_oos:
        try:
            logging.info(f"Direct request failed. Activating ScraperAPI for: {url}")
            response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
            if response.status_code == 200:
                process_soup(BeautifulSoup(response.content, "html.parser"))
        except Exception as e:
            logging.error(f"ScraperAPI fallback error: {e}")

    if is_oos:
        return title, "OOS", [], img_url
    return title, price, offers, img_url

# === FLIPKART PARSER ENGINE ===
def check_flipkart_price(url):
    title, price, offers, img_url, is_oos = "Flipkart Product", None, [], "https://i.imgur.com/E1z1j3Z.png", False
    
    def check_oos_text(soup_obj):
        page_text = soup_obj.get_text(separator=' ', strip=True).lower()
        if "this item is currently out of stock" in page_text: return True
        for btn in soup_obj.find_all('button'):
            if "notify me" in btn.get_text(strip=True).lower(): return True
        return False

    def process_soup(soup):
        nonlocal title, price, img_url, offers, is_oos
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        else:
            t_el = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
            if t_el: title = t_el.text.strip()

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            img_url = og_img.get("content")

        if check_oos_text(soup):
            is_oos = True

        ld_title, ld_price, ld_oos = parse_json_ld(soup)
        if ld_price:
            price = ld_price
            if ld_title: title = ld_title
            if ld_oos: is_oos = True

        if not price:
            price = extract_price_from_soup(soup, FLIPKART_PRICE_SELECTORS)

        # Extraction of Offers
        keywords = ["bank offer", "cashback", "special price", "partner offer", "discount"]
        exclude_words = ["exchange", "sign up"]
        for tag in soup.find_all(['li', 'span', 'div', 'p']):
            txt = tag.text.strip()
            txt_lower = txt.lower()
            if any(kw in txt_lower for kw in keywords) and not any(ex in txt_lower for ex in exclude_words):
                if "T&C" in txt: txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers: offers.append(clean_txt)

    try:
        response = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if response.status_code == 200:
            process_soup(BeautifulSoup(response.content, "html.parser"))
    except Exception as e:
        logging.error(f"Flipkart direct parser error: {e}")

    # Fallback to ScraperAPI
    if not price and not is_oos:
        try:
            logging.info(f"Direct request failed. Activating ScraperAPI for: {url}")
            response = requests.get('http://api.scraperapi.com', params={'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}, timeout=60)
            if response.status_code == 200:
                process_soup(BeautifulSoup(response.content, "html.parser"))
        except Exception as e:
            logging.error(f"ScraperAPI fallback error: {e}")

    if is_oos:
        return title, "OOS", [], img_url
    return title, price, offers[:5], img_url

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

# === BOT UI HELPERS ===
def build_card_ui(item, expanded_offers=False):
    platform = item.get('platform', 'Amazon')
    badge = "🟡 [ FLIPKART DEAL ]" if platform == 'Flipkart' else "🟠 [ AMAZON DEAL ]"
    
    price_history = db_get_price_history(item['id'])
    current_price = price_history[-1]['price'] if price_history else item.get('start_price', 0)
    old_price = item.get('start_price', current_price)
    
    card = f"{badge}\n━━━━━━━━━━━━━━━━━━━━\n📦 **{item['title'][:60]}...**\n\n"
    
    if item.get('is_oos'):
        card += "🚫 **STATUS: OUT OF STOCK**\n"
    elif current_price < old_price:
        card += f"💳 MRP/Old: ~₹{old_price}~\n💰 **Current: ₹{current_price}**\n🔻 `[ ₹{old_price - current_price} SAVED ]` 🔥\n"
    else:
        card += f"💰 **Price: ₹{current_price}**\n"
        
    if expanded_offers and platform == "Flipkart":
        try:
            offs = json.loads(item.get('latest_offers', '[]'))
        except Exception:
            offs = []
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
    welcome_msg = "👋 **Welcome to Deal Hunter V2.6!**\n\nApni Amazon ya Flipkart ki link bhej aur price drop track kar."
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 My Wishlist", callback_data="page_0"))
    markup.row(InlineKeyboardButton("🔄 Refresh All", callback_data="checkall"), InlineKeyboardButton("🗑️ Clear All", callback_data="clearall"))
    try: bot.send_photo(message.chat.id, "https://i.imgur.com/k2eA5Q7.png", caption=welcome_msg, parse_mode="Markdown", reply_markup=markup)
    except Exception: bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['reset'])
def reset_data(message):
    db_clear_wishlist(message.chat.id)
    bot.reply_to(message, "🔥 Database clear! Ab naye links bhej kar check kar.")

@bot.message_handler(commands=['checknow'])
def show_checknow_handler(message):
    threading.Thread(target=manual_price_check, args=(message.chat.id,), daemon=True).start()

@bot.message_handler(commands=['list'])
def show_list(message):
    handle_pagination(message.chat.id, 0)

def handle_pagination(chat_id_raw, page, call=None):
    chat_id = str(chat_id_raw)
    items = db_get_wishlist_items(chat_id)
    if not items:
        if call: bot.send_message(chat_id, "📭 Teri Wishlist khali hai!")
        else: bot.send_message(chat_id, "📭 Teri Wishlist khali hai! Koi link bhej.")
        return
        
    total_pages = len(items)
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    item = items[page]
    card_text = f"📋 **Teri Wishlist ({page+1}/{total_pages})**\n\n{build_card_ui(item)}"
    markup = get_action_keyboard(item['id'], item['url'], item['platform'])

    nav_buttons = []
    if page > 0: nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    if page < total_pages - 1: nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    if nav_buttons: markup.row(*nav_buttons)

    if call:
        try:
            bot.edit_message_media(
                chat_id=chat_id, message_id=call.message.message_id,
                media=InputMediaPhoto(media=item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown"),
                reply_markup=markup
            )
        except Exception:
            try: bot.delete_message(chat_id, call.message.message_id)
            except Exception: pass
            try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown", reply_markup=markup)
            except Exception: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)
    else:
        try: bot.send_photo(chat_id, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except Exception: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)

# === CALLBACK ROUTER (ASYNC BACKGROUND THREADS) ===
@bot.callback_query_handler(func=lambda call: True)
def handle_query_wrapper(call):
    try: bot.answer_callback_query(call.id)
    except Exception: pass
    # Background Thread pool logic so that Telegram doesn't block other users
    threading.Thread(target=handle_query, args=(call,), daemon=True).start()

def handle_query(call):
    chat_id = str(call.message.chat.id)
    
    if call.data.startswith("page_"):
        handle_pagination(chat_id, int(call.data.split("_")[1]), call=call)
        return
    elif call.data == "checkall":
        manual_price_check(chat_id)
        return
    elif call.data == "clearall":
        db_clear_wishlist(chat_id)
        bot.send_message(chat_id, "🔥 Wishlist clear ho gayi!")
        return
        
    try:
        action, item_id = call.data.split('_')
        item = db_get_item(item_id)
                    
        if not item:
            bot.send_message(chat_id, "❌ Ye item ab list mein nahi hai.")
            return
            
        platform = item.get('platform', 'Unknown')
        
        if action == "hist":
            bot.send_message(chat_id, "📊 Graph laa raha hoon...")
            history = db_get_price_history(item_id)
            chart_url = generate_chart_url(history, item['title'])
            prices = [h['price'] for h in history]
            res = f"📉 **PRICE HISTORY REPORT**\n📦 {item['title'][:50]}...\n----------------------------------------\n"
            res += f"🔥 **Lowest:** ₹{min(prices)} | 📈 **Highest:** ₹{max(prices)}\n"
            bot.send_photo(chat_id, chart_url, caption=res, parse_mode='Markdown')
            
        elif action == "off":
            if platform == "Amazon": 
                bot.send_message(chat_id, "🚧 Amazon Offers feature is Coming Soon!")
            else:
                is_currently_expanded = "LIVE OFFERS:" in (call.message.caption or "")
                new_expanded_state = not is_currently_expanded
                
                items = db_get_wishlist_items(chat_id)
                item_index = next((i for i, itm in enumerate(items) if itm['id'] == item_id), 0)
                
                new_card = f"📋 **Teri Wishlist ({item_index+1}/{len(items)})**\n\n{build_card_ui(item, expanded_offers=new_expanded_state)}"
                markup = get_action_keyboard(item_id, item['url'], item['platform'], expanded_offers=new_expanded_state)
                
                nav_buttons = []
                if item_index > 0: nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{item_index-1}"))
                if item_index < len(items) - 1: nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{item_index+1}"))
                if nav_buttons: markup.row(*nav_buttons)
                
                try: bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=markup)
                except Exception: pass
                
        elif action == "ref":
            loading_msg = bot.send_message(chat_id, f"🔄 API se daam nikal raha hoon: {item['title'][:20]}...")
            t, p, o, img = check_amazon_price(item['url']) if platform == "Amazon" else check_flipkart_price(item['url'])
            
            try: bot.delete_message(chat_id, loading_msg.message_id)
            except Exception: pass
            
            if p == "OOS":
                db_update_item_state(item_id, is_oos=True)
                updated_item = db_get_item(item_id)
                bot.send_message(chat_id, f"🚫 **OUT OF STOCK ALERT**\nBhai tera item OOS ho chuka hai.")
            elif p:
                db_update_item_state(item_id, error_count=0, is_oos=False, offers=o)
                history = db_get_price_history(item_id)
                last_price = history[-1]['price'] if history else item.get('start_price', 0)
                
                if p != last_price:
                    db_add_price_history(item_id, get_current_time_str(), p)
                    
                updated_item = db_get_item(item_id)
                items = db_get_wishlist_items(chat_id)
                item_index = next((i for i, itm in enumerate(items) if itm['id'] == item_id), 0)
                
                new_card = f"📋 **Teri Wishlist ({item_index+1}/{len(items)})**\n\n{build_card_ui(updated_item)}"
                markup = get_action_keyboard(item_id, updated_item['url'], platform)
                nav_buttons = []
                if item_index > 0: nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{item_index-1}"))
                if item_index < len(items) - 1: nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{item_index+1}"))
                if nav_buttons: markup.row(*nav_buttons)
                
                try:
                    bot.edit_message_caption(caption=new_card, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown', reply_markup=markup)
                    bot.send_message(chat_id, f"✅ **Update Success!**")
                except Exception:
                    bot.send_message(chat_id, f"✅ Daam abhi bhi **₹{p}** hi hai, koi naya badlaav nahi!")
            else:
                err_count = item.get('error_count', 0) + 1
                db_update_item_state(item_id, error_count=err_count)
                if err_count >= 3:
                    try: bot.send_message(chat_id, f"⚠️ *Maintenance Alert:*\nTere product '{item['title'][:30]}...' ka link check nahi ho pa raha. API fail ho rahi hai.", parse_mode="Markdown")
                    except Exception: pass
                    if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "TERA_CHAT_ID_YAHAN_DAAL":
                        try: bot.send_message(ADMIN_CHAT_ID, f"🚨 *ADMIN ALERT: API FAILED 3 TIMES*\nLink: {item['url']}\nUser: {chat_id}", parse_mode="Markdown")
                        except Exception: pass
                bot.send_message(chat_id, "⚠️ API Timeout ho gaya. Thodi der baad try kar!")
                
        elif action == "del":
            db_delete_item(chat_id, item_id)
            try: bot.delete_message(chat_id, call.message.message_id) 
            except Exception: pass
            bot.send_message(chat_id, f"🗑️ Maine product ko wishlist se hata diya.")
            handle_pagination(chat_id, 0)
            
    except Exception as e:
        logging.error(f"Callback query processing error: {e}")

# === MESSAGE RESOLVER (ASYNC NON-BLOCKING) ===
@bot.message_handler(func=lambda message: True)
def handle_message_wrapper(message):
    threading.Thread(target=handle_message, args=(message,), daemon=True).start()

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
    except Exception: pass

    url = resolve_url(url)
    
    # Check duplicate entry
    existing_items = db_get_wishlist_items(chat_id)
    for item in existing_items:
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
    except Exception: pass

    if current_price == "OOS":
        bot.send_message(chat_id, "❌ **Bhai, tera bheja hua variant/color abhi OUT OF STOCK hai!**")
        return

    if current_price:
        new_id = str(uuid.uuid4())[:8] 
        db_add_item(chat_id, new_id, url, title, platform, current_price, offers, img_url, get_current_time_str())
        
        saved_item = db_get_item(new_id)
        card_text = f"✅ **TRACKING ACTIVATED**\n{build_card_ui(saved_item)}"
        markup = get_action_keyboard(new_id, url, platform) 
        
        try: bot.send_photo(chat_id, img_url, caption=card_text, parse_mode="Markdown", reply_markup=markup)
        except Exception: bot.send_message(chat_id, card_text, parse_mode="Markdown", reply_markup=markup)
    else: 
        bot.send_message(chat_id, "⚠️ Bhai lagta hai server thoda busy hai ya timeout ho gaya. Ek baar fir se link bhej de!")

# === CHECK ALL IMPLEMENTATION ===
def manual_price_check(chat_id_raw):
    chat_id_str = str(chat_id_raw) 
    bot.send_message(chat_id_str, "⚙️ Backend check shuru kar diya! Prices scrape kar raha hoon, thoda wait kar...")
    items = db_get_wishlist_items(chat_id_str)
    
    if not items:
        bot.send_message(chat_id_str, "❌ Teri list khali hai. Pehle koi Flipkart ya Amazon ka link toh bhej!")
        return
        
    for item in items:
        platform = item.get('platform', 'Amazon')
        item_id = item['id']
        
        if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item['url'])
        elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item['url'])
            
        if new_price == "OOS":
            if not item.get('is_oos'):
                db_update_item_state(item_id, is_oos=True)
                bot.send_message(chat_id_str, f"🚫 **OUT OF STOCK ALERT**\n{item['title'][:30]}...")
            continue
             
        if not new_price:
            err_count = item.get('error_count', 0) + 1
            db_update_item_state(item_id, error_count=err_count)
            if err_count >= 3:
                try: bot.send_message(chat_id_str, f"⚠️ *Maintenance Alert:*\nTere product '{item['title'][:30]}...' ka link check nahi ho pa raha. API fail ho rahi hai.", parse_mode="Markdown")
                except Exception: pass
                if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "TERA_CHAT_ID_YAHAN_DAAL":
                    try: bot.send_message(ADMIN_CHAT_ID, f"🚨 *ADMIN ALERT: API FAILED 3 TIMES*\nLink: {item['url']}\nUser: {chat_id_str}", parse_mode="Markdown")
                    except Exception: pass
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Manual Retry", callback_data=f"ref_{item_id}"))
            bot.send_message(chat_id_str, f"⚠️ API Timeout: {item['title'][:30]}...", reply_markup=markup)
            continue
             
        if new_price:
            history = db_get_price_history(item_id)
            last_recorded_price = history[-1]['price'] if history else item.get('start_price', 0)
            
            db_update_item_state(item_id, error_count=0) # Success reset
            
            if item.get('is_oos'):
                db_update_item_state(item_id, is_oos=False)
                bot.send_message(chat_id_str, f"🎉 **BACK IN STOCK!**\n📦 {item['title'][:40]}... ab wapas stock mein hai!")
            
            if new_price != last_recorded_price:
                db_add_price_history(item_id, get_current_time_str(), new_price)
                if platform == "Flipkart" and offers: 
                    db_update_item_state(item_id, offers=offers)
                
                updated_item = db_get_item(item_id)
                alert_card = f"🚨 **DEAL ALERT! Price Changed**\n{build_card_ui(updated_item)}"
                try: bot.send_photo(chat_id_str, item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, item['url'], platform))
                except Exception: bot.send_message(chat_id_str, alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item_id, item['url'], platform))
    
    bot.send_message(chat_id_str, "✅ Manual check poora ho gaya, report de di maine!")

# === SCHEDULED ROUTINE CHECKER ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        if ist_now.hour in [0, 6, 12, 18] and ist_now.minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{ist_now.hour}"
            if check_key not in checked_keys:
                
                # Check expirations (30 days logic)
                all_items = db_get_all_wishlist_items()
                for item in all_items:
                    history = db_get_price_history(item['id'])
                    if history:
                        first_date_str = history[0]['date']
                        try:
                            added_date = datetime.strptime(f"{first_date_str} {ist_now.year}", "%d-%b %I:%M %p %Y")
                            if (ist_now - added_date).days >= 30:
                                db_delete_item(item['chat_id'], item['id'])
                                try: bot.send_message(item['chat_id'], f"⏳ **Tracking Expired!**\n30 din poore ho gaye, maine yeh item hata diya hai:\n🗑️ {item['title'][:40]}...")
                                except Exception: pass
                                continue
                        except Exception:
                            pass
                            
                    platform = item.get('platform', 'Amazon')
                    if platform == "Amazon": title, new_price, offers, img = check_amazon_price(item['url'])
                    elif platform == "Flipkart": title, new_price, offers, img = check_flipkart_price(item['url'])
                    else: continue
                        
                    if new_price == "OOS":
                        if not item.get('is_oos'):
                            db_update_item_state(item['id'], is_oos=True)
                            try: bot.send_message(item['chat_id'], f"🚫 **OUT OF STOCK ALERT**\nBhai tera ye item out of stock ho gaya hai:\n📦 {item['title'][:40]}...")
                            except Exception: pass
                        continue
                        
                    if new_price is None:
                        err_count = item.get('error_count', 0) + 1
                        db_update_item_state(item['id'], error_count=err_count)
                        if err_count >= 3:
                            try: bot.send_message(item['chat_id'], f"⚠️ *Maintenance Alert:*\nTere product '{item['title'][:30]}...' ka link check nahi ho pa raha.", parse_mode="Markdown")
                            except Exception: pass
                            if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "TERA_CHAT_ID_YAHAN_DAAL":
                                try: bot.send_message(ADMIN_CHAT_ID, f"🚨 *ADMIN ALERT: API FAILED 3 TIMES*\nLink: {item['url']}\nUser: {item['chat_id']}", parse_mode="Markdown")
                                except Exception: pass
                        continue
                        
                    if new_price:
                        history = db_get_price_history(item['id'])
                        last_recorded_price = history[-1]['price'] if history else item.get('start_price', 0)
                        
                        db_update_item_state(item['id'], error_count=0)
                        
                        if item.get('is_oos'):
                            db_update_item_state(item['id'], is_oos=False)
                            try: bot.send_message(item['chat_id'], f"🎉 **BACK IN STOCK!**\n📦 {item['title'][:40]}... wapas stock mein aa gaya!")
                            except Exception: pass
                            
                        if new_price != last_recorded_price:
                            db_add_price_history(item['id'], get_current_time_str(), new_price)
                            db_update_item_state(item['id'], offers=offers)
                            
                            updated_item = db_get_item(item['id'])
                            alert_card = f"🚨 **AUTO-DROP DETECTED!**\n{build_card_ui(updated_item)}"
                            try: bot.send_photo(item['chat_id'], item.get('image_url', "https://i.imgur.com/k2eA5Q7.png"), caption=alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item['id'], item['url'], platform))
                            except Exception:
                                try: bot.send_message(item['chat_id'], alert_card, parse_mode="Markdown", reply_markup=get_action_keyboard(item['id'], item['url'], platform))
                                except Exception: pass
                                
                checked_keys.add(check_key)
        time.sleep(30) 

# === ENGINE START ===
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    logging.info("🚀 Harsh's Tracker System Online: SQLite & Non-Blocking Active!")
    bot.infinity_polling()
