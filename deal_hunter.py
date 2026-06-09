import telebot
import requests
from bs4 import BeautifulSoup
import json
import os
import threading
import time
import random
from flask import Flask  # 🔥 NAYA HATHIYAAR: Server ko bewakoof banane ke liye

# --- TERA ASALI TOKEN ---
TOKEN = "7959029994:AAGFMHKyN4_DA4_DQi99xJfHd8NpsRq7PBM"
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "data.json"

# --- DUMMY WEBSITE ENGINE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Harsh ka Deal Hunter Bot 24/7 Zinda Hai!"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7'
}

def auto_price_checker():
    while True:
        print("🔄 [BACKGROUND] Checking prices...")
        data = load_data()
        for chat_id, items in data.items():
            for item in items:
                try:
                    response = requests.get(item['url'], headers=HEADERS)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    price_element = soup.find("span", class_="a-price-whole")
                    
                    if price_element:
                        current_price = float(price_element.text.replace(',', '').replace('.', '').strip())
                        if current_price < item['start_price']:
                            bot.send_message(
                                int(chat_id), 
                                f"🚨🚨 MEGA DEAL ALERT! 🚨🚨\n\n📦 {item['title']}...\n📉 Old Price: ₹{item['start_price']}\n🔥 NEW PRICE: ₹{current_price}\n\nLink: {item['url']}"
                            )
                            item['start_price'] = current_price
                            save_data(data)
                except Exception as e:
                    pass
        time.sleep(random.randint(3600, 7200)) 

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    chat_id = str(message.chat.id)
    
    if "amazon.in" in user_text or "amzn.in" in user_text or "amzn.to" in user_text:
        bot.reply_to(message, "⏳ Link mil gaya! Price save kar raha hoon...")
        try:
            response = requests.get(user_text, headers=HEADERS)
            soup = BeautifulSoup(response.content, 'html.parser')
            title_element = soup.find("span", id="productTitle")
            price_element = soup.find("span", class_="a-price-whole")
            
            if title_element and price_element:
                title = title_element.text.strip()
                clean_price = float(price_element.text.replace(',', '').replace('.', '').strip())
                
                data = load_data()
                if chat_id not in data:
                    data[chat_id] = []
                    
                data[chat_id].append({
                    "url": user_text,
                    "title": title[:30], 
                    "start_price": clean_price
                })
                save_data(data)
                bot.send_message(int(chat_id), f"✅ TRACKING ON!\n📦 {title[:30]}...\n💸 Current: ₹{clean_price}")
            else:
                bot.send_message(int(chat_id), "❌ Price nahi mila.")
        except Exception as e:
            bot.send_message(int(chat_id), f"❌ Error: {e}")
    else:
        bot.reply_to(message, "Sirf Amazon links bhej bhai! 🛒")

# --- ASALI MAIN ENGINE ---
if __name__ == "__main__":
    # Bot aur Background checker dono ko alag dimaag mein start karo
    threading.Thread(target=auto_price_checker, daemon=True).start()
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    # Dummy website ko main port par on kar do
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)