import os
import asyncio
import json
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']

HISTORY_FILE = 'history.json'

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history_dict):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_dict, f, ensure_ascii=False, indent=2)

async def main():
    # Загружаем историю
    history = load_history()
    
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Подключение к каналу...")
        
        # Получаем последние 200 сообщений из ВАШЕГО канала
        messages = await client.get_messages(target_channel, limit=200)
        
        seen_texts = {} 
        deleted_count = 0
        history_changed = False

        # Проходим по сообщениям от старых к новым
        for msg in reversed(messages):
            text = msg.text
            if not text or len(text) < 20:
                continue
            
            if text in seen_texts:
                old_msg_id = seen_texts[text]
                try:
                    # Удаляем старый дубль из канала
                    await client.delete_messages(target_channel, old_msg_id)
                    print(f"Удален дубль (старый ID: {old_msg_id}, оставлен новый ID: {msg.id})")
                    deleted_count += 1
                    
                    # Удаляем ID старого дубля из истории
                    if str(old_msg_id) in history:
                        del history[str(old_msg_id)]
                        history_changed = True
                        
                    await asyncio.sleep(1) 
                except Exception as e:
                    print(f"Ошибка при удалении {old_msg_id}: {e}")
            
            seen_texts[text] = msg.id

        # Сохраняем обновленную историю, если были изменения
        if history_changed:
            save_history(history)
            print("История обновлена (удалены записи о дублях).")

        print(f"\nОчистка завершена. Удалено дублей: {deleted_count}")

asyncio.run(main())
