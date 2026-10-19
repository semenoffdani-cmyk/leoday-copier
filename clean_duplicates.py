import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']

async def main():
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Подключение к каналу для очистки дублей...")
        
        messages = await client.get_messages(target_channel, limit=200)
        
        seen_texts = {} 
        deleted_count = 0

        for msg in reversed(messages):
            text = msg.text
            if not text or len(text) < 20:
                continue
            
            if text in seen_texts:
                old_msg_id = seen_texts[text]
                try:
                    await client.delete_messages(target_channel, old_msg_id)
                    print(f"Удален дубль (старый ID: {old_msg_id}, оставлен новый ID: {msg.id})")
                    deleted_count += 1
                    await asyncio.sleep(1) 
                except Exception as e:
                    print(f"Ошибка при удалении {old_msg_id}: {e}")
            
            seen_texts[text] = msg.id

        print(f"\nОчистка завершена. Удалено дублей: {deleted_count}")

asyncio.run(main())
