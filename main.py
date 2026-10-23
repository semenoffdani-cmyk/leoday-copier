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
# НАСТРОЙКИ И КОНСТАНТЫ
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
RAW_LOG_FILE = 'raw_gigachat.txt'

SIMILARITY_THRESHOLD = 0.85
MAX_EMBEDDINGS_HISTORY = 50
MAX_POSTS_PER_RUN = 1

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# =====================================================================
# ФИЛЬТРАЦИЯ: BLACKLIST / WHITELIST
# =====================================================================
BLACKLIST_PATTERNS = [
    # Спорт
    r'\bспорт\w*', r'\bматч\w*', r'\bфутбол\w*', r'\bхокке\w*', r'\bтренер\w*',
    r'\bгол\b', r'\bголы\b', r'\bчемпионат\w*', r'\bкубок\w*', r'\bолимпиад\w*',
    r'\bтеннис\w*', r'\bбокс\w*', r'\bufc\b', r'\bmma\b', r'\bфигурн\w*',
    r'\bбиатлон\w*', r'\bплаван\w*', r'\bфутболист\w*', r'\bхоккеист\w*',
    r'\bмедал\w*', r'\bтурнир\w*', r'\bкхл\b', r'\bнхл\b', r'\bрпл\b',
    r'\bфнл\b', r'\bбаскетбол\w*', r'\bволейбол\w*', r'\bфутзал\w*',
    r'\bкиберспорт\w*', r'\bбукмекер\w*', r'\bтотализатор\w*',

    # Криминал, ЧП, политика
    r'\bпогиб\w*', r'\bубий\w*', r'\bдтп\b', r'\bпожар\w*', r'\bмчс\b',
    r'\bполици\w*', r'\bсуд\b', r'\bарест\w*', r'\bвзрыв\w*', r'\bстрельб\w*',
    r'\bтеракт\w*', r'\bмошенничеств\w*', r'\bкраж\w*', r'\bограблен\w*',
    r'\bнаркотик\w*', r'\bприговор\w*', r'\bпрокурор\w*', r'\bадвокат\w*',
    r'\bутопул\w*', r'\bгоспитализирован\w*', r'\bжертв\w*', r'\bавари\w*',
    r'\bкатастроф\w*', r'\bкоррупц\w*', r'\bвзятк\w*', r'\bобнал\w*',
    r'\bмобилизац\w*', r'\bвойн\w*', r'\bспецоперац\w*', r'\bтрамп\w*',
    r'\bбайден\w*', r'\bпутин\w*', r'\bмедведев\w*', r'\bзеленск\w*',
    r'\bгосдум\w*', r'\bдепутат\w*', r'\bоппозиц\w*', r'\bмитинг\w*',
    r'\bлгбт\w*', r'\bнавальн\w*', r'\bмигрант\w*', r'\bрелиги\w*',
    r'\bцерков\w*', r'\bбпла\b', r'\bдрон\w*', r'\bатак\w*', r'\bсбит\w*',
    r'\bракет\w*', r'\bукраин\w*', r'\bпосол\w*', r'\bнато\b', r'\bвыбор\w*',
    r'\bконгресс\w*', r'\bсенат\w*', r'\bпарламент\w*', r'\bуголовн\w*',
    r'\bследствен\w*', r'\bпострадав\w*', r'\bэвакуац\w*', r'\bпентагон\w*',
    r'\bгосдеп\w*', r'\bкремл\w*', r'\bбелый дом\b', r'\bгубернатор\w*',
    r'\bмэр\w*', r'\bмэри\w*', r'\bминобороны\w*', r'\bпво\b',
    r'\bуничтожил\w*', r'\bобстрел\w*',

    # Погода и природа
    r'\bпогод\w*', r'\bураган\w*', r'\bнаводнен\w*', r'\bпаводок\w*',
    r'\bземлетрясен\w*', r'\bциклон\w*', r'\bшторм\w*', r'\bгололед\w*',
    r'\bснегопад\w*', r'\bтайфун\w*', r'\bцунами\w*', r'\bсмерч\w*',
    r'\bантициклон\w*', r'\bтемпература воздуха\b', r'\bпрогноз погоды\b',

    # Культура, шоу-бизнес, мода, Музыка
    r'\bшоу-бизнес\w*', r'\bзнаменитост\w*', r'\bактер\w*', r'\bактрис\w*',
    r'\bпевиц\w*', r'\bпевец\w*', r'\bразвод\w*', r'\bзвезд\w*',
    r'\bсериал\w*', r'\bконцерт\w*', r'\bфестивал\w*', r'\bинстаграм\w*',
    r'\bтикток\w*', r'\bблогер\w*', r'\bскандал\w*', r'\bсвадьб\w*',
    r'\bбеременн\w*', r'\bродила\b', r'\bпластик\w*', r'\bютуб\w*',
    r'\bхайп\w*', r'\bаукцион\w*', r'\bфильм\w*', r'\bпремьер\w*',
    r'\bгастрол\w*', r'\bток-шоу\b', r'\bреалити\b', r'\bевровидени\w*',
    r'\bкино\w*', r'\bтеатр\w*', r'\bбалет\w*', r'\bопер\w*', r'\bоскар\w*',
    r'\bканн\w*', r'\bподиум\w*', r'\bмода\b', r'\bмоды\b', r'\bмоде\b',
    r'\bмодный\b', r'\bколлекц\w*', r'\bдизайнер\w*', r'\bпремьера\w*',
    r'\bпесн\w*', r'\bтрек\w*', r'\bальбом\w*', r'\bмузык\w*', r'\bгазманов\w*',

    # Здоровье и медицина
    r'\bкоронавирус\w*', r'\bcovid\w*', r'\bвакцин\w*', r'\bгрипп\w*',
    r'\bзаболеваемост\w*', r'\bэпидеми\w*', r'\bпандеми\w*', r'\bсимптом\w*',
    r'\bлекарств\w*', r'\bклиник\w*', r'\bврач\w*', r'\bмедицин\w*',
    r'\bздоров\w*', r'\bболезн\w*',

    # Быт, транспорт, животные
    r'\bсамокат\w*', r'\bвелосипед\w*', r'\bпарковк\w*', r'\bтротуар\w*',
    r'\bпешеход\w*', r'\bпрорыв трубы\b', r'\bкоммунальная авария\b',
    r'\bуказание\b', r'\bположение\b', r'\bдепонент\w*', r'\bломбард\w*',
    r'\bпамятная монета\b', r'\bпереноск\w*', r'\bживотн\w*', r'\bпоезд\w*',
    r'\bвагон\w*', r'\bкошек\b', r'\bсобак\b', r'\bнерпа\w*', r'\bтигр\w*',
    r'\bфотоловушк\w*'
]
BLACKLIST_REGEX = re.compile('|'.join(BLACKLIST_PATTERNS), re.IGNORECASE)

WHITELIST_PATTERNS = [
    r'\bставк\w*', r'\bрубл\w*', r'\bинфляц\w*', r'\bцб\b', r'\bбанк\w*',
    r'\bакци\w*', r'\bнефт\w*', r'\bбюджет\w*', r'\bналог\w*', r'\bфинанс\w*',
    r'\bкредит\w*', r'\bвклад\w*', r'\bбирж\w*', r'\bдоллар\w*', r'\bевро\b',
    r'\bрынок\w*', r'\bэкономик\w*', r'\bкомпани\w*', r'\bубыт\w*',
    r'\bприбыл\w*', r'\bтариф\w*', r'\bцен\w*', r'\bрецесс\w*', r'\bдефляц\w*',
    r'\bпрофицит\w*', r'\bдефицит\w*', r'\bросстат\w*', r'\bввп\b',
    r'\bинвест\w*', r'\bдивиденд\w*', r'\bоблигац\w*', r'\bбонд\w*', r'\bфонд\w*',
    r'\bиндекс\w*', r'\bкапитализац\w*', r'\bipo\b', r'\bактив\w*',
    r'\bкрипт\w*', r'\bбиткоин\w*', r'\bблокчейн\w*', r'\bтрейд\w*',
    r'\bмосбирж\w*', r'\bзарплат\w*', r'\bпенси\w*', r'\bипотек\w*',
    r'\bбанкрот\w*', r'\bсубсиди\w*', r'\bпособи\w*', r'\bдороговизн\w*',
    r'\bжкх\b', r'\bкоммуналк\w*', r'\bштраф\w*', r'\bльгот\w*',
    r'\bматкапитал\w*', r'\bсбербанк\w*', r'\bвтб\b', r'\bтинькофф\w*',
    r'\bт-банк\w*', r'\bальфа-банк\w*', r'\bгосуслуг\w*', r'\bсбой\w*',
    r'\bсделк\w*', r'\bпоглощен\w*', r'\bстартап\w*', r'\bкорпорац\w*',
    r'\bмонопол\w*', r'\bфраншиз\w*', r'\bритейл\w*', r'\bмаркетплейс\w*',
    r'\bwildberries\b', r'\bozon\b', r'\bпошлин\w*', r'\bэкспорт\w*',
    r'\bимпорт\w*', r'\bнейросет\w*', r'\bискусственн\w*', r'\bтехнолог\w*',
    r'\bробот\w*', r'\bцифров\w*', r'\bгаджет\w*', r'\bсмартфон\w*',
    r'\bopenai\b', r'\bchatgpt\b', r'\bяндекс\w*', r'\bсбер\w*', r'\bайти\b',
    r'\bит-\w*', r'\bии\b', r'\bчип\w*', r'\bпроцессор\w*', r'\bсофт\w*',
    r'\bприложени\w*', r'\bкибербезопасн\w*', r'\bсервер\w*', r'\bоблак\w*',
    r'\bимпортозамещен\w*', r'\bapple\b', r'\btesla\b', r'\bmicrosoft\b',
    r'\bgoogle\b', r'\bamazon\b', r'\bmeta\b', r'\bnvidia\b', r'\bsamsung\b',
    r'\bintel\b', r'\bspacex\b', r'\bэнергет\w*', r'\bдизел\w*',
    r'\bтоплив\w*', r'\bбатаре\w*', r'\bдевальвац\w*', r'\bревальвац\w*',
    r'\bхеджирован\w*', r'\bфьючерс\w*', r'\bопцион\w*', r'\bтрейдер\w*',
    r'\bпромышленн\w*', r'\bзавод\w*', r'\bпроизводств\w*', r'\bфабрик\w*',
    r'\bсельхоз\w*', r'\bагро\w*', r'\bурожай\w*', r'\bтуризм\w*',
    r'\bотель\w*', r'\bэколог\w*', r'\besg\b', r'\bфарм\w*', r'\bтруд\w*',
    r'\bбезработ\w*', r'\bперсонал\w*', r'\bкадр\w*', r'\bмиграц\w*',
    r'\bлогистик\w*', r'\bтранспорт\w*', r'\bстройк\w*', r'\bнедвижим\w*',
    r'\bлицензи\w*', r'\bкапитал\w*', r'\bнорматив\w*', r'\bрезерв\w*',
    r'\bбаланс\w*', r'\bотчетност\w*', r'\bсанаци\w*', r'\bликвидац\w*',
    r'\bгосподдержк\w*', r'\bпоправк\w*', r'\bрепо\b', r'\bдепозит\w*'
]
KEYWORDS_REGEX = re.compile('|'.join(WHITELIST_PATTERNS), re.IGNORECASE)

SKIP_URL_REGEX = re.compile(
    r'cbr\.ru/(statistics|hd_base|analytics|finorg|insurance/faq|DKP/creditco)',
    re.IGNORECASE
)

SESSION = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
SESSION.mount('https://', HTTPAdapter(max_retries=retries))

# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def remove_garbage(text):
    known_brands = {
        'brent', 'wti', 'urals', 'espo', 'opec', 'aramco', 'total', 'eni', 
        'novatek', 'transneft', 'sibur', 'shell', 'bp', 'exxon', 'chevron',
        'visa', 'mastercard', 'nasdaq', 'nyse', 'moex', 'lse', 'dow', 'sp500', 
        'ftse', 'cme', 'jpmorgan', 'goldman', 'sachs', 'morgan', 'stanley', 
        'hsbc', 'paypal', 'swift', 'citi', 'fed', 'ecb', 'frs', 'imf', 'wto', 'gdp',
        'gazprom', 'rosneft', 'lukoil', 'sber', 'vtb', 'tinkoff', 'alfa',
        'bitcoin', 'btc', 'eth', 'ethereum', 'blockchain', 'defi', 'nft', 'xrp', 
        'cardano', 'dogecoin', 'binance', 'coinbase', 'solana', 'usdt', 'usdc', 'tether',
        'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'nvidia',
        'samsung', 'intel', 'spacex', 'openai', 'chatgpt', 'gigachat', 'deepmind', 
        'anthropic', 'claude', 'gemini', 'copilot', 'yandex', 'ozon', 'wildberries', 
        'avito', 'python', 'linux', 'android', 'ios', 'midjourney', 'stable', 'diffusion', 
        'kandinsky', 'huawei', 'xiaomi', 'tiktok', 'youtube', 'netflix', 'php', 'api',
        'boeing', 'airbus', 'ford', 'toyota', 'bmw', 'audi', 'mercedes', 
        'volkswagen', 'byd', 'stellantis', 'renault', 'nissan', 'hyundai', 'kia',
        'ipo', 'esg', 'ai', 'it', 'rbc', 'ria', 'cbr'
    }

    def replace_word(match):
        word = match.group(0)
        if word.lower() in known_brands:
            return word
        return ''

    text = re.sub(r'\b[a-zA-Z]{4,}\b', replace_word, text)
    text = re.sub(r'(?i)amburg\w*', '', text)
    text = re.sub(r'(?i)domclick', '', text)
    text = re.sub(r'\.(ru|com|org|net)\s+\d{2}\.\d{2}\.\d{4}', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b', '', text)
    return text


def fix_caps(text):
    if text.isupper():
        abbreviations = r'\b(РФ|США|ЦБ|ВВП|ЕС|ОПЕК|НАТО|СССР|СНГ|МВФ|ФСБ|МВД|РБК|РИА)\b'
        text = re.sub(abbreviations, lambda m: m.group(0), text)
        text = text.capitalize()
        text = re.sub(r'\.\s*([а-яa-z])', lambda m: '. ' + m.group(1).upper(), text)
    return text


def clean_text(text):
    if not text:
        return ""
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
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_json(data, filepath):
    try:
        if filepath == HISTORY_FILE and len(data) > 2000:
            data = dict(list(data.items())[-2000:])
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения {filepath}: {e}")


def save_raw_response(news_url, raw):
    try:
        with open(RAW_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"--- НОВОСТЬ: {news_url} ---\n{raw}\n-----------------------------\n\n")
    except Exception as e:
        print(f"Ошибка записи raw_gigachat.txt: {e}")


def normalize_url(url):
    if not url:
        return ''
    return url.split('#')[0].strip()


def extract_percents(text):
    result = set()
    for match in re.findall(r'(\d+(?:[.,]\d+)?)\s*%', text):
        result.add(match.replace(',', '.'))
    for match in re.findall(r'(\d+(?:[.,]\d+)?)\s*(?:процент|процента|процентов)', text, re.IGNORECASE):
        result.add(match.replace(',', '.'))
    return result


def percent_variants(percent):
    p = percent.replace(',', '.')
    variants = {p, p.replace('.', ','), f'{p}%', f'{p} %'}
    if p.endswith('.0'):
        short = p[:-2]
        variants.update({short, f'{short}%', f'{short} %'})
        p_for_words = short
    else:
        p_for_words = p

    for word in ('процент', 'процента', 'процентов'):
        variants.add(f'{p_for_words} {word}')
        variants.add(f'{p_for_words} {word}'.replace('.', ','))
    return variants


def is_refusal(text):
    if not text:
        return True
    t = text.lower().strip()
    if len(t) > 700:
        return False
    markers = (
        'отказ', 'к сожалению', 'не обладает собственным мнением',
        'временно ограничены', 'не могу', 'не имею возможности',
        'как языковая модель', 'генеративные языковые модели',
        'ответы на вопросы, связанные с чувствительными темами',
        'благодарим за понимание',
    )
    return any(marker in t for marker in markers)


def clean_gigachat_paragraph(p):
    p = re.sub(r'[*#_]{2,}', '', p)
    header_pattern = r'^(?:Суть новости|Что это значит(?:\s+для\s+кошелька(?:\s+или\s+работы)?)?|Что дальше)\??[:\s\-—]*'
    p = re.sub(header_pattern, '', p, flags=re.IGNORECASE)
    p = re.sub(r'^\d+[\.\)]\s*', '', p)
    return p.strip()

# =====================================================================
# УМНАЯ СИСТЕМА РУБРИК (ИСПОЛЬЗУЕМ ГРАНИЦЫ СЛОВ)
# =====================================================================
def detect_category(text):
    if re.search(r'промышленн|завод|станкостроен|производств|фабрик|сельхоз|агро|туризм|отель|ритейл|маркетплейс|бизнес|компани|предпринимат', text, re.IGNORECASE):
        return "🏭 <b>БИЗНЕС И ПРОМЫШЛЕННОСТЬ</b>\n\n"
    if re.search(r'нефт|\bгаз\b|\bгазпром\b|\bгазов\w*|энергет|топлив|дизел|\bbrent\b|\bwti\b|\burals\b', text, re.IGNORECASE):
        return "🛢️ <b>ЭНЕРГЕТИКА И СЫРЬЕ</b>\n\n"
    if re.search(r'вклад|кредит|ипотек|зарплат|пенси|жкх|рубл|доллар|евро|сбербанк|втб|тинькофф|банк|страхов|маткапитал', text, re.IGNORECASE):
        return "💸 <b>ЛИЧНЫЕ ДЕНЬГИ</b>\n\n"
    if re.search(r'нейросет|искусственн|чип|робот|технолог|apple|openai|смартфон|гаджет|ит-|айти|кибербезопасн|\bии\b|софт|приложени|яндекс', text, re.IGNORECASE):
        return "🤖 <b>ТЕХНОЛОГИИ И ИИ</b>\n\n"
    return "📊 <b>ЭКОНОМИКА</b>\n\n"

# =====================================================================
# GIGACHAT: АВТОРИЗАЦИЯ И ВЕКТОРЫ
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
        response = SESSION.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None


def get_embedding(text, token):
    if not token or not text:
        return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {"model": "Embeddings", "input": [text]}
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=30)
        if response.status_code == 200:
            return response.json()['data'][0]['embedding']
        
        # Логируем ошибку в консоль
        print(f"⚠️ Ошибка API эмбеддингов: HTTP {response.status_code} - {response.text[:150]}")
        return None
    except Exception as e:
        print(f"⚠️ Исключение в get_embedding: {e}")
        return None


def cosine_similarity(vec1, vec2):
    if not vec1 or not vec2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

# =====================================================================
# GIGACHAT: РЕРАЙТ ТЕКСТА
# =====================================================================
def rewrite_text(text, token, source_url):
    if not token or not text:
        return None

    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

        system_prompt = (
            "Ты — профессиональный редактор финансового канала «QIVONZA». "
            "Твоя задача — переписать новость простым, живым русским языком. "
            "Ты работаешь ТОЛЬКО с экономикой, финансами, банками, рынками, технологиями и ИИ. "
            "Если новость про спорт, культуру, шоу-бизнес, моду, здоровье, погоду, криминал, политику, бытовуху, "
            "животных, транспорт или личные драмы — ответь ровно одним словом: ОТКАЗ. "
            "ВАЖНО: если новость про экономику, банки, ЦБ, РЕПО, депозиты, облигации, ставку, инфляцию, "
            "статистику, рынок, компании, технологии или ИИ — ты ОБЯЗАН переписать её. "
            "Не отказывайся от экономики, даже если текст сухой, канцелярский или похож на пресс-релиз ЦБ. "
            "Объясни суть простыми словами. Не добавляй дисклеймеры. Не пиши, что ты ИИ. "
            "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать Markdown (символы **, *, #, _). Только чистый текст. "
            "ЗАПРЕЩЕНО писать заголовки и подзаголовки (например, «Суть новости:», «Что это значит:», «Что дальше:»). "
            "Твой ответ должен состоять ровно из трех абзацев чистого текста."
        )

        user_prompt = (
            "Напиши пост строго из трёх абзацев. Разделяй абзацы ДВУМЯ переносами строки.\n\n"
            "Структура:\n"
            "1. Суть новости: 3-4 подробных предложения, минимум 150 символов.\n"
            "2. Что это значит для кошелька или работы: 2-3 предложения.\n"
            "3. Что дальше: 1-2 предложения, за чем следить.\n\n"
            "Не пиши сами заголовки — просто начни первый абзац с сути, второй с последствий, третий с выводов. "
            "Не используй списки, нумерацию и Markdown. "
            "Если в исходном тексте есть проценты или названия (например, Brent, WTI, Visa) — обязательно сохрани их в ответе.\n\n"
            "Пример хорошего ответа:\n"
            "Банк России объявил о повышении ключевой ставки до 20% годовых. "
            "Это решение принято на фоне ускорения инфляции и ослабления рубля. "
            "Регулятор отметил, что ужесточение денежно-кредитной политики необходимо для стабилизации цен.\n\n"
            "Для обычных граждан это означает, что кредиты и ипотека станут дороже. "
            "Однако вклады и накопительные счета принесут больше дохода. "
            "Банкам придётся пересмотреть условия по своим продуктам.\n\n"
            "В дальнейшем стоит следить за уровнем инфляции и заявлениями ЦБ. "
            "Это покажет, как долго продлится период высоких ставок.\n\n"
            f"Текст новости:\n{text}"
        )

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200:
            save_raw_response(source_url, f"HTTP {response.status_code}: {response.text[:1000]}")
            return None

        raw_rewritten = response.json()['choices'][0]['message']['content'].strip()
        save_raw_response(source_url, raw_rewritten)

        if is_refusal(raw_rewritten):
            return None

        if len(raw_rewritten) < 80:
            return None

        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', raw_rewritten) if p.strip()]
        if len(paragraphs) < 3:
            paragraphs = [p.strip() for p in raw_rewritten.split('\n') if p.strip()]

        if len(paragraphs) < 3:
            sentences = re.split(r'(?<=[.!?])\s+', raw_rewritten)
            if len(sentences) >= 4:
                chunk_size = len(sentences) // 3
                p1 = ' '.join(sentences[:chunk_size + 1])
                p2 = ' '.join(sentences[chunk_size + 1:chunk_size * 2 + 1])
                p3 = ' '.join(sentences[chunk_size * 2 + 1:])
                paragraphs = [p1, p2, p3]

        cleaned_paragraphs = []
        for p in paragraphs:
            cleaned = clean_gigachat_paragraph(p)
            if cleaned:
                cleaned_paragraphs.append(cleaned)

        if len(cleaned_paragraphs) < 3:
            return None

        p1, p2, p3 = cleaned_paragraphs[0], cleaned_paragraphs[1], cleaned_paragraphs[2]

        final_text = (
            f"{p1}\n\n"
            f"<b>Что это значит?</b>\n\n"
            f"{p2}\n\n"
            f"<b>Что дальше?</b>\n\n"
            f"{p3}"
        )
        return final_text.strip()

    except Exception as e:
        save_raw_response(source_url, f"EXCEPTION: {e}")
        return None

# =====================================================================
# GIGACHAT: ГЕНЕРАЦИЯ КАРТИНКИ (ИСПОЛЬЗУЕМ РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ)
# =====================================================================
def generate_image_gigachat(news_text, token):
    if not token:
        return None

    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

        text_lower = news_text.lower()

        if re.search(r'биржа|мосбиржа|бонд|облигац|трейд', text_lower):
            visual_topic = (
                "A photorealistic view of a modern stock exchange trading floor "
                "with large screens and professional atmosphere, cinematic lighting"
            )
        elif re.search(r'нефт|\bгаз\b|\bгазпром\b|\bгазов\w*|энергет|топлив|дизел|\bbrent\b|\bwti\b|\burals\b', text_lower):
            visual_topic = (
                "A photorealistic scene of an oil refinery at golden sunset, "
                "industrial pipelines, dramatic sky, high detail"
            )
        elif re.search(r'банк|\bцб\b|кредит|вклад|сбербанк|\bвтб\b', text_lower):
            visual_topic = (
                "A photorealistic interior of a modern bank office with marble columns, "
                "warm golden lighting, professional atmosphere"
            )
        elif re.search(r'ипотек|дом|жкх|недвиж|квартир', text_lower):
            visual_topic = (
                "A photorealistic modern luxury house with large glass windows, "
                "warm golden evening light, architectural photography"
            )
        elif re.search(r'нейросет|чип|робот|технолог|apple|openai|яндекс', text_lower):
            visual_topic = (
                "A photorealistic close-up of a futuristic microchip on a dark circuit board, "
                "glowing blue and gold lights, macro photography"
            )
        elif re.search(r'акци|индекс|рынок|ставк', text_lower):
            visual_topic = (
                "A photorealistic view of a modern stock exchange trading floor with large screens "
                "and professional atmosphere"
            )
        elif re.search(r'крипт|биткоин|блокчейн', text_lower):
            visual_topic = (
                "A photorealistic close-up of a golden Bitcoin coin on a dark surface "
                "with glowing blue digital elements"
            )
        elif re.search(r'рост|увелич|прибыл|вырос', text_lower):
            visual_topic = (
                "A photorealistic image of a financial analyst looking at a large monitor "
                "with rising golden charts in a modern office"
            )
        elif re.search(r'санкц|запрет|снижен|падени', text_lower):
            visual_topic = (
                "A photorealistic image of a modern trading floor with falling red charts "
                "on large screens, dramatic atmosphere"
            )
        else:
            visual_topic = (
                "A photorealistic scene of a modern financial office with warm golden lighting, "
                "professional atmosphere, clean architecture"
            )

        prompt = (
            f"{visual_topic}. "
            "STYLE: photorealistic, cinematic lighting, 8k resolution, natural colors, "
            "professional photography, highly detailed. "
            "TEXT RULES (STRICT): "
            "1. If the scene contains a screen, monitor, chart, or document — write ONLY the word "
            "'QIVONZA' on it in elegant font. "
            "2. If the scene has NO screens, monitors, charts or documents — there MUST BE ABSOLUTELY NO TEXT ANYWHERE. "
            "3. NEVER write any other words, letters, numbers, gibberish, or watermarks. "
            "4. Do not add any UI elements, labels, or signs with text."
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
        if is_refusal(content):
            return None

        match = re.search(r'<img src="([^"]+)"', content)
        if not match:
            return None

        dl_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{match.group(1)}/content"
        img_res = SESSION.get(dl_url, headers={'Authorization': f'Bearer {token}'}, verify=VERIFY_SSL, timeout=30)
        if img_res.status_code == 200:
            return img_res.content
        return None

    except Exception:
        return None

# =====================================================================
# TELEGRAM
# =====================================================================
def send_photo(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if len(text) > 1024:
        text = text[:1000] + "..."
    try:
        res = SESSION.post(
            url,
            data={"chat_id": CHAT_ID, "caption": text, "parse_mode": "HTML"},
            files={"photo": ("poster.jpg", image_bytes, "image/jpeg")},
            timeout=30
        )
        return res.ok
    except Exception:
        return False


def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = SESSION.post(
            url,
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
        return res.ok
    except Exception:
        return False

# =====================================================================
# MAIN
# =====================================================================
def main():
    history = load_json(HISTORY_FILE)
    embeddings_history = load_json(EMBEDDINGS_FILE)

    token = get_gigachat_token()
    if not token:
        print("Не удалось получить токен GigaChat.")
        return

    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue

        for entry in feed.entries[:30]:
            try:
                news_id = normalize_url(entry.link)
                title = clean_text(entry.title)

                if not news_id or news_id in history:
                    continue

                if SKIP_URL_REGEX.search(news_id):
                    print(f"⏭️ Пропуск (справочная страница CBR): {news_id}")
                    continue

                description = clean_text(getattr(entry, 'description', '') or '')
                text_to_check = f"{title}. {description}".lower()

                if '\ufffd' in text_to_check or len(text_to_check) < 60:
                    print(f"⏭️ Пропуск (битый или короткий текст): {title[:40]}")
                    continue

                match = BLACKLIST_REGEX.search(text_to_check)
                if match:
                    print(f"⏭️ Пропуск (ЧС: '{match.group(0)}'): {title[:40]}")
                    continue

                if not KEYWORDS_REGEX.search(text_to_check):
                    print(f"⏭️ Пропуск (нет ключевых слов): {title[:40]}")
                    continue

                print(f"🔥 Новость прошла фильтры: {title[:60]}...")

                embedding_text = f"{title}. {description[:300]}"
                news_embedding = get_embedding(embedding_text, token)

                # ИСПРАВЛЕНИЕ: Если API упал, мы не блокируем новость, а пропускаем проверку на дубль.
                # history.json всё равно защитит от точных совпадений.
                if news_embedding:
                    is_duplicate = False
                    for old_url, old_emb in embeddings_history.items():
                        similarity = cosine_similarity(news_embedding, old_emb)
                        if similarity > SIMILARITY_THRESHOLD:
                            print(f"⏭️ Пропуск (семантический дубль). Сходство: {similarity:.2f}")
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue
                else:
                    print("⚠️ Эмбеддинг не получен. Пропускаем проверку на семантический дубль.")

                original_percents = extract_percents(text_to_check)
                category_header = detect_category(text_to_check)
                final_text = rewrite_text(f"{title}. {description}", token, news_id)

                if not final_text:
                    print("⏭️ Пропуск (GigaChat отказ или ошибка).")
                    continue

                if original_percents:
                    rewritten_lower = final_text.lower().replace(',', '.')
                    missing_percent = False
                    for percent in original_percents:
                        variants = percent_variants(percent)
                        if not any(v.lower().replace(',', '.') in rewritten_lower for v in variants):
                            print(f"⏭️ Пропуск (факт-чекинг): число {percent}% не найдено.")
                            missing_percent = True
                            break
                    if missing_percent:
                        continue

                image_bytes = generate_image_gigachat(text_to_check, token)
                text_to_publish = f"{category_header}{final_text}\n\n🔗 <a href='{news_id}'>Источник</a>"

                if image_bytes:
                    success = send_photo(text_to_publish, image_bytes)
                    if not success:
                        print("⚠️ Фото не отправилось, пробуем текстом.")
                        success = send_text(text_to_publish)
                else:
                    success = send_text(text_to_publish)

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

                    if new_posts_count >= MAX_POSTS_PER_RUN:
                        return

            except Exception as e:
                print(f"Ошибка обработки новости: {e}")
                continue

if __name__ == '__main__':
    main()
