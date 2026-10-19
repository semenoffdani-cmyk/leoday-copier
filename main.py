import os
import asyncio
import json
import uuid
import requests
import urllib3
from telethon import TelegramClient
from telethon.sessions import StringSession

# Отключаем предупреждения о небезопасном соединении (для GigaChat)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']

# Данные для GigaChat
giga_client_id = os.environ.get('GIGACHAT_CLIENT_ID')
giga_client_secret = os.environ.get('GIGACHAT_CLIENT_SECRET')

# =====================================================================
# ⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️
# 👇👇👇 ВОТ СЮДА ВСТАВЛЯТЬ НАЗВАНИЕ ВТОРОГО КАНАЛА 👇👇👇
#
# Чтобы добавить второй канал, напишите его юзернейм через запятую.
# ПРИМЕР: source_channels = ['@leoday', '@topor']
# ВАЖНО: не забудьте про кавычки и символ @ !
#
source_channels = ['@leoday', '@topor'] 
#
# 👆👆👆 ВОТ СЮДА ВСТАВЛЯТЬ НАЗВАНИЕ ВТОРОГО КАНАЛА 👆👆👆
# ⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️
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
    """Получает токен доступа для GigaChat"""
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
        
        # Если вы используете прокси, добавьте его сюда: proxies=proxies
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
    """Отправляет текст в GigaChat для переписывания"""
    if not token or not text:
        return text
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        prompt = f"Перепиши этот текст другими словами, сохрани смысл, сделай его живым и коротким. Верни только готовый текст без лишних комментариев:\n\n{text}"
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 500
        }
        
        # Если вы используете прокси, добавьте его сюда: proxies=proxies
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        result = response.json()
        
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            
            # --- УМНАЯ ПРОВЕРКА НА ЛЮБОЙ ОТКАЗ GIGACHAT ---
            refusal_markers = [
                "Генеративные языковые модели", 
                "не обладают собственным мнением",
                "чувствительным темам",
                "временно ограничены",
                "Благодарим за понимание"
            ]
            
            if any(marker in rewritten for marker in refusal_markers):
                print(f"GigaChat отказался переписывать пост (сработал фильтр). Пост будет пропущен.")
                return None 
            # -----------------------------------------------

            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]
            return rewritten
        else:
            print(f"Неожиданный ответ от GigaChat: {result}")
            return text
            
    except Exception as e:
        print(f"Ошибка рерайта GigaChat: {e}")
        return text 

async def main():
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} записей из истории.")

    giga_token = get_gigachat_token()
    if giga_token:
        print("Токен GigaChat получен. Рерайт включен.")
    else:
        print("ВНИМАНИЕ: Токен GigaChat не получен. Будет публиковаться оригинальный текст.")

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
                    print(f"Пропущен рекламный пост {msg.id} (найдено стоп-слово)")
                    continue

                # Проверка на дубли
                if str(msg.id) in copied_ids:
                    print(f"Пост {msg.id} уже есть в истории. Пропускаем.")
                    continue
                
                try:
                    final_text = msg.text or ""
                    if final_text and giga_token:
                        print(f"Переписываем текст поста {msg.id}...")
                        final_text = rewrite_text(final_text, giga_token)
                    
                    # --- ПРОВЕРКА: ЕСЛИ РЕРАЙТ НЕ УДАЛСЯ (ФИЛЬТР), ПРОПУСКАЕМ ПОСТ ---
                    if giga_token and final_text is None:
                        print(f"Пост {msg.id} пропущен из-за фильтра GigaChat.")
                        continue
                    # -------------------------------------------------------------------

                    if msg.media:
                        file_path = await msg.download_media(file="/tmp/")
                        if file_path:
                            await client.send_file(target_channel, file_path, caption=final_text)
                            os.remove(file_path)
                            print(f"Скопировано медиа (пост {msg.id} из {source_channel})")
                    elif final_text:
                        await client.send_message(target_channel, final_text)
                        print(f"Скопирован текст (пост {msg.id} из {source_channel})")
                    
                    copied_ids[str(msg.id)] = source_channel
                    save_history(copied_ids)
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"Ошибка при копировании поста {msg.id} из {source_channel}: {e}")

asyncio.run(main())
