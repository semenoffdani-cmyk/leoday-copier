def rewrite_text(text, token):
    if not token or not text: return None
    try:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": (
                    "Ты — профессиональный редактор финансового канала. Пиши строго по шаблону. "
                    "КРИТИЧЕСКИ ВАЖНО: Проверяй падежи и согласование слов! "
                    "Помни: 'Банк России' — это мужской род. Правильно: 'Банк России назначил', а НЕ 'Банка России назначила'. "
                    "КРИТИЧЕСКИ ВАЖНО: НЕ приписывай Банку России (Центробанку) несуществующие функции! Если в новости речь идет о другой организации, пиши именно её название."
                )},
                {"role": "user", "content": (
                    f"Напиши пост строго по этому шаблону (не добавляй ничего лишнего):\n\n"
                    f"[1-2 предложения СУТИ новости. Обязательно начни с заглавной буквы. НЕ пиши просто 'Банк России'. Не пиши капсом.]\n\n"
                    f"<b>Что это значит?</b>\n\n[1-2 предложения о влиянии на кошелек или работу]\n\n"
                    f"<b>Что дальше?</b>\n\n[1 предложение о том, на какой показатель смотреть]\n\n"
                    f"Текст новости:\n{text}"
                )}
            ],
            "temperature": 0.3, "max_tokens": 1000
        }
        response = SESSION.post(url, headers=headers, json=payload, verify=VERIFY_SSL, timeout=90)
        if response.status_code != 200: return None
        rewritten = response.json()['choices'][0]['message']['content'].strip()
        
        if any(root in rewritten.lower() for root in ["генеративн", "облада", "мнени", "ограничен", "неправильн", "благодарим", "отказ"]): return None
        if len(rewritten) < 50: return None
        
        # 1. Очищаем от мусорных символов
        rewritten = re.sub(r'[*_`#]', '', rewritten)
        
        # 2. Исправляем регистр
        rewritten = fix_title_case(rewritten)
        
        # 3. Удаляем фразы-паразиты
        rewritten = re.sub(r'(?i)банк россии не имеет отношения к данной информации\.?\s*', '', rewritten)
        rewritten = re.sub(r'(?i)amburg\w*', '', rewritten)
        rewritten = re.sub(r'(?i)domclick', '', rewritten)
        
        # 4. Чиним "Банк России", если он остался без сказуемого
        if re.match(r'^[А-ЯA-Z]', rewritten) and re.match(r'^[А-ЯA-Z]+\s', rewritten):
            first_word = rewritten.split()[0]
            if first_word.endswith(('Л', 'ЛА', 'ЛО', 'ЛИ', 'ЕТ', 'ИТ', 'УТ', 'ЮТ')):
                rewritten = "Банк России " + rewritten

        rewritten = re.sub(r'(?i)банк россии', 'Банк России', rewritten)
        
        # 5. Жестко расставляем заголовки и отступы
        rewritten = re.sub(r'(?i)что это значит\?', '<b>Что это значит?</b>', rewritten)
        rewritten = re.sub(r'(?i)что дальше\?', '<b>Что дальше?</b>', rewritten)
        rewritten = re.sub(r'\s*<b>', '\n\n<b>', rewritten)
        rewritten = re.sub(r'</b>\s*', '</b>\n\n', rewritten)
        
        # 🚨 6. УДАЛЯЕМ ВСЕ ПРОБЕЛЫ В НАЧАЛЕ КАЖДОЙ СТРОКИ (включая неразрывные)
        rewritten = rewritten.replace('\xa0', ' ') # Меняем неразрывный пробел на обычный
        rewritten = re.sub(r'(?m)^\s+', '', rewritten) # Удаляем пробелы в начале каждой строки
        
        return rewritten.strip()
    except Exception: return None
