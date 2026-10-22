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

# 🚫 МАКСИМАЛЬНО РАСШИРЕННЫЙ ЧЕРНЫЙ СПИСОК (Все, что не относится к финансам)
BLACKLIST_REGEX = re.compile(
    # --- СПОРТ ---
    r'тренер|матч|гол|футбол|хоккей|спорт|чемпионат|кубок|олимпиад|клуб|игрок|трусов|'
    r'теннис|бокс|ufc|mma|фигурное|биатлон|плавание|футболист|хоккеист|медаль|турнир|'
    r'кхл|нхл|рпл|фнл|овертайм|шайб|вратар|голкипер|авангард|нефтехимик|баскетбол|волейбол|'
    r'фигурн|футзал|пляжн|киберспорт|букмекер|тотализатор|'
    # --- КРИМИНАЛ И ЧП ---
    r'погиб|убий|дтп|пожар|мчс|полици|суд|арест|взрыв|стрельб|теракт|мошенник|кража|ограблен|'
    r'наркотик|изнасилован|педофил|тюрьма|колония|приговор|прокурор|адвокат|утонул|госпитализирован|'
    r'плутоний|контрабанда|экстрадиция|отмывание|стрельба|катастроф|авария|крушение|жертв|'
    # --- ПОГОДА И ПРИРОДА ---
    r'погод|ураган|наводнен|паводок|землетрясен|циклон|шторм|гололед|снегопад|тайфун|цунами|'
    r'смерч|антициклон|температура воздуха|прогноз|'
    # --- КУЛЬТУРА, ШОУ-БИЗНЕС, МОДА ---
    r'шоу-бизнес|знаменитост|актер|певиц|развод|звезд|сериал|концерт|фестивал|инстаграм|тикток|блогер|скандал|'
    r'свадьба|беременна|родила|пластика|ютуб|хайп|аукцион|топор|фильм|кубрик|памятник|музей|гражданство|'
    r'выставк|театр|балет|опер|кинопремия|оскар|канн|подиум|мода|коллекц|дизайнер|премьера|'
    r'гастроли|ток-шоу|реалити|евровидение|кинопрокат|кассовые сборы|актриса|певец|музыкант|художник|скульптура|'
    r'литература|книга|роман|поэт|'
    # --- ЗДОРОВЬЕ И МЕДИЦИНА ---
    r'коронавирус|covid|вакцин|грипп|заболеваемост|эпидеми|пандеми|симптом|лекарств|клиник|врач|медицин|здоровье|'
    # --- ЛАЙФСТАЙЛ И ЕДА ---
    r'шок|сенсац|ужас|эксклюзив|гороскоп|астролог|рецепт|диет|похуден|отношени|'
    r'кулинар|ресторан|шеф-повар|фитнес|спортзал|красота|косметика|макияж|беременность|дети|'
    # --- ПОЛИТИКА И ГЕОПОЛИТИКА ---
    r'мобилизац|войн|спецоперац|трамп|байден|путин|медведев|зеленский|госдум|депутат|оппозиц|митинг|'
    r'лгбт|навальн|мигрант|религи|церковь|бпла|дроны|атак|сбит|ракет|украин|дмитриев|воробьев|мид|'
    r'посол|нато|выборы|конгресс|сенат|парламент|уголовн|следствен|пострадав|эвакуац|обнал|'
    r'отмыван|коррупц|взятк|пентагон|госдеп|кремль|белый дом|губернатор|мэр|мэрия|минобороны|пво|'
    r'уничтожили|обстрел|'
    # --- ТРАНСПОРТ И БЫТОВУХА ---
    r'самокат|велосипед|парковк|тротуар|пешеход|прорыв трубы|коммунальная авария|'
    r'указание|положение|депонент|ломбардный|памятная монета|'
    r'переноск|животн|поезд|вагон|кошек|собак|нерпа|тигр|фотоловушка', 
    re.IGNORECASE
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
    text = re.sub(r'(?i)domclick', '', text)
    text = re.sub(r'\.(ru|com|org|net)\s+\d{2}\.\d{2}\.\d{4}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b', '', text) 
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
        return None
    try:
        auth_str = f"{GIGA_CLIENT_ID.strip()}:{GIGA_CLIENT_SECRET.strip()}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json', 'RqUID': str(uuid.uuid4()), 'Authorization': f'Basic {auth_b64}'}
        response = SESSION.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
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

# =====================================================================
# 🤖 GIGACHAT: РЕРАЙТ ТЕКСТА (УСИЛЕННЫЙ ПРОМПТ ДЛЯ ФИЛЬТРАЦИИ)
# =====================================================================
def rewrite_text(text, token, source_url):
    if not token or not text: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": (
                    "Ты — профессиональный редактор финансового канала 'QIVONZA'. "
                    "Твоя задача — переписать ТОЛЬКО экономическую, финансовую или технологическую новость по шаблону. "
                    "КРИТИЧЕСКИ ВАЖНО: Если новость относится к СПОРТУ, КУЛЬТУРЕ, ШОУ-БИЗНЕСУ, МОДЕ, ЗДОРОВЬЮ, ПОГОДЕ, КРИМИНАЛУ или ПОЛИТИКЕ — напиши ровно одно слово: ОТКАЗ. "
                    "КРИТИЧЕСКИ ВАЖНО: Ты ОБЯЗАН переписать экономическую новость, даже если она про банки, ценные бумаги, РЕПО или депозиты. Не отказывайся от экономики. "
                    "Если новость написана сложным канцелярским языком (например, пресс-релизы ЦБ, статистика), объясни её суть простыми словами."
                )},
                {"role": "user", "content": (
                    f"Напиши подробный пост. Используй следующую структуру (раздели абзацы ДВУМЯ переносами строки):\n\n"
                    f"1. Суть новости (3-4 подробных предложения).\n"
                    f"2. Что это значит для кошелька или работы (2-3 предложения).\n"
                    f"3. Что дальше (1-2 предложения).\n\n"
                    f"ПРИМЕР ХОРОШЕГО ОТВЕТА:\n"
                    f"Банк России объявил о повышении ключевой ставки до 20% годовых. Это решение принято на фоне ускорения инфляции и ослабления рубля. Регулятор отметил, что ужесточение денежно-кредитной политики необходимо для стабилизации цен.\n\n"
                    f"Для обычных граждан это означает, что кредиты и ипотека станут дороже. Однако вклады и накопительные счета принесут больше дохода. Банкам придется пересмотреть условия по своим продуктам.\n\n"
                    f"В дальнейшем стоит следить за уровнем инфляции и заявлениями ЦБ. Это покажет, как долго продлится период высоких ставок.\n\n"
                    f"Текст новости:\n{text}"
                )}
            ],
            "temperature": 0.3, "max_tokens": 2000
        }
        
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: 
            return None
            
        raw_rewritten = response.json()['choices'][0]['message']['content'].strip()
        
        if "ОТКАЗ" in raw_rewritten.upper():
            return None

        if len(raw_rewritten) < 50: 
            return None
        
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', raw_rewritten) if p.strip()]
        
        if len(paragraphs) < 3:
            paragraphs = [p.strip() for p in raw_rewritten.split('\n') if p.strip()]
        
        if len(paragraphs) < 3:
            sentences = re.split(r'(?<=[.!?])\s+', raw_rewritten)
            if len(sentences) >= 4:
                chunk_size = len(sentences) // 3
                p1 = ' '.join(sentences[:chunk_size+1])
                p2 = ' '.join(sentences[chunk_size+1:chunk_size*2+1])
                p3 = ' '.join(sentences[chunk_size*2+1:])
                paragraphs = [p1, p2, p3]

        for i in range(len(paragraphs)):
            paragraphs[i] = re.sub(r'^(Что дальше\?|Что это значит\?)\s*', '', paragraphs[i]).strip()

        if len(paragraphs) >= 3:
            final_text = (
                f"{paragraphs[0]}\n\n"
                f"<b>Что это значит?</b>\n\n"
                f"{paragraphs[1]}\n\n"
                f"<b>Что дальше?</b>\n\n"
                f"{paragraphs[2]}"
            )
        elif len(paragraphs) == 2:
            final_text = (
                f"{paragraphs[0]}\n\n"
                f"<b>Что это значит?</b>\n\n"
                f"{paragraphs[1]}"
            )
        else:
            return None
        
        return final_text.strip()
    except Exception: 
        return None

# =====================================================================
# 🎨 GIGACHAT: ГЕНЕРАЦИЯ КАРТИНОК (РЕАЛИСТИЧНЫЕ, QIVONZA ТОЛЬКО НА ЭКРАНАХ)
# =====================================================================
def generate_image_gigachat(news_text, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        text_lower = news_text.lower()
        
        # Формируем РЕАЛИСТИЧНЫЙ визуальный промпт
        if any(w in text_lower for w in ['нефт', 'газ', 'энергет', 'топлив', 'дизел']):
            visual_topic = "A photorealistic scene of an oil refinery at golden sunset, industrial pipelines, dramatic sky, high detail"
        elif any(w in text_lower for w in ['банк', 'цб', 'кредит', 'вклад', 'сбербанк', 'втб']):
            visual_topic = "A photorealistic interior of a modern bank office with marble columns, warm golden lighting, professional atmosphere"
        elif any(w in text_lower for w in ['ипотек', 'дом', 'жкх', 'недвиж', 'квартир']):
            visual_topic = "A photorealistic modern luxury house with large glass windows, warm golden evening light, architectural photography"
        elif any(w in text_lower for w in ['нейросет', 'чип', 'робот', 'технолог', 'apple', 'openai']):
            visual_topic = "A photorealistic close-up of a futuristic microchip on a dark circuit board, glowing blue and gold lights, macro photography"
        elif any(w in text_lower for w in ['акци', 'бирж', 'индекс', 'рынок', 'ставк']):
            visual_topic = "A photorealistic view of a modern stock exchange trading floor with large screens and professional atmosphere"
        elif any(w in text_lower for w in ['крипт', 'биткоин', 'блокчейн']):
            visual_topic = "A photorealistic close-up of a golden Bitcoin coin on a dark surface with glowing blue digital elements"
        elif any(w in text_lower for w in ['рост', 'увеличен', 'прибыл', 'вырос']):
            visual_topic = "A photorealistic image of a financial analyst looking at a large monitor with rising golden charts in a modern office"
        elif any(w in text_lower for w in ['санкц', 'запрет', 'снижен', 'падени']):
            visual_topic = "A photorealistic image of a modern trading floor with falling red charts on large screens, dramatic atmosphere"
        else:
            visual_topic = "A photorealistic scene of a modern financial office with warm golden lighting, professional atmosphere, clean architecture"

        # Стиль: фотореализм + строгие правила для текста
        prompt = (
            f"{visual_topic}. "
            f"STYLE: photorealistic, cinematic lighting, 8k resolution, natural colors, professional photography, highly detailed. "
            f"TEXT RULES (STRICT): "
            f"1. If the scene contains a screen, monitor, chart, or document — write ONLY the word 'QIVONZA' on it in elegant font. "
            f"2. If the scene has NO screens, monitors, charts or documents — there MUST BE ABSOLUTELY NO TEXT ANYWHERE. "
            f"3. NEVER write any other words, letters, numbers, gibberish, or watermarks. "
            f"4. Do not add any UI elements, labels, or signs with text."
        )

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "You are a professional photographer and 3D artist. Use text2image. Return only <img src=\"FILE_ID\"/>"},
                {"role": "user", "content": prompt}
            ],
            "function_call": "auto"
        }
        
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: 
            return None
        content = response.json()['choices'][0]['message']['content']
        match = re.search(r'<img src="([^"]+)"', content)
        if match:
            dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{match.group(1)}/content"
            img_res = SESSION.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=VERIFY_SSL, timeout=30)
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
    if len(text) > 1000: text = text[:1000] + "..."
    try:
        res = SESSION.post(url, data={"chat_id": CHAT_ID, "caption": text, "parse_mode": "HTML"}, files={"photo": ("poster.jpg", image_bytes, "image/jpeg")}, timeout=30)
        return res.ok
    except Exception: 
        return False

def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = SESSION.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=15)
        return res.ok
    except Exception: 
        return False

# =====================================================================
# 🚀 MAIN
# =====================================================================
def main():
    history = load_json(HISTORY_FILE)
    embeddings_history = load_json(EMBEDDINGS_FILE)
    
    token = get_gigachat_token()
    if not token: 
        return
    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        try: feed = feedparser.parse(feed_url)
        except Exception: 
            continue
        
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                title = clean_text(entry.title)

                if not news_id or news_id in history: 
                    continue
                    
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if '�' in text_to_check or len(text_to_check) < 30: 
                    continue
                
                # Проверка по черному списку
                match = BLACKLIST_REGEX.search(text_to_check)
                if match: 
                    print(f"⏭️ Пропуск (ЧС: '{match.group(0)}'): {title[:30]}")
                    continue
                
                # Проверка по белому списку
                if not KEYWORDS_REGEX.search(text_to_check): 
                    print(f"⏭️ Пропуск (нет ключевых слов): {title[:30]}")
                    continue

                print(f"🔥 Новость прошла фильтры: {title[:40]}...")
                
                news_embedding = get_embedding(title, token)
                if news_embedding:
                    is_duplicate = False
                    for old_url, old_emb in embeddings_history.items():
                        similarity = cosine_similarity(news_embedding, old_emb)
                        if similarity > SIMILARITY_THRESHOLD:
                            print(f"⏭️ Пропуск (семантический дубль). Сходство: {similarity:.2f}")
                            is_duplicate = True
                            break
                    if is_duplicate: continue

                original_percents = set(re.findall(r'(\d+(?:[.,]\d+)?)\s*%', text_to_check))

                category_header = detect_category(text_to_check)
                final_text = rewrite_text(f"{title}. {description}", token, news_id)
                if not final_text: 
                    print("⏭️ Пропуск (GigaChat отказ или ошибка).")
                    continue
                
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
                continue
            if new_posts_count >= 1: return

if __name__ == '__main__':
    main()
