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

# --- НАСТРОЙКИ БЕЗОПАСНОСТИ (НЕ ТРОГАТЬ) ---
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
giga_client_id = os.environ.get('GIGACHAT_CLIENT_ID')
giga_client_secret = os.environ.get('GIGACHAT_CLIENT_SECRET')


# =====================================================================
# 👇👇👇 ШАГ 1: ОТКУДА БРАТЬ ПОСТЫ (ИСТОЧНИКИ) 👇👇👇
# =====================================================================
# Инструкция: 
# Сюда вписывайте юзернеймы каналов, из которых хотите копировать новости.
# Формат: '@имя_канала'. Если каналов несколько, разделяйте их запятой.
# 
# Пример 1 (один канал): source_channels = ['@topor']
# Пример 2 (два канала): source_channels = ['@topor', '@toporlive']
# 
# ВАЖНО: Ваш аккаунт Telegram должен быть подписан на все эти каналы!
# =====================================================================
source_channels = ['@topor', '@toporlive'] 
# =====================================================================


HISTORY_FILE = 'history.json'

# =====================================================================
# 👇👇👇 ШАГ 2: ЧТО УДАЛЯТЬ ИЗ ТЕКСТА (ЧИСТКА) 👇👇👇
# =====================================================================
def clean_universal(text):
    if not text:
        return text
    
    # 1. Удаляем все @упоминания
    text = re.sub(r'@\w+', '', text)
    
    # 2. Удаляем все HTTP/HTTPS ссылки
    text = re.sub(r'https?://\S+', '', text)
    
    # 3. Удаляем названия каналов-источников
    # Инструкция: добавляйте сюда названия каналов, которые НЕ ДОЛЖНЫ появляться в посте.
    channel_names = [
        r'Топор Live', 
        r'Топор', 
        r'Леодай', 
        r'Леонардо Дайвинчик'
        # 👇 ВПИСЫВАТЬ НОВЫЕ НАЗВАНИЯ СЮДА, например: r'Новый Канал'
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
    
    if len(text) < 5:
        return None
        
    return text


# =====================================================================
# 👇👇👇 ШАГ 3: КАК ПЕРЕПИСЫВАТЬ ТЕКСТ (НЕЙРОСЕТЬ) 👇👇👇
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
        # ⚠️ ВОТ ЗДЕСЬ МЕНЯЕТСЯ СТИЛЬ КОММЕНТАРИЕВ ⚠️
        # =====================================================================
        # Если хотите изменить стиль комментария, просто отредактируйте текст 
        # в пункте "2." внутри переменной prompt ниже.
        # Например, замените "живой" на "ироничный" или "сдержанный".
        # =====================================================================
        prompt = (
            f"Ты — опытный редактор популярного новостного Telegram-канала. Твоя задача — взять сырой текст новости и сделать из него качественный, цепляющий пост.\n"
            f"1. Перепиши текст своими словами, сохранив все факты и смысл, но убрав канцелярит.\n"
            f"2. В конце добавь пустую строку и напиши короткий (1-2 предложения) живой комментарий от лица автора канала.\n"
            f"3. ВАЖНО: Верни только готовый текст. Не пиши вводных слов и не используй кавычки для всего текста.\n\n"
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
            
            refusal_markers = [
                "Генеративные языковые модели", 
                "не обладают собственным мнением",
                "чувствительным темам",
                "временно ограничены",
                "Благодарим за понимание",
                "хрупкость", 
                "здравый смысл возобладает"
            ]
            
            if any(marker in rewritten for marker in refusal_markers) or len(rewritten) < 20:
                print(f"GigaChat выдал странный ответ или отказ. Пропускаем.")
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
            print(f"Ошибка чтения истории: {e}")
            return {}
    return {}

def save_history(history_dict):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")

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
        
        for source_channel in source_channels:
            print(f"\n--- Проверка канала: {source_channel} ---")
            messages = await client.get_messages(source_channel, limit=5)
            
            for msg in reversed(messages):
                text_to_check = (msg.text or "").lower()
                ad_keywords = ['реклама', 'erid', 'промокод', 'скидка', 'подписывайся', 'переходи по ссылке', 'интеграция', '@futuread', 'купить', 'заказать', 'цена', 'прайс']
                if any(word in text_to_check for word in ad_keywords):
                    continue

                if str(msg.id) in copied_ids:
                    continue
                
                try:
                    final_text = msg.text or ""
                    
                    if final_text:
                        final_text = clean_universal(final_text)
                    
                    if final_text is None:
                         continue

                    if final_text and giga_token:
                        final_text = rewrite_text(final_text, giga_token)
                    
                    if giga_token and final_text is None:
                        continue

                    if any(final_text[:50] in t for t in target_texts):
                        print(f"Пост {msg.id} пропущен (такой текст уже есть в канале).")
                        continue

                    if msg.media:
                        file_path = await msg.download_media(file="/tmp/")
                        if file_path:
                            await client.send_file(
                                target_channel, 
                                file_path, 
                                caption=final_text
                            )
                            os.remove(file_path)
                            print(f"Скопировано медиа (пост {msg.id})")
                    elif final_text:
                        await client.send_message(target_channel, final_text)
                        print(f"Скопирован текст (пост {msg.id})")
                    
                    copied_ids[str(msg.id)] = source_channel
                    save_history(copied_ids)
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"Ошибка при копировании поста {msg.id}: {e}")

asyncio.run(main())
