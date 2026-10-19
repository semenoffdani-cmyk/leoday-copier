import os
import asyncio
import json
import uuid
import re
import requests
import urllib3
from telethon import TelegramClient
from telethon.sessions import StringSession

# Отключаем предупреждения о небезопасном соединении (нужно для GigaChat)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 НАСТРОЙКИ БЕЗОПАСНОСТИ (НЕ ТРОГАТЬ)
# =====================================================================
# Эти данные берутся из настроек GitHub (Secrets).
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
giga_client_id = os.environ.get('GIGACHAT_CLIENT_ID')
giga_client_secret = os.environ.get('GIGACHAT_CLIENT_SECRET')


# =====================================================================
# 👇👇👇 ШАГ 1: НАСТРОЙКА ИСТОЧНИКОВ (ГИБРИДНАЯ ЛОГИКА) 👇👇👇
# =====================================================================
# Инструкция:
# 1. В priority_channels (Приоритет) вписывайте НОВОСТНЫЕ каналы.
#    Скрипт будет проверять их в первую очередь. Если там есть новости, 
#    он опубликует их и НЕ БУДЕТ брать развлекательные посты в этом запуске.
#
# 2. В secondary_channels (Развлечения) вписывайте каналы с мемами.
#    Скрипт возьмет их ТОЛЬКО ЕСЛИ в новостных каналах не было ничего нового.
#
# ФОРМАТ: '@имя_канала'. Разделяйте запятой.
# =====================================================================

# Новостные каналы (идут первыми)
priority_channels = ['@topor', '@toporlive'] 

# Развлекательные каналы (идут как запасной вариант)
secondary_channels = ['@memachh']

# (Не менять) Объединяем списки, чтобы скрипт знал все источники
source_channels = priority_channels + secondary_channels
# =====================================================================


HISTORY_FILE = 'history.json'

# =====================================================================
# 👇👇👇 ШАГ 2: ОЧИСТКА ТЕКСТА (УДАЛЕНИЕ МУСОРА) 👇👇👇
# =====================================================================
def clean_universal(text):
    if not text:
        return text
    
    # 1. Удаляем все @упоминания (например, @futuread)
    text = re.sub(r'@\w+', '', text)
    
    # 2. Удаляем все HTTP/HTTPS ссылки
    text = re.sub(r'https?://\S+', '', text)
    
    # 3. Удаляем названия каналов-источников
    # Инструкция: Если вы добавили новый канал в ШАГ 1, 
    # обязательно впишите его название сюда, чтобы оно не появлялось в постах.
    channel_names = [
        r'Топор Live', 
        r'Топор', 
        r'Леодай', 
        r'Леонардо Дайвинчик', 
        r'МЕМАЧ', 
        r'memachh'
        # 👇 ВПИСЫВАТЬ НОВЫЕ НАЗВАНИЯ СЮДА
    ]
    for name in channel_names:
        text = re.sub(name + r'[^\n.!?]*[.!?]?', '', text, flags=re.IGNORECASE)
    
    # 4. Удаляем фразы, призывающие подписаться
    subscribe_patterns = [
        r'[Пп]одписаться[^\n]*', 
        r'[Пп]одписывайтесь[^\n]*',
        r'[Пп]ерейти в канал[^\n]*', 
        r'[Чч]итать далее[^\n]*', 
        r'[Ии]сточник[^\n]*'
    ]
    for pattern in subscribe_patterns:
        text = re.sub(pattern, '', text)
    
    # 5. Убираем лишние пустые строки
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    
    # Если после очистки осталось мало текста, возвращаем пустую строку
    if len(text) < 5:
        return "" 
    return text


# =====================================================================
# 👇👇👇 ШАГ 3: РАБОТА С GIGACHAT (РЕРАЙТ) 👇👇👇
# =====================================================================
def get_gigachat_token():
    if not giga_client_id or not giga_client_secret:
        return None
    try:
        import base64
        cid = giga_client_id.strip()
        csecret = giga_client_secret.strip()
        auth_str = f"{cid}:{csecret}"
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
        return None
    except Exception as e:
        print(f"Ошибка получения токена GigaChat: {e}")
        return None

def rewrite_text(text, token):
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # =====================================================================
        # ⚠️ ЕСЛИ ХОТИТЕ ИЗМЕНИТЬ СТИЛЬ КОММЕНТАРИЕВ, МЕНЯЙТЕ ТЕКСТ В ПУНКТЕ 2 ⚠️
        # =====================================================================
        prompt = (
            f"Ты — опытный редактор популярного Telegram-канала. Твоя задача — взять сырой текст и сделать из него качественный пост.\n"
            f"1. Перепиши текст своими словами, сохранив все факты и смысл, но убрав канцелярит.\n"
            f"2. Обязательно раздели переписанный текст и свой комментарий переносом строки (нажми Enter). Напиши короткий (1-2 предложения) живой комментарий от лица автора канала.\n"
            f"3. ВАЖНО: Не пиши вводных слов вроде 'Вот ваш текст:', не используй кавычки для всего текста и КАТЕГОРИЧЕСКИ НЕ ПИШИ слова 'пустая строка'.\n\n"
            f"Исходный текст:\n{text}"
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.85,
            "max_tokens": 600
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        result = response.json()
        
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            
            # Защита от отказов и "галлюцинаций" нейросети
            refusal_markers = [
                "Генеративные языковые модели", "не обладают собственным мнением",
                "чувствительным темам", "временно ограничены", "Благодарим за понимание",
                "хрупкость", "здравый смысл возобладает"
            ]
            
            if any(marker in rewritten for marker in refusal_markers) or len(rewritten) < 20:
                return None 

            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]
            if rewritten.startswith('«') and rewritten.endswith('»'):
                rewritten = rewritten[1:-1]
                
            return rewritten.strip()
        else:
            return text
    except Exception as e:
        print(f"Ошибка рерайта GigaChat: {e}")
        return text 


# =====================================================================
# 👇👇👇 ШАГ 4: ОСНОВНАЯ ЛОГИКА (НЕ ТРОГАТЬ) 👇👇👇
# =====================================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {str(k): v for k, v in data.items()}
        except Exception as e:
            return {}
    return {}

def save_history(history_dict):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")

async def process_message(msg, source_channel, client, copied_ids, target_texts, giga_token):
    """Вспомогательная функция для обработки одного поста"""
    text_to_check = (msg.text or "").lower()
    ad_keywords = ['реклама', 'erid', 'промокод', 'скидка', 'подписывайся', 'переходи по ссылке', 'интеграция', '@futuread', 'купить', 'заказать', 'цена', 'прайс']
    if any(word in text_to_check for word in ad_keywords):
        return

    if str(msg.id) in copied_ids:
        return
    
    try:
        final_text = msg.text or ""
        
        if final_text:
            final_text = clean_universal(final_text)
        
        if not final_text and not msg.media:
            return

        if final_text and giga_token:
            final_text = rewrite_text(final_text, giga_token)
        
        if final_text is None and msg.media:
            final_text = ""
        
        if final_text is None and not msg.media:
            return

        if final_text and any(final_text[:50] in t for t in target_texts):
            print(f"Пост {msg.id} пропущен (такой текст уже есть в канале).")
            return

        if msg.media:
            file_path = await msg.download_media(file="/tmp/")
            if file_path:
                await client.send_file(
                    target_channel, 
                    file_path, 
                    caption=final_text if final_text else None
                )
                os.remove(file_path)
                print(f"Скопировано медиа (пост {msg.id} из {source_channel})")
        elif final_text:
            await client.send_message(target_channel, final_text)
            print(f"Скопирован текст (пост {msg.id} из {source_channel})")
        
        copied_ids[str(msg.id)] = source_channel
        save_history(copied_ids)
        await asyncio.sleep(3)
        
    except Exception as e:
        print(f"Ошибка при копировании поста {msg.id}: {e}")

async def main():
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} записей из истории.")

    giga_token = get_gigachat_token()
    if giga_token:
        print("Токен GigaChat получен.")
    else:
        print("ВНИМАНИЕ: Токен GigaChat не получен.")

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        target_messages = await client.get_messages(target_channel, limit=20)
        target_texts = [m.text[:50] for m in target_messages if m.text]
        
        # --- ГИБРИДНАЯ ЛОГИКА ---
        # 1. СНАЧАЛА ПРОВЕРЯЕМ НОВОСТИ (ПРИОРИТЕТ)
        news_found = False
        print("\n--- Проверка приоритетных каналов (Новости) ---")
        for source_channel in priority_channels:
            print(f"Смотрим: {source_channel}")
            messages = await client.get_messages(source_channel, limit=3)
            
            for msg in reversed(messages):
                if str(msg.id) in copied_ids:
                    continue
                
                # Если нашли новый пост, обрабатываем и ставим флаг
                await process_message(msg, source_channel, client, copied_ids, target_texts, giga_token)
                news_found = True
        
        # 2. ЕСЛИ НОВОСТЕЙ НЕТ, БЕРЕМ РАЗВЛЕКАТЕЛЬНЫЙ КОНТЕНТ
        if not news_found:
            print("\n--- Новостей нет. Проверяем развлекательные каналы ---")
            for source_channel in secondary_channels:
                print(f"Смотрим: {source_channel}")
                messages = await client.get_messages(source_channel, limit=3)
                
                for msg in reversed(messages):
                    await process_message(msg, source_channel, client, copied_ids, target_texts, giga_token)
        # ------------------------

asyncio.run(main())
