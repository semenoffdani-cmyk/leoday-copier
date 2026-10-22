def detect_category(text):
    text = text.lower()
    
    # 1. ЭНЕРГЕТИКА
    if any(w in text for w in ['нефт', 'газ', 'энергет', 'топлив', 'дизел', 'бензин', 'баррел']):
        return "🛢️ <b>ЭНЕРГЕТИКА</b>\n\n"

    # 2. ТЕХНОЛОГИИ
    tech_keywords = ['нейросет', 'искусственн', 'чип', 'робот', 'технолог', 'apple', 'openai', 'смартфон', 'гаджет', 'ит-', 'айти', 'кибербезопасн']
    if any(w in text for w in tech_keywords) or re.search(r'\bии\b', text):
        return "🤖 <b>ТЕХНОЛОГИИ</b>\n\n"

    # 3. ДЕНЬГИ
    money_keywords = ['вклад', 'кредит', 'ипотек', 'зарплат', 'пенси', 'жкх', 'рубл', 'доллар', 'евро', 'сбербанк', 'втб', 'тинькофф', 'банк']
    if any(w in text for w in money_keywords):
        return "💸 <b>ДЕНЬГИ</b>\n\n"

    # 4. ЭКОНОМИКА
    return "📊 <b>ЭКОНОМИКА</b>\n\n"
