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
        
        # Получаем последние 3 сообщения из исходного канала
        messages = await client.get_messages(source_channel, limit=3)
        
        for msg in reversed(messages):
            try:
                # Отправляем сообщение, используя параметр copy=True
                # Это скопирует контент без метки "Переслано"
                await client.send_message(target_channel, msg, copy=True)
                print(f"Успешно скопирован пост ID: {msg.id} (без метки 'Переслано')")
                
                # Пауза, чтобы Telegram не расценил это как спам
                await asyncio.sleep(3) 
            except Exception as e:
                print(f"Ошибка при копировании поста {msg.id}: {e}")

asyncio.run(main())
