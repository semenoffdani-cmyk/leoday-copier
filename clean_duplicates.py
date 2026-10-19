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
        print("Подключение к каналу...")
        
        # Получаем последние 200 сообщений из ВАШЕГО канала
        messages = await client.get_messages(target_channel, limit=200)
        
        seen_texts = {} # Словарь для хранения: {текст: ID сообщения}
        deleted_count = 0

        # Проходим по сообщениям от старых к новым
        for msg in reversed(messages):
            # Проверяем только текстовые посты или подписи к медиа
            text = msg.text
            if not text:
                continue
            
            # Если такой текст уже встречался ранее в канале
            if text in seen_texts:
                old_msg_id = seen_texts[text]
                try:
                    # Удаляем старое сообщение
                    await client.delete_messages(target_channel, old_msg_id)
                    print(f"Удален дубль (старый ID: {old_msg_id}, оставлен новый ID: {msg.id})")
                    deleted_count += 1
                    await asyncio.sleep(1) # Пауза, чтобы Telegram не забанил
                except Exception as e:
                    print(f"Ошибка при удалении {old_msg_id}: {e}")
            
            # Записываем актуальный ID для этого текста
            seen_texts[text] = msg.id

        print(f"\nОчистка завершена. Удалено дублей: {deleted_count}")

asyncio.run(main())
