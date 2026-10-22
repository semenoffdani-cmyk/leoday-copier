import os
import json
import requests
import feedparser
import re
import uuid
import base64
import urllib3
import time
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
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# =====================================================================
# 🧹 ОЧИСТКА ТЕКСТА
# =====================================================================
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()

# =====================================================================
# 🤖 GIGACHAT: АВТОРИЗАЦИЯ
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

# =====================================================================
# ✍️ GIGACHAT: РЕРАЙТ ТЕКСТА
# =====================================================================
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
# 🎨 GIGACHAT: ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ (KANDINSKY)
# =====================================================================
def generate_image(prompt, token):
    if not token:
        return None
    try:
        # 1. Отправляем запрос на генерацию
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # Стилизуем промпт под наш канал (сине-золотые тона, минимализм)
        full_prompt = (
            f"Создай стильный минималистичный финансовый постер. "
            f"Тема: {prompt}. "
            f"Стиль: современный, деловой, сине-золотая цветовая гамма, графики, стрелки вверх/вниз, без текста."
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": full_prompt}],
            "function_call": "auto" # Включаем режим генерации картинок
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        result = response.json()
        
        # 2. Извлекаем ID файла из ответа
        if 'choices' not in result:
            return None
            
        content = result['choices'][0]['message']['content']
        # Ищем <img src="file_id" ... />
        match = re.search(r'<img src="([^"]+)"', content)
        if not match:
            print("Картинка не была сгенерирована в ответе.")
            return None
            
        file_id = match.group(1)
        
        # 3. Скачиваем изображение
        download_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
        img_response = requests.get(download_url, headers={'Authorization': f'Bearer {token}'}, verify=False, timeout=30)
        
        if img_response.status_code == 200:
            return img_response.content # Возвращаем бинарные данные картинки
        else:
            print(f"Ошибка скачивания картинки: {img_response.text}")
            return None
            
    except Exception as e:
        print(f"Ошибка генерации картинки: {e}")
        return None

# =====================================================================
# ✈️ TELEGRAM: ОТПРАВКА ФОТО С ТЕКСТОМ
# =====================================================================
def send_photo_to_telegram(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    payload = {
        "chat_id": CHAT_ID,
        "caption": text,
        "parse_mode": "HTML"
    }
    
    files = {
        "photo": ("poster.jpg", image_bytes, "image/jpeg")
    }
    
    try:
        response = requests.post(url, data=payload, files=files, timeout=20)
        if not response.ok:
            print(f"Ошибка Telegram (фото): {response.text}")
        return response.ok
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        return False

# =====================================================================
# ✈️ TELEGRAM: ОТПРАВКА ТЕКСТА (Резервный вариант)
# =====================================================================
def send_text_to_telegram(text):
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
            print(f"Ошибка Telegram (текст): {response.text}")
        return response.ok
    except Exception as e:
        print(f"Ошибка отправки текста: {e}")
        return False

# =====================================================================
# 📦 РАБОТА С ИСТОРИЕЙ
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

# =====================================================================
# 🚀 ОСНОВНАЯ ЛОГИКА
# =====================================================================
def main():
    history = load_history()
    token = get_gigachat_token()
    
    if not token:
        print("ВНИМАНИЕ: Токен GigaChat не получен. Тексты будут без рерайта и картинок.")
    
    new_posts_count = 0

    FINANCIAL_KEYWORDS = [
        'ставк', 'рубл', 'инфляц', 'цб', 'банк', 'акци', 'нефт', 'бюджет', 
        'налог', 'финанс', 'кредит', 'вклад', 'бирж', 'доллар', 'евро', 
        'рынок', 'экономик', 'компан', 'убыт', 'прибыл', 'тариф', 'цен'
    ]

    for feed_url in RSS_FEEDS:
        print(f"Проверка ленты: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:10]:
            news_id = entry.link
            
            if news_id in history:
                continue
                
            title = clean_text(entry.title)
            description = clean_text(getattr(entry, 'description', ''))
            
            text_to_check = f"{title}. {description}".lower()
            
            if len(text_to_check) < 20:
                continue

            # Фильтр по ключевым словам
            is_financial = any(keyword in text_to_check for keyword in FINANCIAL_KEYWORDS)
            if not is_financial:
                print(f"⏭️ Пропуск (не по теме): {title[:40]}...")
                continue

            print(f"Новая новость: {title[:50]}...")
            
            # 1. Рерайт текста
            final_text = rewrite_text(f"{title}. {description}", token)
            
            # 2. Генерация картинки (используем заголовок как основу для промпта)
            print("Генерация постера...")
            image_bytes = generate_image(title, token)
            
            # 3. Публикация
            success = False
            if image_bytes:
                # Если картинка сгенерирована — отправляем фото с подписью
                success = send_photo_to_telegram(final_text, image_bytes)
            else:
                # Если картинка не удалась — отправляем только текст
                print("Картинка не сгенерирована. Отправляем только текст.")
                success = send_text_to_telegram(final_text)
            
            if success:
                print("✅ Опубликовано!")
                history[news_id] = datetime.now().isoformat()
                save_history(history)
                new_posts_count += 1
                time.sleep(5) # Увеличили паузу, так как генерация картинок требует времени
            else:
                print("❌ Не удалось опубликовать.")
                
            if new_posts_count >= 3:
                print("Достигнут лимит постов на этот запуск.")
                return

if __name__ == '__main__':
    main()
