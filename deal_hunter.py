import telebot
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import threading
from flask import Flask

# === TOKENS & SETUP ===
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# === FLASK SETUP ===
app = Flask(__name__)
@app.route('/')
def home():
    return "🚀 Harsh ka Deal Hunter Bot 24/7 Zinda Hai!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# === DATABASE FUNCTIONS ===
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# === STEALTH HEADERS (Bypass Anti-Bot) ===
STEALTH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0'
}

# === AMAZON SCRAPER ENGINE ===
def check_amazon_price(url):
    try:
        response = requests.get(url, headers=STEALTH_HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.find("span", id="productTitle")
        title = title_element.text.strip() if title_element else "Amazon Product"
        
        price_element = soup.find("span", class_="a-price-whole")
        if price_element:
            price_text = price_element.text.replace(",", "").replace(".", "").strip()
            return title, int(price_text)
        return title, None
    except Exception as e:
        print("Amazon Scraping Error:", e)
        return None, None

# === FLIPKART SCRAPER ENGINE ===
def check_flipkart_price(url):
    try:
        response = requests.get(url, headers=STEALTH_HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Flipkart titles
        title_element = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
        title = title_element.text.strip() if title_element else "Flipkart Product"
        
        # Flipkart prices (Purane aur naye dono format)
        price_element = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if price_element:
            price_text = price_element.text.replace("₹", "").replace(",", "").strip()
            return title, int(price_text)
        return title, None
    except Exception as e:
        print("Flipkart Scraping Error:", e)
        return None, None

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Welcome to Harsh's Deal Hunter!\nAmazon ya Flipkart ka link bhej aur price drop track kar.\n\n🛠️ **Commands:**\n/list - Apni Wishlist dekh\n/delete - Item hatao")

@bot.message_handler(commands=['list'])
def show_list(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Teri Wishlist khali hai! Koi Amazon ya Flipkart link bhej.")
        return
    
    response = "📋 **Teri Wishlist & Tracking List:**\n\n"
    for index, item in enumerate(data[chat_id]):
        short_title = item['title'][:40] + "..." if len(item['title']) > 40 else item['title']
        platform_icon = "🛒" if item.get('platform') == "Flipkart" else "📦"
        response += f"*{index + 1}.* {platform_icon} {short_title}\n💰 Current Price: ₹{item['start_price']}\n\n"
    
    response += "🗑️ Kisi item ko hatane ke liye type kar: `/delete 1`"
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['delete'])
def delete_item(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Delete karne ke liye kuch hai hi nahi list mein!")
        return
    
    try:
        item_number = int(message.text.split()[1]) - 1
        if 0 <= item_number < len(data[chat_id]):
            deleted_item = data[chat_id].pop(item_number)
            save_data(data)
            bot.reply_to(message, f"🗑️ Done! Maine **{deleted_item['title'][:30]}...** ko list se hata diya hai.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Sahi number daal bhai.")
    except:
        bot.reply_to(message, "❌ Format galat hai. Aise type kar: `/delete 1`")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "amazon" in url.lower() or "amzn" in url.lower():
        bot.reply_to(message, "🔍 Ek second, Amazon par link check kar raha hoon...")
        title, current_price = check_amazon_price(url)
        platform = "Amazon"
    elif "flipkart" in url.lower() or "fkrt" in url.lower():
        bot.reply_to(message, "🔍 Ek second, Flipkart par link check kar raha hoon...")
        title, current_price = check_flipkart_price(url)
        platform = "Flipkart"
    else:
        bot.reply_to(message, "⚠️ Bhai, abhi sirf Amazon aur Flipkart ke links bhej.")
        return
        
    if current_price:
        data = load_data()
        chat_id = str(message.chat.id)
        if chat_id not in data:
            data[chat_id] = []
            
        data[chat_id].append({
            "url": url,
            "title": title, 
            "start_price": current_price,
            "platform": platform
        })
        save_data(data)
        
        icon = "🛒" if platform == "Flipkart" else "📦"
        bot.reply_to(message, f"✅ **{platform.upper()} TRACKING ON**\n{icon} {title[:50]}...\n💰 Price: ₹{current_price}\n\nPrice girte hi main udta hua notification launga! 🚀", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Bhai, price nahi mil raha. Ho sakta hai item Out of Stock ho ya Anti-Bot security tight ho. Dusra link try kar.")

# === BACKGROUND PRICE CHECKER ===
def auto_price_checker():
    while True:
        time.sleep(7200) 
        data = load_data()
        changes_made = False
        
        for chat_id, items in data.items():
            for item in items:
                try:
                    platform = item.get('platform', 'Amazon')
                    if platform == "Amazon":
                        title, new_price = check_amazon_price(item['url'])
                    elif platform == "Flipkart":
                        title, new_price = check_flipkart_price(item['url'])
                    else:
                        continue
                        
                    if new_price and new_price < item['start_price']:
                        icon = "🛒" if platform == "Flipkart" else "📦"
                        bot.send_message(
                            chat_id,
                            f"🚨🚨 {platform.upper()} MEGA DEAL ALERT! 🚨🚨\n{icon} {item['title'][:50]}...\n📉 Old Price: ₹{item['start_price']}\n🔥 NEW PRICE: ₹{new_price}\n🔗 Buy Now: {item['url']}"
                        )
                        item['start_price'] = new_price
                        changes_made = True
                except:
                    pass
                    
        if changes_made:
            save_data(data)

# === START ENGINE ===
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    checker_thread = threading.Thread(target=auto_price_checker)
    checker_thread.daemon = True
    checker_thread.start()
    
    print("🚀 Harsh's Bot is online and ready!")
    bot.infinity_polling()
