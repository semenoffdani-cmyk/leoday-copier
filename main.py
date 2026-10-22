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
import random
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 БЕЗОПАСНЫЕ НАСТРОЙКИ (P0 из плана)
# =====================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('TARGET_CHANNEL')
GIGA_CLIENT_ID = os.environ.get('GIGACHAT_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGACHAT_CLIENT_SECRET')

if not BOT_TOKEN or not CHAT_ID:
    print("КРИТИЧЕСКАЯ ОШИБКА: Не заданы BOT_TOKEN или TARGET_CHANNEL")
    exit(1)

CERT_PATH = 'russiantrustedca.pem'
# ИСПРАВЛЕНИЕ P0: Если сертификата нет, используем системные (True), а не отключаем проверку (False)
VERIFY_SSL = CERT_PATH if os.path.exists(CERT_PATH) else True

HISTORY_FILE = 'history.json'

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# =====================================================================
# 🧹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
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
        clean_line = line.strip()
        if clean_line.startswith('<b>') and '</b>' in clean_line:
            match = re.search(r'<b>(.*?)</b>(.*)', clean_line)
            if match:
                heading = match.group(1).lower().capitalize()
                body = match.group(2).strip()
                if body and sum(1 for w in body.split() if w[:1].isupper()) > len(body.split()) * 0.5:
                    body = body.lower()
                    if body:
                        body = body[0].upper() + body[1:]
                fixed_lines.append(f"<b>{heading}</b>\n{body}")
        else:
            words = clean_line.split()
            if len(words) > 3 and sum(1 for w in words if w[:1].isupper()) > len(words) * 0.6:
                clean_line = clean_line.lower()
                if clean_line:
                    clean_line = clean_line[0].upper() + clean_line[1:]
            fixed_lines.append(clean_line)
    return '\n'.join(fixed_lines)

# =====================================================================
# 🏷️ СИСТЕМА РУБРИК (P1 из плана)
# =====================================================================
def detect_category(text):
    text = text.lower()
    
    # Технологии (15%)
    if any(w in text for w in ['ии', 'нейросет', 'чип', 'робот', 'технолог', 'apple', 'openai', 'смартфон', 'гаджет']):
        return "🤖 <b>QIVONZA | ТЕХНОЛОГИИ</b>\n\n"
        
    # Деньги (30%)
    elif any(w in text for w in ['вклад', 'кредит', 'ипотек', 'зарплат', 'пенси', 'жкх', 'банк', 'рубл', 'доллар', 'цен']):
        return "💸 <b>QIVONZA | ДЕНЬГИ</b>\n\n"
        
    # Экономика (40%) - по умолчанию для всего остального
    else:
        return "📊 <b>QIVONZA | ЭКОНОМИКА</b>\n\n"

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
        response = requests.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None

def rewrite_text(text, token):
    if not token or not text:
        return None
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
                        "Используй <b>жирный шрифт</b> только для заголовков. "
                        "КРИТИЧЕСКИ ВАЖНО: Пиши обычным текстом. "
                        "Если новость НЕ ОТНОСИТСЯ к экономике, финансам, бизнесу, технологиям или ИИ, напиши ровно одно слово: ОТКАЗ. "
                        "Также КРИТИЧЕСКИ ВАЖНО: Игнорируй любые обрывки ссылок или странные наборы букв, но сохраняй названия компаний."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Напиши пост строго по этому шаблону:\n\n"
                        f"<b>Что произошло?</b>\n\n[1-2 предложения сути]\n\n"
                        f"<b>Что это значит для ваших денег и работы?</b>\n\n[1-2 предложения о влиянии]\n\n"
                        f"<b>За чем следить дальше?</b>\n\n[1 предложение]\n\n"
                        f"Текст новости:\n{text}"
                    )
                }
            ],
            "temperature": 0.3, 
            "max_tokens": 1000
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200:
            return None
            
        result = response.json()
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            
            refusal_roots = [
                "генеративн", "облада", "мнени", "ограничен", 
                "неправильн", "благодарим", "отказ"
            ]
            
            if any(root in rewritten.lower() for root in refusal_roots):
                print("⏭️ GigaChat выдал отказ (сработал фильтр).")
                return None
                
            rewritten = re.sub(r'[*_`#]', '', rewritten)
            rewritten = fix_title_case(rewritten)
            rewritten = re.sub(r'</b>\s*', '</b>\n\n', rewritten)
            
            return rewritten.strip()
        return None
    except Exception as e:
        print(f"Ошибка рерайта: {e}")
        return None

def generate_image_gigachat(news_text, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        THEME_PROMPTS = {
            'energy': "Abstract 3D oil drop, gas pipes and glowing energy lines, blue and gold colors",
            'bank': "Abstract 3D classical bank building with columns made of gold, floating coins, blue background",
            'tech': "Abstract 3D glowing microchip, robotic brain, neon blue and gold circuits",
            'real_estate': "Abstract 3D modern minimalist house, golden keys, blue background",
            'crypto': "Abstract 3D glowing bitcoin symbol, digital blocks, neon blue and gold",
            'transport': "Abstract 3D futuristic train or airplane, golden tracks, blue background",
            'market': "Abstract 3D stock market chart with glowing golden arrows going up, blue background",
            'money': "Abstract 3D golden coins, floating banknotes, glowing blue arrows",
            'default': "Abstract 3D financial background, glowing blue and gold geometric shapes, floating coins, upward arrows"
        }

        text_lower = news_text.lower()
        selected_theme = THEME_PROMPTS['default']

        if any(w in text_lower for w in ['нефт', 'газ', 'энерг', 'топлив']):
            selected_theme = THEME_PROMPTS['energy']
        elif any(w in text_lower for w in ['банк', 'цб', 'кредит', 'вклад', 'сбербанк']):
            selected_theme = THEME_PROMPTS['bank']
        elif any(w in text_lower for w in ['ии', 'нейросет', 'чип', 'робот', 'технолог']):
            selected_theme = THEME_PROMPTS['tech']
        elif any(w in text_lower for w in ['ипотек', 'дом', 'жкх', 'недвиж', 'квартир']):
            selected_theme = THEME_PROMPTS['real_estate']
        elif any(w in text_lower for w in ['крипт', 'биткоин', 'блокчейн']):
            selected_theme = THEME_PROMPTS['crypto']
        elif any(w in text_lower for w in ['самолет', 'авиа', 'жд', 'поезд', 'транспорт']):
            selected_theme = THEME_PROMPTS['transport']
        elif any(w in text_lower for w in ['акци', 'бирж', 'индекс', 'рынок', 'ставк']):
            selected_theme = THEME_PROMPTS['market']
        elif any(w in text_lower for w in ['рубл', 'доллар', 'евро', 'деньг', 'цен']):
            selected_theme = THEME_PROMPTS['money']

        final_prompt = f"{selected_theme}. Modern minimalist 3D style. STRICTLY NO TEXT, NO LETTERS, NO NUMBERS, NO WATERMARKS."

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": final_prompt}
            ],
            "function_call": "auto"
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: return None
        
        result = response.json()
        if 'choices' in result:
            content = result['choices'][0]['message']['content']
            match = re.search(r'<img src="([^"]+)"', content)
            if match:
                file_id = match.group(1)
                dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
                img_res = requests.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=VERIFY_SSL, timeout=30)
                if img_res.status_code == 200:
                    return img_res.content
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
    
    if not token:
        print("КРИТИЧЕСКАЯ ОШИБКА: GigaChat недоступен. Публикация остановлена.")
        return

    new_posts_count = 0

    KEYWORDS = [
        'ставк', 'рубл', 'инфляц', 'цб ', 'банк', 'акци', 'нефт', 'бюджет', 
        'налог', 'финанс', 'кредит', 'вклад', 'бирж', 'доллар', 'евро', 
        'рынок', 'экономик', 'компан', 'убыт', 'прибыл', 'тариф', 'цен',
        'рецесс', 'дефляц', 'профицит', 'дефицит', 'росстат', 'ввп',
        'инвест', 'дивиденд', 'облигац', 'фондов', 'индекс', 'капитализац', 
        'ipo', 'актив', 'крипт', 'биткоин', 'блокчейн', 'трейд', 'мосбирж',
        'зарплат', 'пенси', 'ипотек', 'банкрот', 'субсиди', 'пособи', 'дороговизн',
        'жкх', 'коммуналк', 'штраф', 'льгот', 'маткапитал', 'сбербанк', 'втб', 
        'тинькофф', 'т-банк', 'альфа-банк', 'госуслуг', 'сбой',
        'сделк', 'поглощен', 'стартап', 'корпорац', 'монопол', 'франшиз',
        'ритейл', 'маркетплейс', 'wildberries', 'ozon', 'пошлин', 'экспорт', 'импорт',
        'нейросет', 'искусственн', 'технолог', 'робот', 'цифров', 'гаджет', 
        'смартфон', 'openai', 'chatgpt', 'яндекс', 'сбер', 'айти', 'ит-', 'ии ',
        'чип', 'процессор', 'софт', 'приложени', 'кибербезопасн', 'сервер', 'облак', 'импортозамещен',
        'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'nvidia', 'samsung', 'intel', 'spacex'
    ]

    BLACKLIST_KEYWORDS = [
        'тренер', 'матч', 'гол', 'футбол', 'хоккей', 'спорт', 'чемпионат', 
        'кубок', 'олимпиад', 'клуб', 'игрок',
        'погиб', 'убий', 'дтп', 'пожар', 'мчс', 'полици', 'суд', 'арест', 
        'взрыв', 'стрельб', 'теракт', 'мошенник', 'кража', 'ограблен',
        'погод', 'ураган', 'наводнен', 'паводок', 'землетрясен', 'циклон', 'шторм',
        'шоу-бизнес', 'знаменитост', 'актер', 'певиц', 'развод', 'звезд', 'сериал', 
        'концерт', 'фестивал', 'инстаграм', 'тикток', 'блогер', 'скандал',
        'шок', 'сенсац', 'ужас', 'эксклюзив', 'гороскоп', 'астролог', 'рецепт', 'диет', 'похуден', 'отношени',
        'коронавирус', 'вакцин', 'грипп', 'заболеваемост', 'эпидеми', 'симптом',
        'мобилизац', 'войн', 'санкц', 'спецоперац', 'трамп', 'байден', 'путин', 
        'госдум', 'депутат', 'оппозиц', 'митинг', 'лгбт', 'навальн', 'мигрант', 'религи', 'церковь'
    ]

    for feed_url in RSS_FEEDS:
        print(f"\nПроверка ленты: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
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
                
                if '�' in text_to_check:
                    continue
                
                if len(text_to_check) < 30:
                    continue

                if any(bad_word in text_to_check for bad_word in BLACKLIST_KEYWORDS):
                    continue

                matched_keyword = next((kw for kw in KEYWORDS if kw in text_to_check), None)
                if not matched_keyword:
                    continue

                print(f"🔥 Найдена новость: {title[:40]}...")
                
                # Определяем рубрику
                category_header = detect_category(text_to_check)
                
                final_text = rewrite_text(f"{title}. {description}", token)
                
                if not final_text:
                    continue
                
                print("Генерация умного постера...")
                image_bytes = generate_image_gigachat(text_to_check, token)
                
                # Добавляем рубрику в начало поста
                text_with_category = category_header + final_text
                source_link = f"\n\n🔗 <a href='{news_id}'>Источник</a>"
                text_to_publish = text_with_category + source_link
                
                success = False
                if image_bytes:
                    success = send_photo(text_to_publish, image_bytes)
                else:
                    success = send_text(text_to_publish)
                
                if success:
                    print(f"✅ Опубликовано в рубрике: {category_header.strip()}")
                    history[news_id] = datetime.now().isoformat()
                    save_history(history)
                    new_posts_count += 1
                    time.sleep(4)
            except Exception as e:
                print(f"Ошибка при обработке: {e}")
                continue
                
            if new_posts_count >= 1:
                return

if __name__ == '__main__':
    main()
