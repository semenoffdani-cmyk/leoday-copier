import os
import sys

os.environ['PYTHONUNBUFFERED'] = '1'

import json
import re
import time
import html
import uuid
import base64
import math
import requests
import feedparser
import urllib3
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# ⚙️ НАСТРОЙКИ И КОНСТАНТЫ
# =====================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('TARGET_CHANNEL')
GIGA_CLIENT_ID = os.environ.get('GIGACHAT_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGACHAT_CLIENT_SECRET')

if not BOT_TOKEN or not CHAT_ID:
    print("КРИТИЧЕСКАЯ ОШИБКА: Не заданы BOT_TOKEN или TARGET_CHANNEL")
    sys.exit(1)

CERT_PATH = 'russiantrustedca.pem'
VERIFY_SSL = CERT_PATH if os.path.exists(CERT_PATH) else True
HISTORY_FILE = 'history.json'
EMBEDDINGS_FILE = 'embeddings.json'

SIMILARITY_THRESHOLD = 0.85
MAX_EMBEDDINGS_HISTORY = 50 

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# 🚫 УМЕРЕННЫЙ ЧЕРНЫЙ СПИСОК (ИСПРАВЛЕН)
BLACKLIST_REGEX = re.compile(
    r'тренер|матч|гол|футбол|хоккей|спорт|чемпионат|кубок|олимпиад|клуб|игрок|трусов|'
    r'теннис|бокс|ufc|mma|фигурное|биатлон|плавание|футболист|хоккеист|медаль|турнир|'
    r'погиб|убий|дтп|пожар|мчс|полици|суд|арест|взрыв|стрельб|теракт|мошенник|кража|ограблен|'
    r'наркотик|изнасилован|педофил|тюрьма|колония|приговор|прокурор|адвокат|утонул|госпитализирован|'
    r'плутоний|контрабанда|экстрадиция|отмывание|стрельба|школа|'
    r'погод|ураган|наводнен|паводок|землетрясен|циклон|шторм|гололед|снегопад|тайфун|цунами|'
    r'шоу-бизнес|знаменитост|актер|певиц|развод|звезд|сериал|концерт|фестивал|инстаграм|тикток|блогер|скандал|'
    r'свадьба|беременна|родила|пластика|ютуб|хайп|аукцион|топор|фильм|кубрик|памятник|музей|гражданство|'
    r'шок|сенсац|ужас|эксклюзив|гороскоп|астролог|рецепт|диет|похуден|отношени|коронавирус|'
    r'вакцин|грипп|заболеваемост|эпидеми|симптом|нерпа|тигр|фотоловушка|'
    r'мобилизац|войн|санкц|спецоперац|трамп|байден|путин|зеленский|госдум|депутат|оппозиц|митинг|'
    r'лгбт|навальн|мигрант|религи|церковь|бпла|дроны|атак|сбит|ракет|украин|дмитриев|воробьев|мид|'
    r'посол|нато|выборы|конгресс|сенат|парламент|уголовн|следствен|пострадав|жертв|эвакуац|обнал|'
    r'отмыван|коррупц|взятк|пентагон|госдеп|кремль|белый дом|губернатор|мэр|мэрия|минобороны|пво|'
    r'уничтожили|обстрел|'
    r'самокат|велосипед|парковк|тротуар|пешеход|прорыв трубы|коммунальная авария|'
    r'указание|положение|депонент|ломбардный|памятная монета', 
    re.IGNORECASE
)

# ✅ БЕЛЫЙ СПИСОК (ИСПРАВЛЕН)
KEYWORDS_REGEX = re.compile(
    r'ставк|рубл|инфляц|цб |банк|акци|нефт|бюджет|налог|финанс|кредит|вклад|бирж|доллар|'
    r'евро|рынок|экономик|компан|убыт|прибыл|тариф|цен|рецесс|дефляц|профицит|дефицит|'
    r'росстат|ввп|инвест|дивиденд|облигац|фондов|индекс|капитализац|ipo|актив|крипт|'
    r'биткоин|блокчейн|трейд|мосбирж|зарплат|пенси|ипотек|банкрот|субсиди|пособи|'
    r'дороговизн|жкх|коммуналк|штраф|льгот|маткапитал|сбербанк|втб|тинькофф|т-банк|'
    r'альфа-банк|госуслуг|сбой|сделк|поглощен|стартап|корпорац|монопол|франшиз|ритейл|'
    r'маркетплейс|wildberries|ozon|пошлин|экспорт|импорт|нейросет|искусственн|технолог|'
    r'робот|цифров|гаджет|смартфон|openai|chatgpt|яндекс|сбер|айти|ит-|ии |чип|процессор|'
    r'софт|приложени|кибербезопасн|сервер|облак|импортозамещен|apple|tesla|microsoft|'
    r'google|amazon|meta|nvidia|samsung|intel|spacex|энергет|дизел|топлив|баррел|девальвац|'
    r'ревальвац|хеджирован|фьючерс|опцион|трейдер|тайдан|правительств|кабинет|министр|ведомств|'
    r'промышленн|завод|производств|фабрик|сельхоз|агро|урожай|туризм|отел|экологи|esg|'
    r'фарм|медицин|труд|безработ|персонал|кадр|миграц|логистик|транспорт|стройк|недвижим|'
    r'лицензи|капитал|норматив|резерв|баланс|отчетност|санаци|ликвидац|господдержк|поправк', re.IGNORECASE
)

SESSION = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
SESSION.mount('https://', HTTPAdapter(max_retries=retries))

# =====================================================================
# 🧹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def remove_garbage(text):
    known_brands = {'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'nvidia', 'samsung', 'intel', 'spacex', 'openai', 'chatgpt'}
    def replace_word(match):
        word = match.group(0)
        if word.lower() in known_brands: return word
        return ''
    text = re.sub(r'\b[a-zA-Z]{4,}\b', replace_word, text)
    text = re.sub(r'(?i)amburg\w*', '', text)
    return text

def fix_caps(text):
    if text.isupper():
        text = re.sub(r'\b(РФ|США|ЦБ|ВВП|ЕС|ОПЕК|НАТО|СССР|СНГ|МВФ)\b', lambda m: m.group(0), text)
        text = text.capitalize()
        text = re.sub(r'\.\s*([а-яa-z])', lambda m: '. ' + m.group(1).upper(), text)
    return text

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = remove_garbage(text) 
    text = fix_caps(text) 
    return html.escape(text).strip()

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return {}
    return {}

def save_json(data, filepath):
    try:
        if filepath == HISTORY_FILE and len(data) > 2000: 
            data = dict(list(data.items())[-2000:])
        with open(filepath, 'w', encoding='utf-8') as f: 
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: 
        print(f"Ошибка сохранения {filepath}: {e}")

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
                    if body: body = body[0].upper() + body[1:]
                fixed_lines.append(f"<b>{heading}</b>\n{body}")
        else:
            words = clean_line.split()
            if len(words) > 3 and sum(1 for w in words if w[:1].isupper()) > len(words) * 0.6:
                clean_line = clean_line.lower()
                if clean_line: clean_line = clean_line[0].upper() + clean_line[1:]
            fixed_lines.append(clean_line)
    return '\n'.join(fixed_lines)

# =====================================================================
# 🏷️ УМНАЯ СИСТЕМА РУБРИК
# =====================================================================
def detect_category(text):
    if re.search(r'промышленн|завод|станкостроен|производств|фабрик|сельхоз|агро|туризм|отел|ритейл|маркетплейс|бизнес|компан|предпринимат', text, re.IGNORECASE):
        return "🏭 <b>БИЗНЕС И ПРОМЫШЛЕННОСТЬ</b>\n\n"
    elif re.search(r'нефт|газ|энергет|топлив|дизел|бензин|баррел|уголь|опек', text, re.IGNORECASE):
        return "🛢️ <b>ЭНЕРГЕТИКА И СЫРЬЕ</b>\n\n"
    elif re.search(r'вклад|кредит|ипотек|зарплат|пенси|жкх|рубл|доллар|евро|сбербанк|втб|тинькофф|банк|страхов|маткапитал', text, re.IGNORECASE):
        return "💸 <b>ЛИЧНЫЕ ДЕНЬГИ</b>\n\n"
    elif re.search(r'нейросет|искусственн|чип|робот|технолог|apple|openai|смартфон|гаджет|ит-|айти|кибербезопасн|\bии\b|софт|приложени', text, re.IGNORECASE):
        return "🤖 <b>ТЕХНОЛОГИИ И ИИ</b>\n\n"
    return "📊 <b>ЭКОНОМИКА</b>\n\n"

# =====================================================================
# 🤖 GIGACHAT: АВТОРИЗАЦИЯ И ВЕКТОРЫ
# =====================================================================
def get_gigachat_token():
    if not GIGA_CLIENT_ID or not GIGA_CLIENT_SECRET: 
        print("DEBUG: GIGACHAT_CLIENT_ID или SECRET не заданы!")
        return None
    try:
        auth_str = f"{GIGA_CLIENT_ID.strip()}:{GIGA_CLIENT_SECRET.strip()}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json', 'RqUID': str(uuid.uuid4()), 'Authorization': f'Basic {auth_b64}'}
        response = SESSION.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        
        if response.status_code == 200:
            print("DEBUG: Токен GigaChat получен.")
            return response.json().get('access_token')
        else:
            print(f"DEBUG: Ошибка GigaChat API: {response.status_code} {response.text}")
            return None
    except Exception as e: 
        print(f"DEBUG: Исключение при получении токена GigaChat: {e}")
        return None

def get_embedding(text, token):
    if not token or not text: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {"model": "Embeddings", "input": [text]}
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=30)
        if response.status_code == 200:
            return response.json()['data'][0]['embedding']
        return None
    except Exception: return None

def cosine_similarity(vec1, vec2):
    if not vec1 or not vec2: return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0: return 0.0
    return dot_product / (norm1 * norm2)

# =====================================================================
# 🤖 GIGACHAT: РЕРАЙТ ТЕКСТА
# =====================================================================
def rewrite_text(text, token):
    if not token or not text: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": (
                    "Ты — профессиональный редактор финансового канала. Пиши строго по шаблону. "
                    "КРИТИЧЕСКИ ВАЖНО: Проверяй падежи и согласование слов! "
                    "Помни: 'Банк России' — это мужской род. Правильно: 'Банк России назначил', а НЕ 'Банка России назначила'. "
                    "КРИТИЧЕСКИ ВАЖНО: Слова 'ставка', 'курс', 'санкции', 'валютный контроль' в экономическом контексте НЕ являются политикой. Анализируй их только с точки зрения влияния на финансы. "
                    "Если новость НЕ ОТНОСИТСЯ к экономике, финансам, бизнесу или технологиям, напиши ровно одно слово: ОТКАЗ."
                )},
                {"role": "user", "content": (
                    f"Напиши пост строго по этому шаблону (не добавляй ничего лишнего):\n\n"
                    f"[1-2 предложения СУТИ новости. Обязательно начни с заглавной буквы. НЕ пиши просто 'Банк России'. Не пиши капсом.]\n\n"
                    f"<b>Что это значит?</b>\n\n[1-2 предложения о влиянии на кошелек или работу]\n\n"
                    f"<b>Что дальше?</b>\n\n[1 предложение о том, на какой показатель смотреть]\n\n"
                    f"Текст новости:\n{text}"
                )}
            ],
            "temperature": 0.3, "max_tokens": 1000
        }
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: 
            print(f"DEBUG: Ошибка рерайта GigaChat: {response.status_code}")
            return None
        rewritten = response.json()['choices'][0]['message']['content'].strip()
        
        if any(root in rewritten.lower() for root in ["генеративн", "облада", "мнени", "ограничен", "неправильн", "благодарим", "отказ"]): 
            print("DEBUG: GigaChat выдал ОТКАЗ.")
            return None
        if len(rewritten) < 50: 
            print("DEBUG: GigaChat выдал слишком короткий текст.")
            return None
        
        rewritten = re.sub(r'[*_`#]', '', rewritten)
        rewritten = fix_title_case(rewritten)
        
        rewritten = re.sub(r'(?i)банк россии не имеет отношения к данной информации\.?\s*', '', rewritten)
        rewritten = re.sub(r'(?i)amburg\w*', '', rewritten)
        rewritten = re.sub(r'(?i)domclick', '', rewritten)
        
        if re.match(r'^[А-ЯA-Z]', rewritten) and re.match(r'^[А-ЯA-Z]+\s', rewritten):
            first_word = rewritten.split()[0]
            if first_word.endswith(('Л', 'ЛА', 'ЛО', 'ЛИ', 'ЕТ', 'ИТ', 'УТ', 'ЮТ')):
                rewritten = "Банк России " + rewritten

        rewritten = re.sub(r'(?i)банк россии', 'Банк России', rewritten)
        
        rewritten = re.sub(r'(?i)что это значит\?', '<b>Что это значит?</b>', rewritten)
        rewritten = re.sub(r'(?i)что дальше\?', '<b>Что дальше?</b>', rewritten)
        
        rewritten = re.sub(r'\s*<b>', '\n\n<b>', rewritten)
        rewritten = re.sub(r'</b>\s*', '</b>\n\n', rewritten)
        
        return rewritten.strip()
    except Exception as e: 
        print(f"DEBUG: Исключение при рерайте: {e}")
        return None

# =====================================================================
# 🎨 GIGACHAT: ГЕНЕРАЦИЯ КАРТИНОК
# =====================================================================
def generate_image_gigachat(news_text, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        base_style = "Cinematic lighting, Octane render, 8k resolution, minimalist corporate style, deep navy blue and metallic gold colors, highly detailed, no text."
        theme = f"Abstract 3D financial background, floating golden geometric shapes and glowing blue lines, {base_style}"
        
        if re.search(r'промышленн|завод|станкостроен|производств|фабрик|станок', news_text, re.IGNORECASE): 
            theme = f"Isometric 3D render of a futuristic factory with glowing golden gears and robotic arms, dark blue industrial background, {base_style}"
        elif re.search(r'нефт|газ|энергет|топлив|дизел|бензин|баррел|уголь|опек', news_text, re.IGNORECASE): 
            theme = f"Macro 3D shot of a golden oil drop suspended in mid-air, surrounded by sleek glass pipelines and glowing blue energy, {base_style}"
        elif re.search(r'сельхоз|агро|урожай|ферм|зерно', news_text, re.IGNORECASE): 
            theme = f"Abstract 3D render of golden wheat ears intertwined with glowing blue tech lines, minimalist agriculture concept, {base_style}"
        elif re.search(r'туризм|отел|курорт|путешеств', news_text, re.IGNORECASE): 
            theme = f"Sleek 3D model of a golden airplane and a glowing globe, floating above a dark blue background, travel concept, {base_style}"
        elif re.search(r'экологи|esg|зелен|выброс|углерод', news_text, re.IGNORECASE): 
            theme = f"Futuristic 3D green leaf made of glowing glass and gold, representing ESG and eco-friendly energy, {base_style}"
        elif re.search(r'фарм|медицин|лекарств|клиник', news_text, re.IGNORECASE): 
            theme = f"Premium 3D render of a medical cross and DNA molecule made of gold and blue glass, pharma concept, {base_style}"
        elif re.search(r'труд|безработ|персонал|кадр|миграц', news_text, re.IGNORECASE): 
            theme = f"3D illustration of abstract golden human silhouettes looking at a glowing blue career growth chart, {base_style}"
        elif re.search(r'правительств|министр|кабинет|госдум|заседани|совещани', news_text, re.IGNORECASE): 
            theme = f"Architectural 3D render of a minimalist government building with tall golden columns and glass walls, dramatic blue lighting, {base_style}"
        elif re.search(r'банк|цб|кредит|вклад|сбербанк|втб|тинькофф|регулятор', news_text, re.IGNORECASE): 
            theme = f"3D render of a modern bank vault door slightly open, glowing golden coins floating out, dark blue background, {base_style}"
        elif re.search(r'самолет|авиа|жд|поезд|транспорт|логистик', news_text, re.IGNORECASE): 
            theme = f"High-tech 3D render of a futuristic maglev train moving through a glowing blue tunnel with golden tracks, {base_style}"
        elif re.search(r'ипотек|дом|жкх|недвиж|квартир|стройк', news_text, re.IGNORECASE): 
            theme = f"Modern 3D architectural render of a luxury minimalist house made of glass and gold accents, floating in a dark blue space, {base_style}"
        elif re.search(r'крипт|биткоин|блокчейн|токен', news_text, re.IGNORECASE): 
            theme = f"Glossy 3D render of a floating golden Bitcoin symbol surrounded by glowing blue digital blocks, {base_style}"
        elif re.search(r'нейросет|чип|робот|технолог|apple|openai|айти', news_text, re.IGNORECASE): 
            theme = f"Macro 3D shot of a glowing golden microchip on a dark blue circuit board with neon light pulses, {base_style}"
        elif re.search(r'акци|бирж|индекс|рынок|ставк|трейд', news_text, re.IGNORECASE): 
            theme = f"Minimalist 3D holographic stock market chart with glowing golden arrows pointing upward, dark blue background, {base_style}"
        elif re.search(r'рубл|доллар|евро|деньг|цен|валют', news_text, re.IGNORECASE): 
            theme = f"Macro 3D render of stacked golden coins and floating glowing blue banknotes, {base_style}"
        elif re.search(r'ритейл|маркетплейс|wildberries|ozon|магазин', news_text, re.IGNORECASE): 
            theme = f"Stylish 3D render of a modern shopping cart made of gold and glass, floating blue boxes, {base_style}"

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a professional 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": f"{theme} STRICTLY NO TEXT, NO LETTERS, NO NUMBERS, NO LOGOS."}
            ],
            "function_call": "auto"
        }
        
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: 
            print(f"DEBUG: Ошибка генерации картинки: {response.status_code}")
            return None
        content = response.json()['choices'][0]['message']['content']
        match = re.search(r'<img src="([^"]+)"', content)
        if match:
            dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{match.group(1)}/content"
            img_res = SESSION.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=VERIFY_SSL, timeout=30)
            if img_res.status_code == 200:
                return img_res.content
            else:
                print(f"DEBUG: Ошибка скачивания картинки: {img_res.status_code}")
        else:
            print("DEBUG: GigaChat не вернул ссылку на картинку.")
        return None
    except Exception as e: 
        print(f"DEBUG: Исключение при генерации картинки: {e}")
        return None

# =====================================================================
# ✈️ TELEGRAM
# =====================================================================
def send_photo(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if len(text) > 1000: text = text[:1000] + "..."
    try:
        res = SESSION.post(url, data={"chat_id": CHAT_ID, "caption": text, "parse_mode": "HTML"}, files={"photo": ("poster.jpg", image_bytes, "image/jpeg")}, timeout=30)
        if not res.ok:
            print(f"DEBUG: Ошибка Telegram (фото): {res.text}")
        return res.ok
    except Exception as e: 
        print(f"DEBUG: Исключение Telegram (фото): {e}")
        return False

def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = SESSION.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=15)
        if not res.ok:
            print(f"DEBUG: Ошибка Telegram (текст): {res.text}")
        return res.ok
    except Exception as e: 
        print(f"DEBUG: Исключение Telegram (текст): {e}")
        return False

# =====================================================================
# 🚀 MAIN
# =====================================================================
def main():
    print("DEBUG: Скрипт запущен.")
    
    history = load_json(HISTORY_FILE)
    embeddings_history = load_json(EMBEDDINGS_FILE)
    
    token = get_gigachat_token()
    if not token: 
        print("DEBUG: Работа остановлена, так как нет токена GigaChat.")
        return
    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        print(f"DEBUG: Читаем ленту {feed_url}")
        try: feed = feedparser.parse(feed_url)
        except Exception as e: 
            print(f"DEBUG: Ошибка чтения RSS: {e}")
            continue
        
        print(f"DEBUG: Получено {len(feed.entries)} новостей.")
        
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                title = clean_text(entry.title)
                
                print(f"DEBUG: Проверяю новость: {title[:50]}...")

                if not news_id or news_id in history: 
                    continue
                    
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if '�' in text_to_check or len(text_to_check) < 30: 
                    continue
                
                match = BLACKLIST_REGEX.search(text_to_check)
                if match: 
                    print(f"DEBUG: ⏭️ Пропуск (черный список: '{match.group(0)}'): {title[:30]}")
                    continue
                
                if not KEYWORDS_REGEX.search(text_to_check): 
                    print(f"DEBUG: ⏭️ Пропуск (нет ключевых слов): {title[:30]}")
                    continue

                print(f"🔥 Новость прошла фильтры: {title[:40]}...")
                
                news_embedding = get_embedding(title, token)
                if news_embedding:
                    is_duplicate = False
                    for old_url, old_emb in embeddings_history.items():
                        similarity = cosine_similarity(news_embedding, old_emb)
                        if similarity > SIMILARITY_THRESHOLD:
                            print(f"DEBUG: ⏭️ Пропуск (семантический дубль). Сходство: {similarity:.2f}")
                            is_duplicate = True
                            break
                    if is_duplicate: continue

                original_percents = set(re.findall(r'(\d+(?:[.,]\d+)?)\s*%', text_to_check))

                category_header = detect_category(text_to_check)
                final_text = rewrite_text(f"{title}. {description}", token)
                if not final_text: 
                    print("DEBUG: ⏭️ Пропуск (GigaChat не смог переписать).")
                    continue
                
                if original_percents:
                    rewritten_lower = final_text.lower()
                    for p in original_percents:
                        p_variants = [p, p.replace(',', '.'), p.replace('.', ',')]
                        if not any(variant in rewritten_lower for variant in p_variants):
                            print(f"DEBUG: ⏭️ Пропуск (фактчекинг): число {p}% не найдено.")
                            final_text = None
                            break
                
                if not final_text: continue

                image_bytes = generate_image_gigachat(text_to_check, token)
                text_to_publish = category_header + final_text + f"\n\n🔗 <a href='{news_id}'>Источник</a>"
                
                success = send_photo(text_to_publish, image_bytes) if image_bytes else send_text(text_to_publish)
                
                if success:
                    print("DEBUG: ✅ Опубликовано!")
                    history[news_id] = datetime.now().isoformat()
                    save_json(history, HISTORY_FILE)
                    
                    if news_embedding:
                        embeddings_history[news_id] = news_embedding
                        if len(embeddings_history) > MAX_EMBEDDINGS_HISTORY:
                            oldest_key = next(iter(embeddings_history))
                            del embeddings_history[oldest_key]
                        save_json(embeddings_history, EMBEDDINGS_FILE)

                    new_posts_count += 1
                    time.sleep(4)
            except Exception as e:
                print(f"DEBUG: Ошибка при обработке: {e}")
                continue
            if new_posts_count >= 1: return

if __name__ == '__main__':
    main()
