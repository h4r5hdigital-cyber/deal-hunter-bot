import telebot
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import threading
from flask import Flask
from datetime import datetime, timedelta

# === TOKENS & SETUP ===
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# === FLASK SETUP (For 24/7 Uptime) ===
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

# === INDIA TIME HELPER ===
def get_ist_time():
    # Render server America mein hota hai, isliye +5:30 karke India ka time nikalenge
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# === AMAZON SCRAPER ENGINE (Direct Stealth Mask) ===
AMAZON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive"
}

def check_amazon_price(url):
    try:
        response = requests.get(url, headers=AMAZON_HEADERS, timeout=15)
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

# === FLIPKART SCRAPER ENGINE (Ultra-Smart Symbol Finder) ===
def check_flipkart_price(url):
    # 👇 APNI SCRAPER-API KEY YAHAN DAAL 👇
    API_KEY = "b96371ea776a13335d3c6fd192254409" 
    
    payload = {
        'api_key': API_KEY, 
        'url': url, 
        'country_code': 'in', 
        'render': 'true'
    }
    
    try:
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
        title = title_element.text.strip() if title_element else "Flipkart Product"
        
        if "Request Unsuccessful" in title or "Verify" in title:
            return "Blocked by Security", None

        price_element = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if price_element:
            price_text = price_element.text.replace("₹", "").replace(",", "").strip()
            return title, int(price_text)
            
        for tag in soup.find_all(['div', 'span']):
            text = tag.text.strip()
            if text.startswith('₹') and len(text) < 15:
                clean_text = text.replace('₹', '').replace(',', '').strip()
                if clean_text.isdigit(): 
                    return title, int(clean_text)
                    
        return title, None
    except Exception as e:
        print("Flipkart Scraping Error:", e)
        return None, None

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Welcome to Harsh's Deal Hunter!\nAmazon ya Flipkart ka link bhej aur price history track kar.\n\n🛠️ **Commands:**\n/list - Apni Wishlist dekh\n/history [no] - Price utaar-chadhaw dekho\n/delete [no] - Item hatao")

@bot.message_handler(commands=['list'])
def show_list(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Teri Wishlist khali hai! Koi Amazon ya Flipkart link bhej.")
        return
    
    response = "📋 **Teri Wishlist & Tracking List:**\n\n"
    for index, item in enumerate(data[chat_id]):
        short_title = item['title'][:35] + "..." if len(item['title']) > 35 else item['title']
        platform_icon = "🛒" if item.get('platform') == "Flipkart" else "📦"
        
        current_price = item['price_history'][-1]['price']
        start_price = item['start_price']
        
        response += f"*{index + 1}.* {platform_icon} {short_title}\n💰 Current: ₹{current_price} | Start: ₹{start_price}\n📈 History: `/history {index + 1}`\n\n"
    
    response += "🗑️ Kisi item ko hatane ke liye type kar: `/delete 1`"
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['history'])
def show_history(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 List khali hai bhai, history kahan se dikhau!")
        return
        
    try:
        item_number = int(message.text.split()[1]) - 1
        if 0 <= item_number < len(data[chat_id]):
            item = data[chat_id][item_number]
            
            response = f"📉 **PRICE HISTORY REPORT**\n"
            response += f"📦 **Product:** {item['title'][:50]}...\n"
            response += f"🌐 **Platform:** {item['platform']}\n"
            response += f"----------------------------------------\n\n"
            
            prices = [h['price'] for h in item['price_history']]
            lowest = min(prices)
            highest = max(prices)
            
            for h in item['price_history']:
                response += f"• `{h['date']}` → **₹{h['price']}**\n"
                
            response += f"\n----------------------------------------\n"
            response += f"🔥 **Lowest Ever:** ₹{lowest}\n"
            response += f"📈 **Highest Ever:** ₹{highest}\n"
            
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Sahi number daal bhai. Jaise: `/history 1`")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Aise use kar bhai: `/history 1` (List ka number daal)")

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
    elif "flipkart" in url.lower() or "fkrt" in url.lower() or "fktr" in url.lower() or "dl.flipkart" in url.lower():
        bot.reply_to(message, "🔍 Ek second, Flipkart par link check kar raha hoon (Isme 10-15 seconds lag sakte hain)...")
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
            
        current_time_str = get_ist_time().strftime("%d-%b %I:%M %p")
        
        data[chat_id].append({
            "url": url,
            "title": title, 
            "start_price": current_price,
            "platform": platform,
            "price_history": [{"date": current_time_str, "price": current_price}]
        })
        save_data(data)
        
        icon = "🛒" if platform == "Flipkart" else "📦"
        bot.reply_to(message, f"✅ **{platform.upper()} TRACKING ON**\n{icon} {title[:50]}...\n💰 Price: ₹{current_price}\n\nPrice ab automatic 6 AM, 12 PM, 6 PM aur 12 AM par check hoga! 🚀", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Bhai, price nahi mil raha. Ho sakta hai item Out of Stock ho ya link galat ho.")

# === SCHEDULED ROUTINE CHECKER (6AM, 12PM, 6PM, 12AM IST) ===
def auto_price_checker():
    checked_keys = set()
    while True:
        # India ka time nikalo
        ist_now = get_ist_time()
        current_hour = ist_now.hour
        current_minute = ist_now.minute
        
        # Target hours: 0 (12 AM), 6 (6 AM), 12 (12 PM), 18 (6 PM)
        # Hum pehle 5 minute ke andar check run karenge taaki exact time par hit ho
        if current_hour in [0, 6, 12, 18] and current_minute < 5:
            date_key = ist_now.strftime("%Y-%m-%d")
            check_key = f"{date_key}-{current_hour}"
            
            # Ensure ek routine sirf ek hi baar chale
            if check_key not in checked_keys:
                print(f"⏰ Routine Time! Running checks for {current_hour}:00 IST")
                
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
                                
                            if new_price:
                                last_recorded_price = item['price_history'][-1]['price']
                                
                                if new_price != last_recorded_price:
                                    current_time_str = get_ist_time().strftime("%d-%b %I:%M %p")
                                    item['price_history'].append({"date": current_time_str, "price": new_price})
                                    changes_made = True
                                
                                if new_price < last_recorded_price:
                                    icon = "🛒" if platform == "Flipkart" else "📦"
                                    bot.send_message(
                                        chat_id,
                                        f"🚨🚨 {platform.upper()} MEGA DEAL ALERT! 🚨🚨\n{icon} {item['title'][:50]}...\n📉 Old Price: ₹{last_recorded_price}\n🔥 NEW PRICE: ₹{new_price}\n📊 History: `/history`\n🔗 Buy Now: {item['url']}"
                                    )
                        except Exception as e:
                            print("Error in routine check:", e)
                            
                if changes_made:
                    save_data(data)
                    
                checked_keys.add(check_key)
        
        # CPU ko aaram dene ke liye har 1 minute baad ghadi dekhega
        time.sleep(60)

# === START ENGINE ===
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    checker_thread = threading.Thread(target=auto_price_checker)
    checker_thread.daemon = True
    checker_thread.start()
    
    print("🚀 Harsh's Routine Bot is online and ready!")
    bot.infinity_polling()
