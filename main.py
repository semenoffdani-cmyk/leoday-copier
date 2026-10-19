import os
import asyncio
import json
import uuid
import re
import requests
import urllib3
from telethon import TelegramClient
from telethon.sessions import StringSession

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']

giga_client_id = os.environ.get('GIGACHAT_CLIENT_ID')
giga_client_secret = os.environ.get('GIGACHAT_CLIENT_SECRET')

# =====================================================================
# ⬇️⬇️⬇️ ВСТАВЛЯТЬ НАЗВАНИЯ КАНАЛОВ СЮДА ⬇️⬇️⬇️
source_channels = ['@leoday', '@toporlive'] 
# ⬆️⬆️⬆️ ВСТАВЛЯТЬ НАЗВАНИЯ КАНАЛОВ СЮДА ⬆️⬆️⬆️
# =====================================================================

HISTORY_FILE = 'history.json'

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

def get_gigachat_token():
    if not giga_client_id or not giga_client_secret:
        print("Ошибка: не заданы GIGACHAT_CLIENT_ID или GIGACHAT_CLIENT_SECRET")
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
        else:
            print(f"Ошибка авторизации GigaChat. Статус: {response.status_code}")
            return None
    except Exception as e:
        print(f"Ошибка получения токена GigaChat: {e}")
        return None

def rewrite_text(text, token):
    """Переписывает текст и добавляет комментарий автора"""
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # --- НОВЫЙ ПРОМПТ (сдержанный, но живой) ---
        prompt = (
            f"Ты — опытный редактор популярного новостного Telegram-канала. Твоя задача — взять сырой текст новости и сделать из него качественный, цепляющий пост.\n"
            f"1. Перепиши текст своими словами (сделай рерайт), сохранив все факты и смысл, но убрав канцелярит. Сделай текст коротким и удобным для чтения.\n"
            f"2. В конце добавь пустую строку и напиши короткий (1-2 предложения) комментарий от лица автора канала. Комментарий должен быть сдержанным, но живым — как мнение умного человека, который наблюдает за ситуацией (с легкой долей иронии, если это уместно по контексту, но без злого сарказма и пошлости).\n"
            f"3. ВАЖНО: Верни только готовый текст. Не пиши вводных слов вроде 'Вот ваш текст:', не используй кавычки для всего текста.\n\n"
            f"Исходный текст:\n{text}"
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.85, # Чуть повысили температуру для креативности
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
                "Благодарим за понимание"
            ]
            
            if any(marker in rewritten for marker in refusal_markers):
                print(f"GigaChat отказался переписывать пост. Пропускаем.")
                return None 

            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]
            return rewritten
        else:
            return text
    except Exception as e:
        print(f"Ошибка рерайта GigaChat: {e}")
        return text 

def clean_universal(text):
    """Универсальная очистка от всех ссылок и упоминаний"""
    if not text:
        return text
    
    # 1. Удаляем все @упоминания
    text = re.sub(r'@\w+', '', text)
    
    # 2. Удаляем все HTTP/HTTPS ссылки
    text = re.sub(r'https?://\S+', '', text)
    
    # 3. Удаляем фразы, призывающие подписаться
    subscribe_patterns = [
        r'[Пп]одписаться[^\n]*', 
        r'[Пп]одписывайтесь[^\n]*',
        r'[Пп]ерейти в канал[^\n]*',
        r'[Чч]итать далее[^\n]*',
        r'[Ии]сточник[^\n]*'
    ]
    for pattern in subscribe_patterns:
        text = re.sub(pattern, '', text)
    
    # 4. Убираем лишние пустые строки
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    
    # 5. Если осталось слишком мало текста, возвращаем None
    if len(text) < 5:
        return None
        
    return text

async def main():
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} записей из истории.")

    giga_token = get_gigachat_token()
    if giga_token:
        print("Токен GigaChat получен. Рерайт включен.")
    else:
        print("ВНИМАНИЕ: Токен GigaChat не получен.")

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        for source_channel in source_channels:
            print(f"\n--- Проверка канала: {source_channel} ---")
            messages = await client.get_messages(source_channel, limit=5)
            
            for msg in reversed(messages):
                
                # --- ФИЛЬТР РЕКЛАМЫ ---
                text_to_check = (msg.text or "").lower()
                ad_keywords = [
                    'реклама', 'erid', 'промокод', 'скидка', 
                    'подписывайся', 'переходи по ссылке', 'интеграция',
                    '@futuread', 'купить', 'заказать', 'цена', 'прайс'
                ]
                if any(word in text_to_check for word in ad_keywords):
                    print(f"Пропущен рекламный пост {msg.id}")
                    continue

                if str(msg.id) in copied_ids:
                    print(f"Пост {msg.id} уже есть в истории. Пропускаем.")
                    continue
                
                try:
                    final_text = msg.text or ""
                    
                    # 1. Сначала ОЧИЩАЕМ текст от ссылок (чтобы GigaChat их не видел)
                    if final_text:
                        final_text = clean_universal(final_text)
                    
                    # Если после очистки ничего не осталось — пропускаем
                    if final_text is None:
                         print(f"Пост {msg.id} пропущен (в оригинале были только ссылки).")
                         continue

                    # 2. Теперь ОТПРАВЛЯЕМ чистый текст в GigaChat
                    if final_text and giga_token:
                        print(f"Переписываем текст поста {msg.id}...")
                        final_text = rewrite_text(final_text, giga_token)
                    
                    # Если фильтр GigaChat сработал
                    if giga_token and final_text is None:
                        print(f"Пост {msg.id} пропущен (фильтр GigaChat).")
                        continue

                    # 3. Отправляем
                                       if msg.media:
                        # Скачиваем само видео/фото
                        file_path = await msg.download_media(file="/tmp/")
                        if file_path:
                            # Пытаемся скачать превью (обложку), если оно есть
                            thumb_path = None
                            if hasattr(msg.media, 'photo') and msg.media.photo:
                                # Если это фото внутри сообщения с текстом
                                thumb_path = await client.download_media(msg.media.photo, file="/tmp/thumb_")
                            elif hasattr(msg.media, 'document') and msg.media.document:
                                # Если это видео или документ
                                # Ищем миниатюру в атрибутах документа
                                for attr in msg.media.document.attributes:
                                    if hasattr(attr, 'thumb') and attr.thumb:
                                        thumb_path = await client.download_media(attr.thumb, file="/tmp/thumb_")
                                        break
                            
                            # Отправляем с превью (если оно скачалось)
                            await client.send_file(
                                target_channel, 
                                file_path, 
                                caption=final_text,
                                thumb=thumb_path
                            )
                            
                            # Чистим временные файлы
                            os.remove(file_path)
                            if thumb_path and os.path.exists(thumb_path):
                                os.remove(thumb_path)
                                
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
