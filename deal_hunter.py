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

# === FLASK SETUP (FOR UPTIMEROBOT 24/7) ===
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

# === AMAZON SCRAPER FUNCTION ===
def check_amazon_price(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.find("span", id="productTitle")
        title = title_element.text.strip() if title_element else "Unknown Product"
        
        price_element = soup.find("span", class_="a-price-whole")
        if price_element:
            price_text = price_element.text.replace(",", "").replace(".", "").strip()
            return title, int(price_text)
        return title, None
    except Exception as e:
        print("Error scraping:", e)
        return None, None

# === BOT COMMANDS ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Welcome to Harsh's Deal Hunter!\nAmazon ka link bhej aur price drop track kar.\n\n🛠️ **Commands:**\n/list - Apni Wishlist dekh\n/delete - Item hatao")

@bot.message_handler(commands=['list'])
def show_list(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Teri Wishlist ekdum khali hai bhai! Koi Amazon link bhej.")
        return
    
    response = "📋 **Teri Wishlist & Tracking List:**\n\n"
    for index, item in enumerate(data[chat_id]):
        # Title lamba ho toh chota kar do
        short_title = item['title'][:40] + "..." if len(item['title']) > 40 else item['title']
        response += f"*{index + 1}.* {short_title}\n💰 Current Tracked Price: ₹{item['start_price']}\n\n"
    
    response += "🗑️ Kisi item ko hatane ke liye type kar: `/delete 1` (number badal dena)"
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
            bot.reply_to(message, f"🗑️ Done! Maine **{deleted_item['title'][:30]}...** ko teri wishlist se hata diya hai.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Sahi number daal bhai. Wishlist check karne ke liye /list type kar.")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Format galat hai. Aise type kar: `/delete 1`")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text
    if "amazon" not in url.lower():
        bot.reply_to(message, "⚠️ Bhai, abhi sirf Amazon ke links bhej.")
        return
        
    bot.reply_to(message, "🔍 Ek second, Amazon par link check kar raha hoon...")
    title, current_price = check_amazon_price(url)
    
    if current_price:
        data = load_data()
        chat_id = str(message.chat.id)
        if chat_id not in data:
            data[chat_id] = []
            
        data[chat_id].append({
            "url": url,
            "title": title, 
            "start_price": current_price
        })
        save_data(data)
        bot.reply_to(message, f"✅ **WISHLIST & TRACKING ON**\n📦 {title[:50]}...\n💰 Price: ₹{current_price}\n\nPrice girte hi main udta hua notification launga! 🚀", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Bhai, price nahi mil raha. Link check kar.")

# === BACKGROUND PRICE CHECKER ===
def auto_price_checker():
    while True:
        time.sleep(7200) # Har 2 ghante mein check karega (7200 seconds)
        data = load_data()
        changes_made = False
        
        for chat_id, items in data.items():
            for item in items:
                try:
                    title, new_price = check_amazon_price(item['url'])
                    if new_price and new_price < item['start_price']:
                        # BINGO! Price Drop
                        bot.send_message(
                            chat_id,
                            f"🚨🚨 MEGA DEAL ALERT! 🚨🚨\n📦 {item['title'][:50]}...\n📉 Old Price: ₹{item['start_price']}\n🔥 NEW PRICE: ₹{new_price}\n🔗 Buy Now: {item['url']}"
                        )
                        # Naya sasta price update kar do
                        item['start_price'] = new_price
                        changes_made = True
                except Exception as e:
                    print("Error in background check:", e)
                    
        if changes_made:
            save_data(data)

# === START ENGINE ===
if __name__ == "__main__":
    # 1. Start UptimeRobot Flask Server
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 2. Start Background Price Checker
    checker_thread = threading.Thread(target=auto_price_checker)
    checker_thread.daemon = True
    checker_thread.start()
    
    # 3. Start Telegram Bot
    print("🚀 Harsh's Bot is online and ready!")
    bot.infinity_polling()
