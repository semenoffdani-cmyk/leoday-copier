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

# Отключаем предупреждения на случай, если сертификат не подгрузится
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

# Проверяем наличие сертификата для безопасных запросов
CERT_PATH = 'russiantrustedca.pem'
VERIFY_SSL = CERT_PATH if os.path.exists(CERT_PATH) else False

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
# 🧹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    # Английские слова больше не удаляются, чтобы сохранять названия компаний
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
                        "Используй <b>жирный шрифт</b> только для трех заголовков. "
                        "КРИТИЧЕСКИ ВАЖНО: Пиши обычным текстом. "
                        "Если новость НЕ ОТНОСИТСЯ к экономике, финансам, бизнесу, технологиям или ИИ, напиши ровно одно слово: ОТКАЗ. "
                        "Также КРИТИЧЕСКИ ВАЖНО: Игнорируй любые обрывки ссылок или странные наборы букв, но сохраняй названия компаний (Apple, OpenAI, Сбер и т.д.)."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Напиши пост строго по этому шаблону:\n\n"
                        f"<b>Что произошло?</b>\n[1-2 предложения сути]\n\n"
                        f"<b>Что это меняет для обычного человека?</b>\n[1-2 предложения о влиянии на кошелек или работу]\n\n"
                        f"<b>За чем следить дальше?</b>\n[1 предложение о том, на какой показатель смотреть]\n\n"
                        f"Текст новости:\n{text}"
                    )
                }
            ],
            "temperature": 0.2, 
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
            return rewritten.strip()
        return None
    except Exception as e:
        return None

def generate_image_gigachat(token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        prompts = [
            "Abstract 3D financial background. Glowing blue and gold geometric shapes, floating coins, upward arrows. STRICTLY NO TEXT, NO LETTERS, NO NUMBERS.",
            "Modern minimalist 3D financial illustration. Dark blue background, gold glowing stock market lines, abstract crystals. STRICTLY NO TEXT, NO TYPOGRAPHY.",
            "Abstract 3D rendering of financial growth. Gold spheres, neon blue grids, futuristic architecture. STRICTLY NO TEXT, NO WATERMARKS."
        ]
        random_prompt = random.choice(prompts)
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": random_prompt}
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
    
    new_posts_count = 0

    # ✅ РАСШИРЕННЫЙ БЕЛЫЙ СПИСОК (Что мы хотим видеть)
    KEYWORDS = [
        # Экономика и финансы
        'ставк', 'рубл', 'инфляц', 'цб ', 'банк', 'акци', 'нефт', 'бюджет', 
        'налог', 'финанс', 'кредит', 'вклад', 'бирж', 'доллар', 'евро', 
        'рынок', 'экономик', 'компан', 'убыт', 'прибыл', 'тариф', 'цен',
        # Инвестиции
        'инвест', 'дивиденд', 'облигац', 'фондов', 'индекс', 'капитализац', 
        'ipo', 'актив', 'крипт', 'биткоин', 'блокчейн', 'трейд',
        # Личные деньги
        'зарплат', 'пенси', 'ипотек', 'банкрот', 'субсиди', 'пособи', 'дороговизн',
        # Бизнес
        'сделк', 'поглощен', 'стартап', 'корпорац', 'монопол', 'франшиз',
        # Технологии и ИИ
        'нейросет', 'искусственн', 'технолог', 'робот', 'цифров', 'гаджет', 
        'смартфон', 'openai', 'chatgpt', 'яндекс', 'сбер', 'айти', 'ит-', 'ии ',
        'чип', 'процессор', 'софт', 'приложени', 'кибербезопасн', 'сервер', 'облак',
        # Западные компании
        'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'nvidia', 'samsung', 'intel', 'spacex'
    ]

    # 🚫 РАСШИРЕННЫЙ ЧЕРНЫЙ СПИСОК (Что мы отсекаем)
    BLACKLIST_KEYWORDS = [
        # Спорт
        'тренер', 'матч', 'гол', 'футбол', 'хоккей', 'спорт', 'чемпионат', 
        'кубок', 'олимпиад', 'клуб', 'игрок',
        # Криминал и ЧП
        'погиб', 'убий', 'дтп', 'пожар', 'мчс', 'полици', 'суд', 'арест', 
        'взрыв', 'стрельб', 'теракт', 'мошенник', 'кража', 'ограблен',
        # Погода
        'погод', 'ураган', 'наводнен', 'паводок', 'землетрясен', 'циклон', 'шторм',
        # Шоу-бизнес
        'шоу-бизнес', 'знаменитост', 'актер', 'певиц', 'развод', 'звезд', 'сериал', 'концерт', 'фестивал',
        # Медицина
        'коронавирус', 'вакцин', 'грипп', 'заболеваемост', 'эпидеми', 'симптом',
        # Политика и чувствительные темы
        'мобилизац', 'войн', 'санкц', 'спецоперац', 'трамп', 'байден', 'путин', 
        'госдум', 'депутат', 'оппозиц', 'митинг'
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

                # 1. Отсекаем мусор (спорт, ЧП, шоу-бизнес)
                if any(bad_word in text_to_check for bad_word in BLACKLIST_KEYWORDS):
                    print(f"⏭️ Пропуск (черный список): {title[:40]}...")
                    continue

                # 2. Ищем только то, что нам нужно (финансы, IT, бизнес)
                matched_keyword = next((kw for kw in KEYWORDS if kw in text_to_check), None)
                if not matched_keyword:
                    continue

                print(f"🔥 Найдена новость: {title[:40]}...")
                
                final_text = rewrite_text(f"{title}. {description}", token)
                
                if not final_text:
                    print("⏭️ Пропуск: GigaChat не смог обработать текст.")
                    continue
                
                print("Генерация постера...")
                image_bytes = generate_image_gigachat(token)
                
                source_link = f"\n\n🔗 <a href='{news_id}'>Источник</a>"
                text_with_source = final_text + source_link
                
                success = False
                if image_bytes:
                    success = send_photo(text_with_source, image_bytes)
                else:
                    print("Картинка не сгенерирована. Отправляем только текст.")
                    success = send_text(text_with_source)
                
                if success:
                    print("✅ Опубликовано!")
                    history[news_id] = datetime.now().isoformat()
                    save_history(history)
                    new_posts_count += 1
                    time.sleep(4)
            except Exception as e:
                print(f"Ошибка при обработке: {e}")
                continue
                
            if new_posts_count >= 1:
                print("\nЛимит постов на этот запуск выполнен.")
                return

if __name__ == '__main__':
    main()
