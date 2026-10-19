import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session = os.environ['SESSION']
target_channel = os.environ['TARGET_CHANNEL']
source_channel = '@leoday'

async def main():
    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        print("Успешный вход в аккаунт.")
        
        # Получаем последние 3 сообщения
        messages = await client.get_messages(source_channel, limit=3)
        
        for msg in reversed(messages):
            try:
                # Если в сообщении есть медиа (видео, фото, документ)
                if msg.media:
                    # Скачиваем файл во временную папку на сервере GitHub
                    file_path = await msg.download_media(file="/tmp/")
                    if file_path:
                        # Отправляем скачанный файл в ваш канал
                        await client.send_file(
                            target_channel, 
                            file_path, 
                            caption=msg.text if msg.text else ""
                        )
                        print(f"Успешно скопировано медиа из поста ID: {msg.id}")
                        # Удаляем временный файл, чтобы не забивать память
                        os.remove(file_path)
                    else:
                        print(f"Не удалось скачать медиа из поста {msg.id}")
                
                # Если медиа нет, но есть текст — копируем просто текст
                elif msg.text:
                    await client.send_message(target_channel, msg.text)
                    print(f"Успешно скопирован текст поста ID: {msg.id}")
                
                # Пауза, чтобы Telegram не заблокировал за спам
                await asyncio.sleep(3)
                
            except Exception as e:
                print(f"Ошибка при копировании поста {msg.id}: {e}")

asyncio.run(main())
