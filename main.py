import os
import asyncio
import json
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']

# =====================================================================
# СПИСОК КАНАЛОВ-ИСТОЧНИКОВ
# =====================================================================
# Сейчас здесь только @leoday.
# Чтобы добавить новый канал, допишите его через запятую в квадратных скобках.
# Например: source_channels = ['@leoday', '@Топор18', '@new_channel']
# ВАЖНО: ваш аккаунт Telegram должен быть подписан на все эти каналы!
# =====================================================================
source_channels = ['@leoday'] 
# =====================================================================

HISTORY_FILE = 'history.json'

def load_history():
    """Загружает историю скопированных постов"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_history(history_dict):
    """Сохраняет историю в файл"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_dict, f, ensure_ascii=False, indent=2)

async def main():
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} записей из истории.")

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        # Проходим по каждому каналу из списка
        for source_channel in source_channels:
            print(f"\n--- Проверка канала: {source_channel} ---")
            
            # Получаем последние 5 сообщений
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
                # --- КОНЕЦ ФИЛЬТРА ---

                # Проверка на дубли
                if msg.id in copied_ids:
                    print(f"Пост {msg.id} уже есть в истории. Пропускаем.")
                    continue
                
                try:
                    if msg.media:
                        file_path = await msg.download_media(file="/tmp/")
                        if file_path:
                            await client.send_file(target_channel, file_path, caption=msg.text or "")
                            os.remove(file_path)
                            print(f"Скопировано медиа (пост {msg.id} из {source_channel})")
                    elif msg.text:
                        await client.send_message(target_channel, msg.text)
                        print(f"Скопирован текст (пост {msg.id} из {source_channel})")
                    
                    # Записываем ID поста в историю
                    copied_ids[msg.id] = source_channel
                    save_history(copied_ids)
                    
                    await asyncio.sleep(3) # Пауза между отправками
                    
                except Exception as e:
                    print(f"Ошибка при копировании поста {msg.id} из {source_channel}: {e}")

asyncio.run(main())
