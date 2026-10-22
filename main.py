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
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = html.escape(text)
    return text.strip()

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
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

def fix_title_case(text):
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        if line.startswith('<b>') and '</b>' in line:
            match = re.search(r'<b>(.*?)</b>(.*)', line)
            if match:
                heading = match.group(1).lower().capitalize()
                body = match.group(2).strip()
                if body and sum(1 for w in body.split() if w[:1].isupper()) > len(body.split()) * 0.5:
                    body = body.lower()
                    if body:
                        body = body[0].upper() + body[1:]
                fixed_lines.append(f"<b>{heading}</b>\n{body}")
        else:
            words = line.split()
            if len(words) > 3 and sum(1 for w in words if w[:1].isupper()) > len(words) * 0.6:
                line = line.lower()
                if line:
                    line = line[0].upper() + line[1:]
            fixed_lines.append(line)
    return '\n'.join(fixed_lines)

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
            return response.json().get('access_token')
        return None
    except Exception:
        return None

def rewrite_text(text, token):
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — профессиональный редактор финансового канала. "
                        "Твоя задача — написать пост строго по шаблону. "
                        "Используй <b>жирный шрифт</b> только для трех заголовков (в шаблоне они уже есть). "
                        "КРИТИЧЕСКИ ВАЖНО: Пиши обычным текстом. НЕ ПИШИ КАЖДОЕ СЛОВО С БОЛЬШОЙ БУКВЫ. "
                        "Только первая буква предложения должна быть заглавной. Никаких звездочек и маркдауна."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Напиши пост строго по этому шаблону (не отклоняйся от него):\n\n"
                        f"<b>Что произошло?</b>\n[1-2 предложения сути]\n\n"
                        f"<b>Что это меняет для обычного человека?</b>\n[1-2 предложения о влиянии на кошелек]\n\n"
                        f"<b>За чем следить дальше?</b>\n[1 предложение о том, на какой показатель смотреть]\n\n"
                        f"Текст новости:\n{text}"
                    )
                }
            ],
            "temperature": 0.2, 
            "max_tokens": 1000
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=90)
        if response.status_code != 200:
            return text
            
        result = response.json()
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            rewritten = re.sub(r'[*_`#]', '', rewritten)
            rewritten = fix_title_case(rewritten)
            
            if not re.search(r'[.!?]$', rewritten):
                rewritten += "..." 
                
            return rewritten.strip()
        return text
    except Exception as e:
        print(f"Ошибка рерайта: {e}")
        return text

# =====================================================================
# 🎨 ГЕНЕРАЦИЯ КАРТИНОК (БЕЗ ТЕКСТА)
# =====================================================================
def generate_image_gigachat(prompt, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": f"Abstract 3D financial illustration. Theme: {prompt}. Blue and gold colors, geometric shapes, glowing lines. STRICTLY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO WATERMARKS. Clean minimalist background."}
            ],
            "function_call": "auto"
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=90)
        if response.status_code != 200: return None
        
        result = response.json()
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
    try:
        safe_prompt = urllib.parse.quote(f"abstract 3d financial background, {prompt}, blue and gold, no text, no letters, no numbers, no typography, clean minimalist")
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
        headers = {'User-Agent': 'Mozilla/5.0'}
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
        return res.ok
    except: return False

def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        res = requests.post(url, json=payload, timeout=15)
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
        print(f"\nПроверка ленты: {feed_url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            resp = requests.get(feed_url, headers=headers, timeout=20)
            resp.encoding = 'utf-8' 
            feed = feedparser.parse(resp.content)
            
            print(f"Получено новостей из ленты: {len(feed.entries)}")
            if len(feed.entries) == 0:
                print("ВНИМАНИЕ: Лента пуста или не удалось её прочитать.")
        except Exception as e:
            print(f"Ошибка чтения RSS: {e}")
            continue
        
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                if not news_id or news_id in history:
                    continue
                    
                title = clean_text(entry.title)
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if len(text_to_check) < 30:
                    continue

                matched_keyword = next((kw for kw in FINANCIAL_KEYWORDS if kw in text_to_check), None)
                if not matched_keyword:
                    continue

                print(f"🔥 Найдена новость: {title[:40]}... (по слову '{matched_keyword}')")
                
                final_text = rewrite_text(f"{title}. {description}", token)
                
                print("Генерация постера...")
                image_bytes = generate_image_gigachat(title, token)
                
                if not image_bytes:
                    print("Резервный генератор...")
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
                print(f"Ошибка при обработке: {e}")
                continue
                
            if new_posts_count >= 3:
                print("\nЛимит постов на этот запуск выполнен.")
                return

if __name__ == '__main__':
    main()
