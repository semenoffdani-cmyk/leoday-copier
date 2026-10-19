import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
source_channel = '@leoday'

async def main():
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        # Получаем 3 последних поста
        messages = await client.get_messages(source_channel, limit=3)
        
        for msg in reversed(messages):
            if msg.text:
                try:
                    await client.send_message(target_channel, msg.text)
                    print(f"Скопирован пост ID: {msg.id}")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"Ошибка: {e}")

asyncio.run(main())
