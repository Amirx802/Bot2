import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8882882330:AAEVYzu-3TMhH5D81sAEcFRMHj7FxSgtrXE")
ADMIN_IDS = [7239765881, 6945406088]

NEWS_CHANNEL_ID = "@B_World_War"
DB_PATH = "database.db"

ECONOMY_HOURS = 1
BATTLE_MINUTES = 20
CARAVAN_NORMAL_MINUTES = 15
CARAVAN_BORDER_MINUTES = 5

START_POPULATION = 1000
START_GOLD = 10000
START_OIL = 10000
START_IRON = 10000
START_FOOD = 10000
POP_GROWTH_PERCENT = 20
FOOD_PER_POP = 1
BONUS_PER_1000_POP = 1

FACTORIES = {
    "gold":  {"name": "کارخانه طلا",  "gold": 500, "iron": 1500, "oil": 100, "output": "gold",  "amount": 150, "run_oil": 10},
    "oil":   {"name": "پالایشگاه",    "gold": 500, "iron": 1000, "oil": 100, "output": "oil",   "amount": 200, "run_oil": 5},
    "iron":  {"name": "کارخانه آهن",  "gold": 400, "iron": 2000, "oil": 100, "output": "iron",  "amount": 350, "run_oil": 8},
    "food":  {"name": "مزرعه صنعتی", "gold": 300, "iron": 1200, "oil": 100, "output": "food",  "amount": 600, "run_oil": 5},
}

UNITS = {
    "soldier":    {"name": "سرباز", "power": 1.0, "population": 10,  "gold": 20,  "iron": 30,  "oil": 0,   "maint_gold": 1,  "maint_iron": 1},
    "helicopter": {"name": "هلیکوپتر", "power": 2.0, "population": 50,  "gold": 200, "iron": 150, "oil": 100, "maint_gold": 4,  "maint_iron": 4},
    "warship":    {"name": "ناو جنگی", "power": 3.0, "population": 100, "gold": 400, "iron": 500, "oil": 300, "maint_gold": 8,  "maint_iron": 8},
    "spy":        {"name": "جاسوس / نفوذی", "power": 0.5, "population": 5,   "gold": 500, "iron": 250, "oil": 100, "maint_gold": 20, "maint_iron": 20},
}

FACTIONS = {
    1: {
        "name": "ایران", "flag": "🇮🇷", "type": "country",
        "desc": "🛢 نفت نامحدود (سقف ۳۰) | 🌾 کشاورزی قوی (سقف ۲۰) | ⛓ آهن متوسط (سقف ۱۰) | 💰 طلا (سقف ۱۰)",
        "caps": {"oil": 30, "food": 20, "iron": 10, "gold": 10},
        "init_army": {"soldier": 100, "helicopter": 10, "warship": 2, "spy": 5}
    },
    2: {
        "name": "ایالات متحده آمریکا", "flag": "🇺🇸", "type": "country",
        "desc": "💰 قطب اقتصاد و طلا (سقف ۲۵) | 🛢 نفت بالا (سقف ۲۰) | ⛓ صنایع آهن پیشرفته (سقف ۲۰) | 🌾 غذا (سقف ۱۵)",
        "caps": {"gold": 25, "oil": 20, "iron": 20, "food": 15},
        "init_army": {"soldier": 120, "helicopter": 15, "warship": 5, "spy": 5}
    },
    3: {
        "name": "روسیه", "flag": "🇷🇺", "type": "country",
        "desc": "⛓ غول آهن و تسلیحات (سقف ۳۰) | 🛢 نفت و گاز فراوان (سقف ۲۵) | 💰 طلا (سقف ۱۰) | 🌾 غذا کم (سقف ۸)",
        "caps": {"iron": 30, "oil": 25, "gold": 10, "food": 8},
        "init_army": {"soldier": 150, "helicopter": 12, "warship": 4, "spy": 4}
    },
    4: {
        "name": "چین", "flag": "🇨🇳", "type": "country",
        "desc": "🏭 کارخانجات آهن عظیم (سقف ۳۰) | 🌾 مزارع گسترده (سقف ۲۵) | 💰 طلا (سقف ۱۵) | 🛢 نفت کم (سقف ۵)",
        "caps": {"iron": 30, "food": 25, "gold": 15, "oil": 5},
        "init_army": {"soldier": 200, "helicopter": 8, "warship": 3, "spy": 6}
    },
    5: {
        "name": "انگلستان", "flag": "🇬🇧", "type": "country",
        "desc": "💰 مرکز سرمایه‌گذاری طلا (سقف ۳۰) | 🛢 بدون نفت (سقف ۰!) | ⛓ آهن کم (سقف ۵) | 🌾 مزارع (سقف ۱۰)",
        "caps": {"gold": 30, "oil": 0, "iron": 5, "food": 10},
        "init_army": {"soldier": 90, "helicopter": 10, "warship": 6, "spy": 8}
    },
    6: {
        "name": "حزب‌الله", "flag": "🟡", "type": "faction",
        "desc": "🏴 بدون امکان ساخت کارخانه | ⚔️ ارتش چریکی قدرتمند",
        "caps": {"gold": 0, "oil": 0, "iron": 0, "food": 0},
        "init_army": {"soldier": 450, "helicopter": 40, "warship": 0, "spy": 25}
    },
    7: {
        "name": "انصارالله", "flag": "🟢", "type": "faction",
        "desc": "🏴 بدون ساخت‌وساز | ⚔️ نیروهای موشکی و ضدکشتی سهمگین",
        "caps": {"gold": 0, "oil": 0, "iron": 0, "food": 0},
        "init_army": {"soldier": 500, "helicopter": 30, "warship": 10, "spy": 20}
    },
    8: {
        "name": "داعش", "flag": "🏴", "type": "faction",
        "desc": "🏴 بدون ساخت‌وساز | ⚔️ لشکر انتحاری و نفوذی‌های مرگبار",
        "caps": {"gold": 0, "oil": 0, "iron": 0, "food": 0},
        "init_army": {"soldier": 650, "helicopter": 15, "warship": 0, "spy": 40}
    },
    9: {
        "name": "حماس", "flag": "🇵🇸", "type": "faction",
        "desc": "🏴 بدون ساخت‌وساز | ⚔️ ارتش چریکی و استقامتی",
        "caps": {"gold": 0, "oil": 0, "iron": 0, "food": 0},
        "init_army": {"soldier": 420, "helicopter": 10, "warship": 5, "spy": 35}
    },
    10: {
        "name": "طالبان", "flag": "⚪", "type": "faction",
        "desc": "🏴 بدون ساخت‌وساز | ⚔️ نیروهای کوهستان و غنائم زرهی",
        "caps": {"gold": 0, "oil": 0, "iron": 0, "food": 0},
        "init_army": {"soldier": 580, "helicopter": 35, "warship": 0, "spy": 15}
    }
}

REGIONS = [
    ("nw", "شمال‌غرب"), ("n", "شمال"),   ("ne", "شمال‌شرق"),
    ("w", "غرب"),       ("capital", "پایتخت / پایگاه مرکزی"), ("e", "شرق"),
    ("sw", "جنوب‌غرب"), ("s", "جنوب"),   ("se", "جنوب‌شرق")
]
