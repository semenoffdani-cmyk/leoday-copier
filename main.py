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
        
        # Перебираем их от старых к новым
        for msg in reversed(messages):
            try:
                # Пересылаем сообщение целиком (текст, видео, картинки)
                # Если вы хотите, чтобы не было надписи "Переслано из @leoday", 
                # замените forward_messages на send_message с параметром copy
                await client.forward_messages(target_channel, msg)
                print(f"Успешно скопирован пост ID: {msg.id}")
                await asyncio.sleep(3) # Пауза 3 секунды, чтобы Telegram не блокировал за спам
            except Exception as e:
                print(f"Ошибка при копировании поста {msg.id}: {e}")

asyncio.run(main())
