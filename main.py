import os
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
    exit(1)

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

# 🚫 ЧЕРНЫЙ СПИСОК
BLACKLIST_REGEX = re.compile(
    r'тренер|матч|гол|футбол|хоккей|спорт|чемпионат|кубок|олимпиад|клуб|игрок|трусов|'
    r'погиб|убий|дтп|пожар|мчс|полици|суд|арест|взрыв|стрельб|теракт|мошенник|кража|ограблен|'
    r'погод|ураган|наводнен|паводок|землетрясен|циклон|шторм|шоу-бизнес|знаменитост|'
    r'актер|певиц|развод|звезд|сериал|концерт|фестивал|инстаграм|тикток|блогер|скандал|'
    r'шок|сенсац|ужас|эксклюзив|гороскоп|астролог|рецепт|диет|похуден|отношени|коронавирус|'
    r'вакцин|грипп|заболеваемост|эпидеми|симптом|мобилизац|войн|санкц|спецоперац|'
    r'трамп|байден|путин|госдум|депутат|оппозиц|митинг|лгбт|навальн|мигрант|религи|'
    r'церковь|бпла|атак|сбит|ракет|украин|дмитриев|воробьев|мид|нато|выборы|конгресс|'
    r'сенат|парламент|уголовн|следствен|пострадав|жертв|эвакуац|обнал|отмыван|коррупц|взятк', re.IGNORECASE
)

# ✅ БЕЛЫЙ СПИСОК
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
    r'фарм|медицин|труд|безработ|персонал|кадр|миграц|логистик|транспорт|стройк|недвижим', re.IGNORECASE
)

SESSION = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
SESSION.mount('https://', HTTPAdapter(max_retries=retries))

# =====================================================================
# 🧹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def remove_garbage(text):
    """Удаляет случайные английские обрывки (типа 'amburg'), но оставляет известные бренды."""
    known_brands = {'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'nvidia', 'samsung', 'intel', 'spacex', 'openai', 'chatgpt'}
    
    def replace_word(match):
        word = match.group(0)
        if word.lower() in known_brands:
            return word
        return ''
    
    # Ищем английские слова длиной от 4 букв и заменяем их
    return re.sub(r'\b[a-zA-Z]{4,}\b', replace_word, text)

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = remove_garbage(text) # Применяем умную очистку
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
    # Приоритет: Бизнес/Промышленность > Энергетика > Личные деньги > Технологии > Экономика
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
# 🤖 GIGACHAT: АВТОРИЗАЦИЯ, ВЕКТОРЫ И ГЕНЕРАЦИЯ
# =====================================================================
def get_gigachat_token():
    if not GIGA_CLIENT_ID or not GIGA_CLIENT_SECRET: return None
    try:
        auth_str = f"{GIGA_CLIENT_ID.strip()}:{GIGA_CLIENT_SECRET.strip()}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json', 'RqUID': str(uuid.uuid4()), 'Authorization': f'Basic {auth_b64}'}
        response = SESSION.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        return response.json().get('access_token') if response.status_code == 200 else None
    except Exception: return None

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
                    "Если новость НЕ ОТНОСИТСЯ к экономике, финансам, бизнесу или технологиям, напиши ровно одно слово: ОТКАЗ."
                )},
                {"role": "user", "content": (
                    f"Напиши пост строго по шаблону:\n\n"
                    f"<b>Что произошло?</b>\n\n[1-2 предложения сути. Следи за падежами!]\n\n"
                    f"<b>Что это значит для ваших денег и работы?</b>\n\n[1-2 предложения о влиянии]\n\n"
                    f"<b>За чем следить дальше?</b>\n\n[1 предложение]\n\n"
                    f"Текст новости:\n{text}"
                )}
            ],
            "temperature": 0.3, "max_tokens": 1000
        }
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: return None
        rewritten = response.json()['choices'][0]['message']['content'].strip()
        if any(root in rewritten.lower() for root in ["генеративн", "облада", "мнени", "ограничен", "неправильн", "благодарим", "отказ"]): return None
        if len(rewritten) < 50: return None
        rewritten = re.sub(r'[*_`#]', '', rewritten)
        rewritten = fix_title_case(rewritten)
        return re.sub(r'</b>\s*', '</b>\n\n', rewritten).strip()
    except Exception: return None

def generate_image_gigachat(news_text, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        theme = "Abstract 3D financial background, glowing blue and gold geometric shapes"
        if re.search(r'промышленн|завод|станкостроен|производств|фабрик|станок', news_text, re.IGNORECASE): theme = "Abstract 3D gears, robotic arm, industrial factory, blue and gold"
        elif re.search(r'нефт|газ|энергет|топлив|дизел|бензин|баррел|уголь|опек', news_text, re.IGNORECASE): theme = "Abstract 3D oil drop, gas pipes, energy lines, blue and gold"
        elif re.search(r'сельхоз|агро|урожай|ферм|зерно', news_text, re.IGNORECASE): theme = "Abstract 3D golden wheat ears, leaves, agriculture, blue and gold"
        elif re.search(r'туризм|отел|курорт|путешеств', news_text, re.IGNORECASE): theme = "Abstract 3D airplane, suitcase, globe, travel, blue and gold"
        elif re.search(r'экологи|esg|зелен|выброс|углерод', news_text, re.IGNORECASE): theme = "Abstract 3D green leaf, eco-friendly energy, blue and gold"
        elif re.search(r'фарм|медицин|лекарств|клиник', news_text, re.IGNORECASE): theme = "Abstract 3D medical cross, molecule, pill, blue and gold"
        elif re.search(r'труд|безработ|персонал|кадр|миграц', news_text, re.IGNORECASE): theme = "Abstract 3D silhouettes of people, briefcase, career graph, blue and gold"
        elif re.search(r'правительств|министр|кабинет|госдум|заседани|совещани', news_text, re.IGNORECASE): theme = "Abstract 3D government building with columns, golden scales, blue background"
        elif re.search(r'банк|цб|кредит|вклад|сбербанк|втб|тинькофф|регулятор', news_text, re.IGNORECASE): theme = "Abstract 3D bank building with gold columns, floating coins, blue background"
        elif re.search(r'самолет|авиа|жд|поезд|транспорт|логистик', news_text, re.IGNORECASE): theme = "Abstract 3D futuristic train or airplane, golden tracks, blue background"
        elif re.search(r'ипотек|дом|жкх|недвиж|квартир|стройк', news_text, re.IGNORECASE): theme = "Abstract 3D modern house, golden keys, blue background"
        elif re.search(r'крипт|биткоин|блокчейн|токен', news_text, re.IGNORECASE): theme = "Abstract 3D glowing bitcoin symbol, digital blocks, neon blue and gold"
        elif re.search(r'нейросет|чип|робот|технолог|apple|openai|айти', news_text, re.IGNORECASE): theme = "Abstract 3D glowing microchip, robotic brain, neon blue and gold circuits"
        elif re.search(r'акци|бирж|индекс|рынок|ставк|трейд', news_text, re.IGNORECASE): theme = "Abstract 3D stock market chart with glowing golden arrows going up, blue background"
        elif re.search(r'рубл|доллар|евро|деньг|цен|валют', news_text, re.IGNORECASE): theme = "Abstract 3D golden coins, floating banknotes, glowing blue arrows"
        elif re.search(r'ритейл|маркетплейс|wildberries|ozon|магазин', news_text, re.IGNORECASE): theme = "Abstract 3D shopping cart, shopping bags, retail, blue and gold"
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": f"{theme}. STRICTLY NO TEXT, NO LETTERS, NO NUMBERS."}
            ],
            "function_call": "auto"
        }
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: return None
        content = response.json()['choices'][0]['message']['content']
        match = re.search(r'<img src="([^"]+)"', content)
        if match:
            dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{match.group(1)}/content"
            img_res = SESSION.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=VERIFY_SSL, timeout=30)
            return img_res.content if img_res.status_code == 200 else None
        return None
    except Exception: return None

# =====================================================================
# ✈️ TELEGRAM
# =====================================================================
def send_photo(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if len(text) > 1000: text = text[:1000] + "..."
    try:
        res = SESSION.post(url, data={"chat_id": CHAT_ID, "caption": text, "parse_mode": "HTML"}, files={"photo": ("poster.jpg", image_bytes, "image/jpeg")}, timeout=30)
        return res.ok
    except: return False

def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = SESSION.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=15)
        return res.ok
    except: return False

# =====================================================================
# 🚀 MAIN
# =====================================================================
def main():
    history = load_json(HISTORY_FILE)
    embeddings_history = load_json(EMBEDDINGS_FILE)
    
    token = get_gigachat_token()
    if not token: return
    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        try: feed = feedparser.parse(feed_url)
        except Exception: continue
        
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                if not news_id or news_id in history: continue
                    
                title = clean_text(entry.title)
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if '�' in text_to_check or len(text_to_check) < 30: continue
                if BLACKLIST_REGEX.search(text_to_check): continue
                if not KEYWORDS_REGEX.search(text_to_check): continue

                print(f"🔥 Новость: {title[:40]}...")
                
                # --- 1. СЕМАНТИЧЕСКАЯ ДЕДУПЛИКАЦИЯ ---
                news_embedding = get_embedding(title, token)
                if news_embedding:
                    is_duplicate = False
                    for old_url, old_emb in embeddings_history.items():
                        similarity = cosine_similarity(news_embedding, old_emb)
                        if similarity > SIMILARITY_THRESHOLD:
                            print(f"⏭️ Пропуск (семантический дубль с {old_url[:30]}...). Сходство: {similarity:.2f}")
                            is_duplicate = True
                            break
                    if is_duplicate: continue

                # --- 2. ФАКТЧЕКИНГ ЦИФР ---
                original_percents = set(re.findall(r'(\d+(?:[.,]\d+)?)\s*%', text_to_check))

                category_header = detect_category(text_to_check)
                final_text = rewrite_text(f"{title}. {description}", token)
                if not final_text: continue
                
                if original_percents:
                    rewritten_lower = final_text.lower()
                    for p in original_percents:
                        p_variants = [p, p.replace(',', '.'), p.replace('.', ',')]
                        if not any(variant in rewritten_lower for variant in p_variants):
                            print(f"⏭️ Пропуск (фактчекинг): число {p}% не найдено.")
                            final_text = None
                            break
                
                if not final_text: continue

                image_bytes = generate_image_gigachat(text_to_check, token)
                text_to_publish = category_header + final_text + f"\n\n🔗 <a href='{news_id}'>Источник</a>"
                
                success = send_photo(text_to_publish, image_bytes) if image_bytes else send_text(text_to_publish)
                
                if success:
                    print("✅ Опубликовано!")
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
                print(f"Ошибка: {e}")
                continue
            if new_posts_count >= 1: return

if __name__ == '__main__':
    main()
