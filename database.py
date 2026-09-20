import sqlite3
import time
from config import (
    DB_PATH, FACTIONS, REGIONS,
    START_POPULATION, START_GOLD, START_OIL, START_IRON, START_FOOD
)

def conn():
    c = sqlite3.connect(DB_PATH, timeout=60)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout = 60000")
    return c

def init_db():
    c = conn()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    x = c.cursor()
    x.executescript('''
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS players(user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, country_id INTEGER, group_id INTEGER, is_banned INTEGER DEFAULT 0, statements_banned INTEGER DEFAULT 0, created_at INTEGER);
    CREATE TABLE IF NOT EXISTS countries(id INTEGER PRIMARY KEY, name TEXT NOT NULL, flag TEXT NOT NULL, player_id INTEGER, population INTEGER DEFAULT 1000, gold INTEGER DEFAULT 10000, oil INTEGER DEFAULT 10000, iron INTEGER DEFAULT 10000, food INTEGER DEFAULT 10000, eliminated INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS regions(id INTEGER PRIMARY KEY, country_id INTEGER NOT NULL, code TEXT, name TEXT NOT NULL, owner_country_id INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS factories(id INTEGER PRIMARY KEY, region_id INTEGER NOT NULL, kind TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS armies(id INTEGER PRIMARY KEY, owner_type TEXT NOT NULL, owner_id INTEGER NOT NULL, region_id INTEGER NOT NULL, unit_type TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS spies(id INTEGER PRIMARY KEY, owner_country_id INTEGER NOT NULL, region_id INTEGER NOT NULL, status TEXT DEFAULT 'ready', target_region_id INTEGER, created_at INTEGER);
    CREATE TABLE IF NOT EXISTS wars(id INTEGER PRIMARY KEY AUTOINCREMENT, attacker_country_id INTEGER, defender_country_id INTEGER, region_id INTEGER NOT NULL, status TEXT NOT NULL, started_at INTEGER, ends_at INTEGER, winner_country_id INTEGER, created_at INTEGER);
    CREATE TABLE IF NOT EXISTS war_forces(id INTEGER PRIMARY KEY AUTOINCREMENT, war_id INTEGER, side TEXT, owner_type TEXT, owner_id INTEGER, from_region_id INTEGER, unit_type TEXT, amount INTEGER);
    CREATE TABLE IF NOT EXISTS caravans(id INTEGER PRIMARY KEY AUTOINCREMENT, sender_country_id INTEGER, receiver_country_id INTEGER, from_region_id INTEGER, to_region_id INTEGER, status TEXT, cargo_kind TEXT, cargo_amount INTEGER, departed_at INTEGER, arrive_at INTEGER, attacked_at INTEGER, battle_ends_at INTEGER, attacker_type TEXT, attacker_id INTEGER);
    CREATE TABLE IF NOT EXISTS statements(id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER, text TEXT, created_at INTEGER);
    CREATE TABLE IF NOT EXISTS season(id INTEGER PRIMARY KEY AUTOINCREMENT, number INTEGER, start_at INTEGER, end_at INTEGER, status TEXT);
    CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, text TEXT, created_at INTEGER);
    ''')
    
    # ارتقای خودکار جداول قدیمی جهت جلوگیری از خطای نبود ستون
    try:
        x.execute("ALTER TABLE war_forces ADD COLUMN from_region_id INTEGER DEFAULT 1")
    except Exception:
        pass

    for k, v in [("last_economy", str(int(time.time()))), ("battle_minutes", "20"), ("season_status", "active"), ("peace_time", "0")]:
        x.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))

    if x.execute("SELECT COUNT(*) FROM countries").fetchone()[0] == 0:
        for cid, fac in FACTIONS.items():
            init_gold = 25000 if fac["type"] == "faction" else START_GOLD
            x.execute(
                "INSERT INTO countries(id, name, flag, population, gold, oil, iron, food) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, fac["name"], fac["flag"], START_POPULATION, init_gold, START_OIL, START_IRON, START_FOOD)
            )
            for code, rname in REGIONS:
                x.execute("INSERT INTO regions(country_id, code, name, owner_country_id) VALUES(?, ?, ?, ?)", (cid, code, rname, cid))

            cap_id = x.execute("SELECT id FROM regions WHERE country_id=? AND code='capital'", (cid,)).fetchone()[0]
            for utype, uamt in fac["init_army"].items():
                if utype == "spy":
                    for _ in range(uamt):
                        x.execute("INSERT INTO spies(owner_country_id, region_id, status, created_at) VALUES(?, ?, 'ready', ?)",
                                  (cid, cap_id, int(time.time())))
                else:
                    x.execute("INSERT INTO armies(owner_type, owner_id, region_id, unit_type, amount) VALUES('country', ?, ?, ?, ?)",
                              (cid, cap_id, utype, uamt))

    if x.execute("SELECT COUNT(*) FROM season").fetchone()[0] == 0:
        now = int(time.time())
        x.execute("INSERT INTO season(number, start_at, status) VALUES(?, ?, ?)", (1, now, "active"))
    c.commit()
    c.close()

def get_setting(key, default=None):
    c = conn()
    try:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default
    finally:
        c.close()

def set_setting(key, value):
    c = conn()
    try:
        c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        c.commit()
    finally:
        c.close()

def log(kind, text):
    try:
        c = conn()
        c.execute("INSERT INTO logs(kind, text, created_at) VALUES(?, ?, ?)", (kind, text, int(time.time())))
        c.commit()
        c.close()
    except Exception:
        pass
