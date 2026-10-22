import os
import json
import requests
import feedparser
import re
import uuid
import base64
import urllib3
import time
import html
import urllib.parse
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 БЕЗОПАСНЫЕ НАСТРОЙКИ
# =====================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('TARGET_CHANNEL')
GIGA_CLIENT_ID = os.environ.get('GIGACHAT_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGACHAT_CLIENT_SECRET')

if not BOT_TOKEN or not CHAT_ID:
    print("КРИТИЧЕСКАЯ ОШИБКА: Не заданы BOT_TOKEN или TARGET_CHANNEL")
    exit(1)

HISTORY_FILE = 'history.json'

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# =====================================================================
# 🧹 УТИЛИТЫ
# =====================================================================
def clean_text(text):
    if not text:
        return ""
    # Удаляем все HTML-теги, чтобы они не сломали разметку Telegram
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = html.escape(text) # Экранируем символы < и >
    return text.strip()

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка чтения истории: {e}")
            return {}
    return {}

def save_history(history):
    try:
        if len(history) > 2000:
            keys_to_remove = list(history.keys())[:-2000]
            for k in keys_to_remove:
                del history[k]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")

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
        response = requests.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=False, timeout=30)
        
        if response.status_code == 200:
            try:
                return response.json().get('access_token')
            except ValueError:
                print(f"GigaChat вернул не JSON: {response.text[:100]}")
                return None
        return None
    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None

def rewrite_text(text, token):
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        prompt = (
            f"Ты — ведущий финансового канала 'QIVONZA | КАПИТАЛ'. Сделай из этой новости пост. "
            f"Отвечай строго на три вопроса (без звездочек, скобок и markdown):\n"
            f"1. Что произошло?\n2. Что это меняет для обычного человека?\n3. За чем следить дальше?\n\n"
            f"Текст новости:\n{text}"
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2, 
            "max_tokens": 600   
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=90)
        if response.status_code != 200:
            print(f"Ошибка API GigaChat: {response.status_code}")
            return text
            
        try:
            result = response.json()
        except ValueError:
            return text
            
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            # Очищаем от любых случайных тегов
            rewritten = re.sub(r'<[^>]+>', '', rewritten) 
            return rewritten
        return text
    except Exception as e:
        print(f"Исключение при рерайте: {e}")
        return text

# =====================================================================
# 🎨 КАРТИНКИ
# =====================================================================
def generate_image_gigachat(prompt, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Ты — художник. Используй text2image. Верни только <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": f"Финансовый постер без текста. Тема: {prompt}. Сине-золотые тона, графики."}
            ],
            "function_call": "auto"
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=90)
        if response.status_code != 200: return None
        
        try:
            result = response.json()
        except ValueError:
            return None
            
        if 'choices' in result:
            content = result['choices'][0]['message']['content']
            match = re.search(r'<img src="([^"]+)"', content)
            if match:
                file_id = match.group(1)
                dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
                img_res = requests.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=False, timeout=30)
                if img_res.status_code == 200:
                    return img_res.content
        return None
    except Exception:
        return None

def generate_image_fallback(prompt):
    """Резервный генератор. Добавлен User-Agent, чтобы сервер не блокировал запрос."""
    try:
        safe_prompt = urllib.parse.quote(f"financial minimalistic poster, {prompt}, blue and gold colors, no text")
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=40)
        if response.status_code == 200:
            return response.content
        return None
    except Exception:
        return None

# =====================================================================
# ✈️ TELEGRAM
# =====================================================================
def send_photo(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    if len(text) > 1000:
        try:
            requests.post(url, data={"chat_id": CHAT_ID}, files={"photo": ("poster.jpg", image_bytes, "image/jpeg")}, timeout=30)
            return send_text(text)
        except: return False

    payload = {"chat_id": CHAT_ID, "caption": text, "parse_mode": "HTML"}
    files = {"photo": ("poster.jpg", image_bytes, "image/jpeg")}
    try:
        res = requests.post(url, data=payload, files=files, timeout=30)
        if not res.ok:
            print(f"Ошибка Telegram (фото): {res.text[:100]}")
        return res.ok
    except: return False

def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        res = requests.post(url, json=payload, timeout=15)
        if not res.ok:
            print(f"Ошибка Telegram (текст): {res.text[:100]}")
        return res.ok
    except: return False

# =====================================================================
# 🚀 MAIN
# =====================================================================
def main():
    history = load_history()
    token = get_gigachat_token()
    
    new_posts_count = 0

    FINANCIAL_KEYWORDS = [
        'ставк', 'рубл', 'инфляц', 'цб ', 'банк', 'акци', 'нефт', 'бюджет', 
        'налог', 'финанс', 'кредит', 'вклад', 'бирж', 'доллар', 'евро', 
        'рынок', 'экономик', 'компан', 'убыт', 'прибыл', 'тариф', 'цен'
    ]

    for feed_url in RSS_FEEDS:
        print(f"Проверка: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Ошибка чтения RSS: {e}")
            continue
        
        for entry in feed.entries[:15]:
            try:
                news_id = entry.link
                if not news_id or news_id in history:
                    continue
                    
                title = clean_text(entry.title)
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if len(text_to_check) < 30:
                    continue

                if not any(keyword in text_to_check for keyword in FINANCIAL_KEYWORDS):
                    continue

                print(f"🔥 Новость: {title[:40]}...")
                
                final_text = rewrite_text(f"{title}. {description}", token)
                
                print("Генерация постера...")
                image_bytes = generate_image_gigachat(title, token)
                
                if not image_bytes:
                    print("GigaChat не смог. Резервный вариант...")
                    image_bytes = generate_image_fallback(title)
                
                success = False
                if image_bytes:
                    success = send_photo(final_text, image_bytes)
                else:
                    success = send_text(final_text)
                
                if success:
                    print("✅ Опубликовано!")
                    history[news_id] = datetime.now().isoformat()
                    save_history(history)
                    new_posts_count += 1
                    time.sleep(4)
            except Exception as e:
                print(f"Ошибка при обработке новости: {e}")
                continue
                
            if new_posts_count >= 3:
                print("Лимит постов выполнен.")
                return

if __name__ == '__main__':
    main()
