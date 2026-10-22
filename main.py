import os
import json
import re
import time
import html
import uuid
import base64
import requests
import feedparser
import urllib3
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Отключаем предупреждения о сертификатах
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

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# 🚫 РАСШИРЕННЫЙ ЧЕРНЫЙ СПИСОК (Для мгновенного отсева мусора)
# Включает спорт, ЧП, светскую хронику, военную/политическую лексику и криминал,
# на котором нейросеть часто выдает "ОТКАЗ".
BLACKLIST_REGEX = re.compile(
    r'тренер|матч|гол|футбол|хоккей|спорт|чемпионат|кубок|олимпиад|клуб|игрок|трусов|'
    r'погиб|убий|дтп|пожар|мчс|полици|суд|арест|взрыв|стрельб|теракт|мошенник|кража|ограблен|'
    r'погод|ураган|наводнен|паводок|землетрясен|циклон|шторм|шоу-бизнес|знаменитост|'
    r'актер|певиц|развод|звезд|сериал|концерт|фестивал|инстаграм|тикток|блогер|скандал|'
    r'шок|сенсац|ужас|эксклюзив|гороскоп|астролог|рецепт|диет|похуден|отношени|коронавирус|'
    r'вакцин|грипп|заболеваемост|эпидеми|симптом|мобилизац|войн|санкц|спецоперац|'
    r'трамп|байден|путин|госдум|депутат|оппозиц|митинг|лгбт|навальн|мигрант|религи|'
    r'церковь|бпла|атак|сбит|ракет|украин|дмитриев|воробьев|мид|нато|выборы|конгресс|'
    r'сенат|парламент|уголовн|следствен|пострадав|жертв|эвакуац|обнал|отмыван|коррупц|взятк', 
    re.IGNORECASE
)

# ✅ БЕЛЫЙ СПИСОК (Что мы хотим видеть)
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
    r'ревальвац|хеджирован|фьючерс|опцион|трейдер', re.IGNORECASE
)

# Настройка сессии с автоматическими повторными попытками (Retry)
SESSION = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
SESSION.mount('https://', HTTPAdapter(max_retries=retries))

# =====================================================================
# 🧹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================
def clean_text(text):
    if not text:
        return ""
    # Удаляем HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    # Раскодируем сущности (например, &quot; в кавычки)
    text = html.unescape(text)
    # Убираем лишние пробелы и ссылки
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    # Экранируем обратно для безопасности Telegram
    return html.escape(text).strip()

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
        # Обрезаем словарь, оставляя только последние 2000 записей (оптимизация памяти)
        if len(history) > 2000:
            history = dict(list(history.items())[-2000:])
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
    if re.search(r'нефт|газ|энергет|топлив|дизел|бензин|баррел', text, re.IGNORECASE):
        return "🛢️ <b>ЭНЕРГЕТИКА</b>\n\n"
    elif re.search(r'нейросет|искусственн|чип|робот|технолог|apple|openai|смартфон|гаджет|ит-|айти|кибербезопасн|\bии\b', text, re.IGNORECASE):
        return "🤖 <b>ТЕХНОЛОГИИ</b>\n\n"
    elif re.search(r'вклад|кредит|ипотек|зарплат|пенси|жкх|рубл|доллар|евро|сбербанк|втб|тинькофф|банк', text, re.IGNORECASE):
        return "💸 <b>ДЕНЬГИ</b>\n\n"
    return "📊 <b>ЭКОНОМИКА</b>\n\n"

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
        response = SESSION.post(url, headers=headers, data='scope=GIGACHAT_API_PERS', verify=VERIFY_SSL, timeout=30)
        return response.json().get('access_token') if response.status_code == 200 else None
    except Exception:
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
                {"role": "system", "content": "Ты — профессиональный редактор финансового канала. Пиши строго по шаблону. Если новость НЕ ОТНОСИТСЯ к экономике, финансам, бизнесу или технологиям, напиши ровно одно слово: ОТКАЗ. Игнорируй обрывки ссылок и мусор."},
                {"role": "user", "content": f"Напиши пост строго по шаблону:\n\n<b>Что произошло?</b>\n\n[1-2 предложения сути]\n\n<b>Что это значит для ваших денег и работы?</b>\n\n[1-2 предложения о влиянии]\n\n<b>За чем следить дальше?</b>\n\n[1 предложение]\n\nТекст новости:\n{text}"}
            ],
            "temperature": 0.3, "max_tokens": 1000
        }
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: return None
            
        rewritten = response.json()['choices'][0]['message']['content'].strip()
        
        # Защита от отказов нейросети
        if any(root in rewritten.lower() for root in ["генеративн", "облада", "мнени", "ограничен", "неправильн", "благодарим", "отказ"]):
            return None
            
        # Защита от "пустых" ответов
        if len(rewritten) < 50:
            return None
            
        rewritten = re.sub(r'[*_`#]', '', rewritten)
        rewritten = fix_title_case(rewritten)
        return re.sub(r'</b>\s*', '</b>\n\n', rewritten).strip()
    except Exception:
        return None

def generate_image_gigachat(news_text, token):
    if not token: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        
        theme = "Abstract 3D financial background, glowing blue and gold geometric shapes"
        if re.search(r'нефт|газ|энергет|топлив', news_text, re.IGNORECASE): theme = "Abstract 3D oil drop, gas pipes, glowing blue and gold"
        elif re.search(r'ипотек|дом|жкх|недвиж|квартир', news_text, re.IGNORECASE): theme = "Abstract 3D modern house, golden keys, blue background"
        elif re.search(r'крипт|биткоин|блокчейн', news_text, re.IGNORECASE): theme = "Abstract 3D glowing bitcoin symbol, digital blocks"
        elif re.search(r'самолет|авиа|жд|поезд|транспорт', news_text, re.IGNORECASE): theme = "Abstract 3D futuristic train, golden tracks"
        elif re.search(r'банк|цб|кредит|вклад|сбербанк', news_text, re.IGNORECASE): theme = "Abstract 3D bank building with gold columns, coins"
        elif re.search(r'нейросет|чип|робот|технолог|apple', news_text, re.IGNORECASE): theme = "Abstract 3D glowing microchip, robotic brain"
        elif re.search(r'акци|бирж|индекс|рынок|ставк', news_text, re.IGNORECASE): theme = "Abstract 3D stock market chart with golden arrows"
        
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
    except Exception:
        return None

# =====================================================================
# ✈️ TELEGRAM
# =====================================================================
def send_photo(text, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    # Жесткая обрезка под лимит подписи к фото в Telegram (1024 символа)
    if len(text) > 1000:
        text = text[:1000] + "..."

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
    history = load_history()
    token = get_gigachat_token()
    
    if not token:
        print("КРИТИЧЕСКАЯ ОШИБКА: GigaChat недоступен.")
        return

    new_posts_count = 0

    for feed_url in RSS_FEEDS:
        print(f"\nПроверка: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                if not news_id or news_id in history: continue
                    
                title = clean_text(entry.title)
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if '�' in text_to_check or len(text_to_check) < 30: continue

                # Фильтрация по Черному и Белому спискам (за доли миллисекунд)
                if BLACKLIST_REGEX.search(text_to_check): 
                    continue
                
                if not KEYWORDS_REGEX.search(text_to_check): 
                    continue

                print(f"🔥 Новость: {title[:40]}...")
                
                category_header = detect_category(text_to_check)
                final_text = rewrite_text(f"{title}. {description}", token)
                
                if not final_text:
                    print("⏭️ GigaChat отказался или текст пуст.")
                    continue
                
                print("Генерация постера...")
                image_bytes = generate_image_gigachat(text_to_check, token)
                
                # Собираем финальный пост
                text_to_publish = category_header + final_text + f"\n\n🔗 <a href='{news_id}'>Источник</a>"
                
                if image_bytes:
                    success = send_photo(text_to_publish, image_bytes)
                else:
                    success = send_text(text_to_publish)
                
                if success:
                    print("✅ Опубликовано!")
                    history[news_id] = datetime.now().isoformat()
                    save_history(history)
                    new_posts_count += 1
                    time.sleep(4) # Пауза, чтобы не спамить Telegram
            except Exception as e:
                print(f"Ошибка при обработке: {e}")
                continue
                
            if new_posts_count >= 1: return

if __name__ == '__main__':
    main()
