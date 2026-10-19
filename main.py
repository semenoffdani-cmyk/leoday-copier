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
        
        # 1. Получаем последние 3 поста из ИСТОЧНИКА
        source_messages = await client.get_messages(source_channel, limit=3)
        
        # 2. Получаем последние 50 постов из ВАШЕГО канала для сверки
        target_messages = await client.get_messages(target_channel, limit=50)
        
        # --- ЧАСТЬ 1: Копирование новых постов ---
        for msg in reversed(source_messages):
            # Проверяем, есть ли уже этот текст в вашем канале (простая проверка по первым 50 символам)
            is_copied = any(
                t_msg.text and msg.text and t_msg.text[:50] == msg.text[:50] 
                for t_msg in target_messages
            )
            
            if is_copied:
                continue # Пропускаем, если уже скопировали
            
            try:
                if msg.media:
                    file_path = await msg.download_media(file="/tmp/")
                    if file_path:
                        await client.send_file(target_channel, file_path, caption=msg.text or "")
                        os.remove(file_path)
                        print(f"Скопировано медиа: {msg.id}")
                elif msg.text:
                    await client.send_message(target_channel, msg.text)
                    print(f"Скопирован текст: {msg.id}")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"Ошибка при копировании {msg.id}: {e}")

        # --- ЧАСТЬ 2: Удаление постов, которых больше нет в источнике ---
        print("Проверка на удаленные посты...")
        
        # Берем последние 100 постов из источника, чтобы знать, что там осталось
        current_source_msgs = await client.get_messages(source_channel, limit=100)
        current_source_texts = [m.text[:50] for m in current_source_msgs if m.text]

        for t_msg in target_messages:
            if t_msg.text:
                # Если текста этого поста нет в источнике (проверяем по первым 50 символам)
                if t_msg.text[:50] not in current_source_texts:
                    try:
                        await client.delete_messages(target_channel, t_msg.id)
                        print(f"Удален пост из вашего канала (ID: {t_msg.id}), так как его нет в источнике.")
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"Не удалось удалить пост {t_msg.id}: {e}")

asyncio.run(main())
