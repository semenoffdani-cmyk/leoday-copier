import os
import json
import requests
import feedparser
import re
import uuid
import base64
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 НАСТРОЙКИ (Читаются из GitHub Secrets)
# =====================================================================
BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['TARGET_CHANNEL']
GIGA_CLIENT_ID = os.environ.get('GIGACHAT_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGACHAT_CLIENT_SECRET')

HISTORY_FILE = 'history.json'

# =====================================================================
# 📡 ИСТОЧНИКИ (RSS ЛЕНТЫ)
# =====================================================================
RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',      # РБК
    'https://www.cbr.ru/rss/RssNews',                         # ЦБ РФ
    'https://ria.ru/export/rss2/archive/index.xml'            # РИА Новости
]

# =====================================================================
# 🧹 ОЧИСТКА ТЕКСТА
# =====================================================================
def clean_text(text):
    if not text:
        return ""
    # Удаляем HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\s+', ' ', text)
    # Удаляем ссылки
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()

# =====================================================================
# 🤖 GIGACHAT
# =====================================================================
def get_gigachat_token():
    if not GIGA_CLIENT_ID or not GIGA_CLIENT_SECRET:
        return None
    try:
        auth_str = f"{GIGA_CLIENT_ID.strip()}:{GIGA_CLIENT_SECRET.strip()}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {auth_b64}'
        }
        payload = 'scope=GIGACHAT_API_PERS'
        response = requests.post(url, headers=headers, data=payload, verify=False, timeout=30)
        
        if response.status_code == 200:
            return response.json().get('access_token')
        print(f"Ошибка токена: {response.text}")
        return None
    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None

def rewrite_text(text, token):
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        prompt = (
            f"Ты — ведущий финансового канала 'QIVONZA | КАПИТАЛ'. Твоя задача — сделать из этой новости пост. "
            f"Отвечай на три вопроса кратко (не более 800 знаков): "
            f"1. Что произошло? (суть новости). "
            f"2. Что это меняет для обычного человека? (как это влияет на кошелек, рубль, инфляцию, кредиты). "
            f"3. За чем следить дальше? (какие показатели). "
            f"Пиши простым языком, без markdown-разметки (звездочек).\n\nТекст новости:\n{text}"
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3, 
            "max_tokens": 700   
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        result = response.json()
        
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            return re.sub(r'[*_`#]', '', rewritten)
        return text
    except Exception as e:
        print(f"Ошибка рерайта: {e}")
        return text

# =====================================================================
# ✈️ ПУБЛИКАЦИЯ В TELEGRAM (Через Bot API)
# =====================================================================
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if not response.ok:
            print(f"Ошибка Telegram: {response.text}")
        return response.ok
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False

# =====================================================================
# 🚀 ОСНОВНАЯ ЛОГИКА
# =====================================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def main():
    history = load_history()
    token = get_gigachat_token()
    
    if not token:
        print("ВНИМАНИЕ: Токен GigaChat не получен. Тексты будут без рерайта.")
    
    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        print(f"Проверка ленты: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        # Берем последние 3 новости из каждой ленты
        for entry in feed.entries[:3]:
            # Создаем уникальный ID новости (ссылка + дата)
            news_id = entry.link
            
            if news_id in history:
                continue # Уже публиковали
                
            title = clean_text(entry.title)
            description = clean_text(getattr(entry, 'description', ''))
            full_text = f"{title}. {description}"
            
            if len(full_text) < 20:
                continue

            print(f"Новая новость: {title[:50]}...")
            
            # 1. Рерайт через GigaChat
            final_text = rewrite_text(full_text, token)
            
            # 2. Публикация
            if send_to_telegram(final_text):
                print("✅ Опубликовано!")
                history[news_id] = datetime.now().isoformat()
                save_history(history)
                new_posts_count += 1
                # Пауза между постами, чтобы не спамить
                import time
                time.sleep(3)
            else:
                print("❌ Не удалось опубликовать.")
                
            if new_posts_count >= 3:
                print("Достигнут лимит постов на этот запуск.")
                return

if __name__ == '__main__':
    main()
