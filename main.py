import os
import asyncio
import json
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
source_channel = '@leoday'
HISTORY_FILE = 'history.json'

def load_history():
    """Загружает список ID скопированных постов из файла"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history(history_list):
    """Сохраняет обновленный список ID в файл"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_list, f, ensure_ascii=False, indent=2)

async def main():
    # Загружаем историю в начале
    copied_ids = load_history()
    print(f"Загружено {len(copied_ids)} ID из истории.")

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        # Получаем последние 5 сообщений из источника (чуть больше для надежности)
        messages = await client.get_messages(source_channel, limit=5)
        
        for msg in reversed(messages):
            # Пропускаем, если пост уже был скопирован (дубль)
            if msg.id in copied_ids:
                print(f"Пост {msg.id} уже есть в истории. Пропускаем.")
                continue
            
            try:
                if msg.media:
                    # Скачиваем во временную папку
                    file_path = await msg.download_media(file="/tmp/")
                    if file_path:
                        await client.send_file(
                            target_channel, 
                            file_path, 
                            caption=msg.text or ""
                        )
                        os.remove(file_path)
                        print(f"Скопировано медиа (пост {msg.id})")
                elif msg.text:
                    await client.send_message(target_channel, msg.text)
                    print(f"Скопирован текст (пост {msg.id})")
                
                # Добавляем ID в список успешно скопированных и сохраняем
                copied_ids.append(msg.id)
                save_history(copied_ids)
                
                # Пауза, чтобы не было спам-бана
                await asyncio.sleep(3)
                
            except Exception as e:
                print(f"Ошибка при копировании поста {msg.id}: {e}")

asyncio.run(main())
