import os
import asyncio
import json
import uuid
import re
import requests
import urllib3
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# Отключаем предупреждения о небезопасном соединении (нужно для GigaChat)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 НАСТРОЙКИ БЕЗОПАСНОСТИ (НЕ ТРОГАТЬ)
# =====================================================================
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
giga_client_id = os.environ.get('GIGACHAT_CLIENT_ID')
giga_client_secret = os.environ.get('GIGACHAT_CLIENT_SECRET')


# =====================================================================
# 👇👇👇 ШАГ 1: ИСТОЧНИКИ (ССЫЛКИ ПРОВЕРЕНЫ) 👇👇👇
# =====================================================================
priority_channels = ['@rian_ru', '@prime1', '@centralbank_russia'] 
secondary_channels = [] 

source_channels = priority_channels + secondary_channels
# =====================================================================


HISTORY_FILE = 'history.json'

# =====================================================================
# 👇👇👇 ШАГ 2: ОЧИСТКА ТЕКСТА 👇👇👇
# =====================================================================
def clean_universal(text):
    if not text:
        return text
    
    # 1. Удаляем HTML-теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. Удаляем скрытые ссылки Telegram [текст](ссылка), оставляя только текст
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 3. Удаляем оставшиеся @упоминания и обычные ссылки
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    
    # 4. Удаляем одинокие скобки и спецсимволы
    text = text.replace('[', '').replace(']', '')
    
    # 5. Удаляем названия каналов
    channel_names = [
        'РИА Новости', 'rian_ru',
        'ПРАЙМ', 'prime1',
        'Банк России', 'centralbank_russia'
    ]
    for name in channel_names:
        safe_name = re.escape(name)
        text = re.sub(r'\b' + safe_name + r'\b[:,]?\s*', '', text, flags=re.IGNORECASE)
    
    # 6. Удаляем призывы к подписке
    subscribe_patterns = [
        r'[Пп]одписаться[^\n]*', r'[Пп]одписывайтесь[^\n]*',
        r'[Пп]ерейти в канал[^\n]*', r'[Чч]итать далее[^\n]*', r'[Ии]сточник[^\n]*',
        r'[Пп]одробнее[^\n]*'
    ]
    for pattern in subscribe_patterns:
        text = re.sub(pattern, '', text)
    
    # 7. Убираем лишние пустые строки (оставляем максимум одну пустую строку между абзацами)
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    
    # 8. УДАЛЯЕМ ПРОБЕЛЫ В НАЧАЛЕ КАЖДОЙ СТРОКИ (решает проблему отступа слева)
    text = re.sub(r'(?m)^\s+', '', text)
    
    # 9. Проверка на осмысленный текст (должно быть больше 10 символов и хотя бы одна буква)
    if len(text) < 10 or not re.search(r'[а-яА-Яa-zA-Z]', text):
        return "" 
    return text


# =====================================================================
# 👇👇👇 ШАГ 3: НЕЙРОСЕТЬ (ФИНАНСОВЫЙ АНАЛИЗ) 👇👇👇
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
        
        prompt = (
            f"Ты — профессиональный финансовый редактор. Твоя задача — сделать из этого текста красивый и понятный пост. "
            f"1. Исправь грамматические ошибки и обрывы текста, если они есть в оригинале. "
            f"2. Перескажи суть новости простым языком (2-3 предложения). "
            f"3. Если в тексте есть сложные финансовые термины, кратко объясни их. "
            f"4. Не используй никакую разметку: никаких звездочек (**), квадратных скобок ([]) и ссылок. "
            f"Верни только готовый текст:\n\n{text}"
        )
        
        payload = {
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3, 
            "max_tokens": 700   
        }
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        result = response.json()
        
        if 'choices' in result:
            rewritten = result['choices'][0]['message']['content'].strip()
            
            refusal_markers = [
                "Генеративные языковые модели", "не обладают собственным мнением",
                "чувствительным темам", "временно ограничены", "Благодарим за понимание"
            ]
            
            if any(marker in rewritten for marker in refusal_markers) or len(rewritten) < 15:
                return None 

            # Финальная зачистка от случайных символов
            rewritten = re.sub(r'[*_`#]', '', rewritten)
            rewritten = rewritten.replace('[', '').replace(']', '')
            
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
# 👇👇👇 ШАГ 4: ОСНОВНАЯ ЛОГИКА (МАКСИМАЛЬНАЯ ЗАЩИТА) 👇👇👇
# =====================================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if len(data) > 5000:
                    data = dict(list(data.items())[-5000:])
                return {str(k): v for k, v in data.items()}
        except Exception:
            return {}
    return {}

def save_history(history_dict):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")

async def process_message(msg, source_channel, client, copied_ids, target_texts, giga_token):
    history_key = f"{source_channel.replace('@', '')}_{msg.id}"
    
    if history_key in copied_ids:
        return False

    text_to_check = (msg.text or "").lower()
    ad_keywords = ['реклама', 'erid', 'промокод', 'скидка', 'подписывайся', 'переходи по ссылке', 'интеграция', 'купить', 'заказать', 'цена', 'прайс']
    if any(word in text_to_check for word in ad_keywords):
        return False
    
    try:
        final_text = msg.text or ""
        
        # Очищаем текст
        if final_text:
            final_text = clean_universal(final_text)
        
        # Если текста нет (или он мусорный) — ПРОПУСКАЕМ пост (защита от картинок Vinted)
        if not final_text:
            print(f"Пост {msg.id} пропущен (нет осмысленного текста).")
            return False

        # Отправляем в GigaChat
        if giga_token:
            final_text = rewrite_text(final_text, giga_token)
        
        # Если нейросеть отказалась — пропускаем
        if final_text is None:
            return False

        # Проверка на дубли в целевом канале
        if any(final_text[:50] in t for t in target_texts):
            print(f"Пост {msg.id} пропущен (такой текст уже есть в канале).")
            return False

        # ЗАЩИТА ОТ СЛИШКОМ ДЛИННЫХ ТЕКСТОВ
        if len(final_text) > 4000:
            final_text = final_text[:4000] + "..."

        posted = False
        
        # Отправка (мы точно знаем, что текст есть)
        if msg.media:
            try:
                file_path = await msg.download_media(file="/tmp/")
                if file_path:
                    # Защита от лимита Telegram (1024 символа)
                    if len(final_text) > 1024:
                        await client.send_file(target_channel, file_path)
                        await client.send_message(target_channel, final_text)
                    else:
                        await client.send_file(
                            target_channel, 
                            file_path, 
                            caption=final_text
                        )
                    os.remove(file_path)
                    print(f"Скопировано медиа с текстом (пост {msg.id} из {source_channel})")
                    posted = True
            except FloodWaitError as e:
                print(f"Telegram просит подождать {e.seconds} секунд. Ждем...")
                await asyncio.sleep(e.seconds)
            except Exception as media_err:
                print(f"Ошибка скачивания/отправки медиа {msg.id}: {media_err}")
                
        else:
            try:
                await client.send_message(target_channel, final_text)
                print(f"Скопирован текст (пост {msg.id} из {source_channel})")
                posted = True
            except FloodWaitError as e:
                print(f"Telegram просит подождать {e.seconds} секунд. Ждем...")
                await asyncio.sleep(e.seconds)

        if posted:
            copied_ids[history_key] = source_channel
            save_history(copied_ids)
            await asyncio.sleep(3)
            return True
        return False
        
    except Exception as e:
        print(f"Ошибка при обработке поста {msg.id}: {e}")
        return False

async def main():
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} записей из истории.")

    giga_token = get_gigachat_token()
    if giga_token:
        print("Токен GigaChat получен.")
    else:
        print("ВНИМАНИЕ: Токен GigaChat не получен. Будет использоваться оригинальный текст.")

    try:
        async with TelegramClient(StringSession(session), api_id, api_hash) as client:
            print("Успешный вход в аккаунт.")
            
            target_messages = await client.get_messages(target_channel, limit=20)
            target_texts = [m.text[:50] for m in target_messages if m.text]
            
            news_found = False
            print("\n--- Проверка приоритетных каналов ---")
            for source_channel in priority_channels:
                print(f"Смотрим: {source_channel}")
                try:
                    messages = await client.get_messages(source_channel, limit=3)
                except Exception as e:
                    print(f"Не удалось получить сообщения из {source_channel}: {e}")
                    continue
                
                for msg in reversed(messages):
                    if await process_message(msg, source_channel, client, copied_ids, target_texts, giga_token):
                        news_found = True
            
            if not news_found and secondary_channels:
                print("\n--- Новостей нет. Проверяем дополнительные каналы ---")
                for source_channel in secondary_channels:
                    print(f"Смотрим: {source_channel}")
                    try:
                        messages = await client.get_messages(source_channel, limit=3)
                    except Exception as e:
                        print(f"Не удалось получить сообщения из {source_channel}: {e}")
                        continue
                    
                    for msg in reversed(messages):
                        await process_message(msg, source_channel, client, copied_ids, target_texts, giga_token)
    except Exception as global_err:
        print(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ РАБОТЕ С TELEGRAM: {global_err}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Глобальный сбой скрипта: {e}")
