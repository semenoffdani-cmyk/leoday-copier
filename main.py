import os
import json
import requests
import feedparser
import re
import uuid
import base64
import urllib3
import time
import html
import urllib.parse
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 🔒 БЕЗОПАСНЫЕ НАСТРОЙКИ
# =====================================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('TARGET_CHANNEL')
GIGA_CLIENT_ID = os.environ.get('GIGACHAT_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGACHAT_CLIENT_SECRET')

if not BOT_TOKEN or not CHAT_ID:
    print("КРИТИЧЕСКАЯ ОШИБКА: Не заданы BOT_TOKEN или TARGET_CHANNEL")
    exit(1)

HISTORY_FILE = 'history.json'

RSS_FEEDS = [
    'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'https://www.cbr.ru/rss/RssNews',
    'https://ria.ru/export/rss2/archive/index.xml'
]

# ... (функции clean_text, load_history, save_history, fix_title_case, get_gigachat_token, rewrite_text, generate_image_gigachat, generate_image_fallback, send_photo, send_text остаются БЕЗ ИЗМЕНЕНИЙ) ...

# =====================================================================
# 🚀 ОБНОВЛЕННЫЙ MAIN
# =====================================================================
def main():
    history = load_history()
    token = get_gigachat_token()
    
    new_posts_count = 0

    FINANCIAL_KEYWORDS = [
        'ставк', 'рубл', 'инфляц', 'цб ', 'банк', 'акци', 'нефт', 'бюджет', 
        'налог', 'финанс', 'кредит', 'вклад', 'бирж', 'доллар', 'евро', 
        'рынок', 'экономик', 'компан', 'убыт', 'прибыл', 'тариф', 'цен'
    ]

    for feed_url in RSS_FEEDS:
        print(f"\nПроверка ленты: {feed_url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            resp = requests.get(feed_url, headers=headers, timeout=20)
            resp.encoding = 'utf-8' 
            feed = feedparser.parse(resp.content)
            
            print(f"Получено новостей из ленты: {len(feed.entries)}")
            if len(feed.entries) == 0:
                print("ВНИМАНИЕ: Лента пуста или не удалось её прочитать.")
        except Exception as e:
            print(f"Ошибка чтения RSS: {e}")
            continue
        
        # Увеличили лимит до 30 новостей, чтобы фильтру было из чего выбирать
        for entry in feed.entries[:30]:
            try:
                news_id = entry.link
                if not news_id or news_id in history:
                    continue
                    
                title = clean_text(entry.title)
                description = clean_text(getattr(entry, 'description', ''))
                text_to_check = f"{title}. {description}".lower()
                
                if len(text_to_check) < 30:
                    print(f"⏭️ Пропуск (слишком короткая): {title[:30]}...")
                    continue

                # Проверка на ключевые слова
                matched_keyword = next((kw for kw in FINANCIAL_KEYWORDS if kw in text_to_check), None)
                if not matched_keyword:
                    print(f"⏭️ Пропуск (не по теме): {title[:40]}...")
                    continue

                print(f"🔥 Найдена новость: {title[:40]}... (по слову '{matched_keyword}')")
                
                final_text = rewrite_text(f"{title}. {description}", token)
                
                print("Генерация постера...")
                image_bytes = generate_image_gigachat(title, token)
                
                if not image_bytes:
                    print("Резервный генератор...")
                    image_bytes = generate_image_fallback(title)
                
                success = False
                if image_bytes:
                    success = send_photo(final_text, image_bytes)
                else:
                    success = send_text(final_text)
                
                if success:
                    print("✅ Опубликовано!")
                    history[news_id] = datetime.now().isoformat()
                    save_history(history)
                    new_posts_count += 1
                    time.sleep(4)
            except Exception as e:
                print(f"Ошибка при обработке: {e}")
                continue
                
            if new_posts_count >= 3:
                print("\nЛимит постов на этот запуск выполнен.")
                return

if __name__ == '__main__':
    main()
