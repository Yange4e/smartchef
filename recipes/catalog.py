CATEGORIES = [
    {"id": "vegetables", "kk": "Көкөністер", "ru": "Овощи", "emoji": "🥕"},
    {"id": "fruits", "kk": "Жемістер", "ru": "Фрукты", "emoji": "🍎"},
    {"id": "dairy", "kk": "Сүт өнімдері", "ru": "Молочные продукты", "emoji": "🥛"},
    {"id": "protein", "kk": "Ет, жұмыртқа және бұршақ", "ru": "Мясо, яйца и бобовые", "emoji": "🥚"},
    {"id": "grains", "kk": "Жарма және макарон", "ru": "Крупы и макароны", "emoji": "🍚"},
    {"id": "pantry", "kk": "Негізгі өнімдер", "ru": "Базовые продукты", "emoji": "🧂"},
]

PRODUCTS = [
    {"id": "potato", "category": "vegetables", "kk": "Картоп", "ru": "Картофель"},
    {"id": "carrot", "category": "vegetables", "kk": "Сәбіз", "ru": "Морковь"},
    {"id": "onion", "category": "vegetables", "kk": "Пияз", "ru": "Лук"},
    {"id": "tomato", "category": "vegetables", "kk": "Қызанақ", "ru": "Помидор"},
    {"id": "apple", "category": "fruits", "kk": "Алма", "ru": "Яблоко"},
    {"id": "banana", "category": "fruits", "kk": "Банан", "ru": "Банан"},
    {"id": "lemon", "category": "fruits", "kk": "Лимон", "ru": "Лимон"},
    {"id": "pear", "category": "fruits", "kk": "Алмұрт", "ru": "Груша"},
    {"id": "milk", "category": "dairy", "kk": "Сүт", "ru": "Молоко"},
    {"id": "cheese", "category": "dairy", "kk": "Ірімшік", "ru": "Сыр"},
    {"id": "cottage_cheese", "category": "dairy", "kk": "Сүзбе", "ru": "Творог"},
    {"id": "kefir", "category": "dairy", "kk": "Айран", "ru": "Кефир"},
    {"id": "egg", "category": "protein", "kk": "Жұмыртқа", "ru": "Яйцо"},
    {"id": "chicken", "category": "protein", "kk": "Тауық еті", "ru": "Курица"},
    {"id": "beans", "category": "protein", "kk": "Үрмебұршақ", "ru": "Фасоль"},
    {"id": "lentils", "category": "protein", "kk": "Жасымық", "ru": "Чечевица"},
    {"id": "rice", "category": "grains", "kk": "Күріш", "ru": "Рис"},
    {"id": "pasta", "category": "grains", "kk": "Макарон", "ru": "Макароны"},
    {"id": "buckwheat", "category": "grains", "kk": "Қарақұмық", "ru": "Гречка"},
    {"id": "oatmeal", "category": "grains", "kk": "Сұлы үлпегі", "ru": "Овсяные хлопья"},
    {"id": "oil", "category": "pantry", "kk": "Өсімдік майы", "ru": "Растительное масло"},
    {"id": "flour", "category": "pantry", "kk": "Ұн", "ru": "Мука"},
    {"id": "sugar", "category": "pantry", "kk": "Қант", "ru": "Сахар"},
    {"id": "salt", "category": "pantry", "kk": "Тұз", "ru": "Соль"},
]


def build_products(selected_ids, extra, language):
    language = language if language in ("kk", "ru") else "kk"
    lookup = {product["id"]: product for product in PRODUCTS}
    selected = list(dict.fromkeys(selected_ids))
    if any(product_id not in lookup for product_id in selected):
        raise ValueError("Белгісіз өнім таңдалды." if language == "kk" else "Выбран неизвестный продукт.")
    parts = [lookup[product_id][language] for product_id in selected]
    extra = extra.strip()
    if extra:
        parts.append(extra)
    combined = ", ".join(parts)
    if not 3 <= len(combined) <= 500:
        raise ValueError(
            "Өнімдерді таңда немесе енгіз: жалпы ұзындығы 3–500 таңба."
            if language == "kk" else "Выбери или введи продукты: общая длина 3–500 символов."
        )
    return selected, combined
