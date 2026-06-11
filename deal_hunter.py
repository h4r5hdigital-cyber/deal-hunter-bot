import telebot
import requests
from bs4 import BeautifulSoup
import json
import os
import time
import threading
from flask import Flask
from datetime import datetime, timedelta
import urllib.parse

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

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# === AMAZON SCRAPER ENGINE ===
AMAZON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

def check_amazon_price(url):
    try:
        response = requests.get(url, headers=AMAZON_HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.find("span", id="productTitle")
        title = title_element.text.strip() if title_element else "Amazon Product"
        
        price_element = soup.find("span", class_="a-price-whole")
        price = None
        if price_element:
            price_text = price_element.text.replace(",", "").replace(".", "").strip()
            price = int(price_text)
            
        offers = []
        keywords = ["Discount", "Card", "Cashback", "Bank Offer", "EMI"]
        for tag in soup.find_all(["span", "li", "div"]):
            txt = tag.text.strip()
            if any(kw in txt for kw in keywords):
                if "See All" in txt or "Learn more" in txt or txt == "Offers":
                    continue
                if 20 < len(txt) < 250:
                    clean_txt = " ".join(txt.split())
                    if clean_txt not in offers:
                        offers.append(clean_txt)
                        
        return title, price, offers[:5]
    except:
        return None, None, []

# === FLIPKART SCRAPER ENGINE ===
def check_flipkart_price(url):
    API_KEY = "b96371ea776a13335d3c6fd192254409" 
    payload = {'api_key': API_KEY, 'url': url, 'country_code': 'in', 'render': 'true'}
    
    try:
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=60)
        soup = BeautifulSoup(response.content, "html.parser")
        
        title_element = soup.find("span", class_="B_NuCI") or soup.find("span", class_="VU-Tbw")
        title = title_element.text.strip() if title_element else "Flipkart Product"
        
        if "Request Unsuccessful" in title or "Verify" in title:
            return "Blocked", None, []

        price = None
        price_element = soup.find("div", class_="_30jeq3 _16Jk6d") or soup.find("div", class_="Nx9bqj CxhGGd") or soup.find("div", class_="HLz_71")
        if price_element:
            price_text = price_element.text.replace("₹", "").replace(",", "").strip()
            price = int(price_text)
        else:
            for tag in soup.find_all(['div', 'span']):
                text = tag.text.strip()
                if text.startswith('₹') and len(text) < 15:
                    clean_text = text.replace('₹', '').replace(',', '').strip()
                    if clean_text.isdigit(): 
                        price = int(clean_text)
                        break
                        
        offers = []
        keywords = ["Bank Offer", "Cashback", "Special Price", "Partner Offer", "Discount"]
        for tag in soup.find_all(['li', 'span', 'div']):
            txt = tag.text.strip()
            if any(kw in txt for kw in keywords):
                if "T&C" in txt:
                    txt = txt.split("T&C")[0]
                if 15 < len(txt) < 250:
                    clean_txt = " ".join(txt.split()).strip()
                    if clean_txt not in offers:
                        offers.append(clean_txt)
                        
        return title, price, offers[:5]
    except:
        return None, None, []

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
            "scales": {
                "yAxes": [{"ticks": {"beginAtZero": False}}] 
            }
        }
    }
    encoded_config = urllib.parse.quote(json.dumps(chart_config))
    return f"https://quickchart.io/chart?c={encoded_config}&w=600&h=400&bkg=white"

# === BOT COMMANDS ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 Welcome to Harsh's Deal Hunter!\nAmazon ya Flipkart ka link bhej aur price drop/hike dono track kar.\n\n🛠️ **Commands:**\n/list - Apni Wishlist dekh\n/history [no] - Graph History dekho\n/delete [no] - Item hatao\n/reset - Sab kuch delete")

@bot.message_handler(commands=['reset'])
def reset_data(message):
    chat_id = str(message.chat.id)
    data = load_data()
    data[chat_id] = []
    save_data(data)
    bot.reply_to(message, "🔥 Database clear! Ab naye links bhej kar check kar.")

@bot.message_handler(commands=['list'])
def show_list(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 Teri Wishlist khali hai!")
        return
    
    response = "📋 **Teri Wishlist & Tracking List:**\n\n"
    for index, item in enumerate(data[chat_id]):
        short_title = item['title'][:35] + "..." if len(item['title']) > 35 else item['title']
        platform_icon = "🛒" if item.get('platform') == "Flipkart" else "📦"
        
        if 'price_history' in item and len(item['price_history']) > 0:
            current_price = item['price_history'][-1]['price']
        else:
            current_price = item['start_price']
            
        response += f"*{index + 1}.* {platform_icon} {short_title}\n💰 Current: ₹{current_price}\n📈 Graph History: `/history {index + 1}`\n\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['history'])
def show_history(message):
    chat_id = str(message.chat.id)
    data = load_data()
    
    if chat_id not in data or len(data[chat_id]) == 0:
        bot.reply_to(message, "📭 List khali hai bhai!")
        return
        
    try:
        item_number = int(message.text.split()[1]) - 1
        if 0 <= item_number < len(data[chat_id]):
            item = data[chat_id][item_number]
            
            if 'price_history' not in item or len(item['price_history']) == 0:
                bot.reply_to(message, "⚠️ Purana data hai. Delete karke naya add kar.")
                return
                
            chart_url = generate_chart_url(item['price_history'], item['title'])
                
            response = f"📉 **PRICE HISTORY REPORT**\n"
            response += f"📦 **Product:** {item['title'][:50]}...\n----------------------------------------\n"
            
            prices = [h['price'] for h in item['price_history']]
            response += f"🔥 **Lowest:** ₹{min(prices)} | 📈 **Highest:** ₹{max(prices)}\n"
            
            if 'latest_offers' in item and item['latest_offers']:
                response += f"\n💳 **Saved Offers:**\n"
                for off in item['latest_offers']:
                    response += f"└ {off}\n"
            
            bot.send_photo(chat_id, chart_url, caption=response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Sahi number daal bhai.")
    except:
        bot.reply_to(message, "❌ Aise use kar: `/history 1`")

@bot.message_handler(commands=['delete'])
def delete_item(message):
    chat_id = str(message.chat.id)
    data = load_data()
    try:
        item_number = int(message.text.split()[1]) - 1
        deleted_item = data[chat_id].pop(item_number)
        save_data(data)
        bot.reply_to(message, f"🗑️ Maine **{deleted_item['title'][:30]}...** ko hata diya.")
    except:
        bot.reply_to(message, "❌ Aise type kar: `/delete 1`")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if "amazon" in url.lower() or "amzn" in url.lower():
        bot.reply_to(message, "🔍 Amazon par price aur card offers check kar raha hoon...")
        title, current_price, offers = check_amazon_price(url)
        platform = "Amazon"
    elif "flipkart" in url.lower() or "fkrt" in url.lower() or "fktr" in url.lower() or "dl.flipkart" in url.lower():
        bot.reply_to(message, "🔍 Flipkart par price aur card offers check kar raha hoon...")
        title, current_price, offers = check_flipkart_price(url)
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
            "price_history": [{"date": current_time_str, "price": current_price}],
            "latest_offers": offers
        })
        save_data(data)
        
        icon = "🛒" if platform == "Flipkart" else "📦"
        response = f"✅ **{platform.upper()} TRACKING ON**\n{icon} {title[:50]}...\n💰 Price: ₹{current_price}\n\n"
        
        if offers:
            response += "💳 **LIVE BANK / CARD OFFERS:**\n"
            for off in offers:
                response += f"👉 {off}\n"
        else:
            response += "💳 *Abhi koi bada bank offer nahi dikha.*\n"
            
        response += "\n🚀 Price drop aur hike dono automatic routine par track honge!"
        bot.reply_to(message, response, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Bhai, data nahi mil raha. Link check kar le ek baar.")

# === SCHEDULED ROUTINE CHECKER WITH DROP & HIKE ALERTS ===
def auto_price_checker():
    checked_keys = set()
    while True:
        ist_now = get_ist_time()
        current_hour = ist_now.hour
        current_minute = ist_now.minute
        
        if current_hour in [0, 6, 12, 18] and current_minute < 5:
            check_key = f"{ist_now.strftime('%Y-%m-%d')}-{current_hour}"
            if check_key not in checked_keys:
                data = load_data()
                changes_made = False
                
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
                                
                            if new_price:
                                if 'price_history' not in item:
                                    item['price_history'] = [{"date": "Old Data", "price": item['start_price']}]
                                    
                                last_recorded_price = item['price_history'][-1]['price']
                                item['latest_offers'] = offers  
                                
                                # 1. GRAPH UPDATE LOGIC (Chaye badhe ya ghate, save hoga)
                                if new_price != last_recorded_price:
                                    current_time_str = get_ist_time().strftime("%d-%b %I:%M %p")
                                    item['price_history'].append({"date": current_time_str, "price": new_price})
                                    changes_made = True
                                
                                icon = "🛒" if platform == "Flipkart" else "📦"
                                
                                # 2. PRICE DROP NOTIFICATION
                                if new_price < last_recorded_price:
                                    bot.send_message(
                                        chat_id,
                                        f"🚨🚨 {platform.upper()} MEGA DEAL ALERT! 🚨🚨\n{icon} {item['title'][:40]}...\n💰 Old Price: ₹{last_recorded_price}\n🔥 NEW PRICE: ₹{new_price}\n📊 History: `/history`\n🔗 {item['url']}"
                                    )
                                    
                                # 3. NAYA FEATURE: PRICE HIKE NOTIFICATION (Price badhne par alert)
                                elif new_price > last_recorded_price:
                                    bot.send_message(
                                        chat_id,
                                        f"⚠️⚠️ {platform.upper()} PRICE HIKE ALERT! ⚠️⚠️\n{icon} {item['title'][:40]}...\n📈 Price badh gaya hai bhai!\n💰 Old Price: ₹{last_recorded_price}\n🔺 NEW PRICE: ₹{new_price}\n📊 History: `/history`\n🔗 {item['url']}"
                                    )
                        except:
                            pass
                if changes_made:
                    save_data(data)
                checked_keys.add(check_key)
        time.sleep(60)

# === START ENGINE ===
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_price_checker, daemon=True).start()
    bot.infinity_polling()
