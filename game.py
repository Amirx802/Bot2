import time
from database import conn, get_setting
from config import UNITS, FACTORIES, FACTIONS

def country(cid):
    if not cid: return None
    c = conn()
    try:
        return c.execute("SELECT * FROM countries WHERE id=?", (cid,)).fetchone()
    finally:
        c.close()

def player(uid):
    if not uid: return None
    c = conn()
    try:
        return c.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone()
    finally:
        c.close()

def my_country(uid):
    p = player(uid)
    return country(p["country_id"]) if p and p["country_id"] else None

def regions(cid):
    c = conn()
    try:
        return c.execute("SELECT * FROM regions WHERE owner_country_id=? ORDER BY id", (cid,)).fetchall()
    finally:
        c.close()

def region(rid):
    if not rid: return None
    c = conn()
    try:
        return c.execute("SELECT * FROM regions WHERE id=?", (rid,)).fetchone()
    finally:
        c.close()

def armies(owner_type, owner_id, region_id=None):
    c = conn()
    try:
        q = "SELECT unit_type, SUM(amount) amount FROM armies WHERE owner_type=? AND owner_id=?"
        args = [owner_type, owner_id]
        if region_id is not None:
            q += " AND region_id=?"
            args.append(region_id)
        q += " GROUP BY unit_type"
        rows = c.execute(q, args).fetchall()
        return {r["unit_type"]: r["amount"] for r in rows}
    finally:
        c.close()

def total_power(owner_type, owner_id, region_id=None):
    a = armies(owner_type, owner_id, region_id)
    return sum(a.get(k, 0) * UNITS[k]["power"] for k in ("soldier", "helicopter", "warship"))

def fmt_resources(c):
    return (
        f"💰 طلا: <b>{c['gold']:,}</b> | 🛢 نفت: <b>{c['oil']:,}</b>\n"
        f"⛓ آهن: <b>{c['iron']:,}</b> | 🌾 غذا: <b>{c['food']:,}</b>\n"
        f"👥 جمعیت: <b>{c['population']:,}</b>"
    )

def dashboard_text(cid, uid=None):
    c = country(cid)
    if not c:
        return "جناح یافت نشد."
    owned = regions(cid)
    cap = next((r for r in owned if r["code"] == "capital"), None)
    ars = armies("country", cid)
    power = total_power("country", cid)

    last = int(get_setting("last_economy", int(time.time())))
    next_tick = max(0, 3600 - (int(time.time()) - last) % 3600)
    m, s = divmod(next_tick, 60)

    co = conn()
    try:
        factories_count = co.execute(
            "SELECT COUNT(*) FROM factories f JOIN regions r ON r.id=f.region_id WHERE r.owner_country_id=?",
            (cid,)
        ).fetchone()[0]
        spies_count = co.execute(
            "SELECT COUNT(*) FROM spies WHERE owner_country_id=? AND status='ready'", (cid,)
        ).fetchone()[0]
        active_wars_count = co.execute(
            "SELECT COUNT(*) FROM wars WHERE (attacker_country_id=? OR defender_country_id=?) AND status='active'",
            (cid, cid)
        ).fetchone()[0]
        p_info = co.execute("SELECT * FROM players WHERE user_id=?", (uid,)).fetchone() if uid else None
    finally:
        co.close()

    fac_spec = FACTIONS.get(cid, {})
    p_name = p_info["name"] if p_info else "فرمانده"
    peace_status = get_setting("peace_time", "0")
    peace_badge = "🕊 <b>وضعیت صلح عمومی فعال است</b>\n" if peace_status == "1" else ""

    return (
        f"{peace_badge}"
        f"🎖 <b>داشبورد جامع: {p_name}</b>\n"
        f"👑 جناح: {c['flag']} <b>{c['name']}</b>\n"
        f"📜 ویژگی: <i>{fac_spec.get('desc', '')}</i>\n\n"
        f"📦 <b>خزانه و منابع ملی:</b>\n"
        f"💰 طلا: <b>{c['gold']:,}</b> | 🛢 نفت: <b>{c['oil']:,}</b>\n"
        f"⛓ آهن: <b>{c['iron']:,}</b> | 🌾 غذا: <b>{c['food']:,}</b>\n"
        f"👥 جمعیت کل: <b>{c['population']:,} نفر</b>\n\n"
        f"⚔️ <b>قوای رزمی آماده:</b>\n"
        f"⚡ توان نظامی: <b>{power:g}</b>\n"
        f"🪖 پیاده‌نظام: <b>{ars.get('soldier', 0):,}</b>\n"
        f"🚁 هلیکوپتر: <b>{ars.get('helicopter', 0):,}</b>\n"
        f"🚢 ناو جنگی: <b>{ars.get('warship', 0):,}</b>\n"
        f"🕵️ نفوذی‌ها: <b>{spies_count:,}</b>\n\n"
        f"🗺 <b>مناطق و مراکز:</b>\n"
        f"🏛 پایگاه مرکزی: {'✅ در اختیار' if cap else '❌ سقوط کرده'}\n"
        f"🌐 مناطق تحت تسلط: <b>{len(owned)} از ۹</b>\n"
        f"🏭 کارخانجات: <b>{factories_count} مرکز</b>\n"
        f"🚩 درگیری‌های فعال: <b>{active_wars_count} نبرد</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>واریز اقتصادی بعدی:</b> <b>{m:02d}:{s:02d} دقیقه</b>"
    )

def map_keyboard(cid):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    c = conn()
    try:
        rows = c.execute("SELECT * FROM regions WHERE country_id=? ORDER BY id", (cid,)).fetchall()
    finally:
        c.close()
    d = {r["code"]: r for r in rows}

    out = []
    for pair in (("nw", "n", "ne"), ("w", "capital", "e"), ("sw", "s", "se")):
        line = []
        for code in pair:
            r = d[code]
            mark = "🟢" if r["owner_country_id"] == cid else "🔴"
            line.append(InlineKeyboardButton(f"{mark} {r['name']}", callback_data=f"region:{r['id']}"))
        out.append(line)

    out.append([InlineKeyboardButton("🏠 بازگشت به داشبورد", callback_data="home")])
    return InlineKeyboardMarkup(out)

def region_text(cid, rid):
    r = region(rid)
    if not r:
        return "منطقه پیدا نشد."
    owner = country(r["owner_country_id"])
    a = armies("country", cid, rid)

    c = conn()
    try:
        fs = c.execute("SELECT kind, COUNT(*) n FROM factories WHERE region_id=? GROUP BY kind", (rid,)).fetchall()
        spies_count = c.execute(
            "SELECT COUNT(*) FROM spies WHERE owner_country_id=? AND region_id=? AND status='ready'",
            (cid, rid)
        ).fetchone()[0]
    finally:
        c.close()

    f_desc = ", ".join(f"{FACTORIES[x['kind']]['name']} × {x['n']}" for x in fs) if fs else "ندارد"
    military = ", ".join(f"{UNITS[k]['name']} × {v:,}" for k, v in a.items()) if a else "هیچ نیرویی مستقر نیست"
    active_tag = "" if owner and owner["player_id"] else " <i>(بدون بازیکن - غیرفعال)</i>"
    owner_name = f"{owner['flag']} {owner['name']}" if owner else "نامشخص"

    return (
        f"📍 <b>منطقه {r['name']}</b>\n"
        f"👑 حاکم فعلی: {owner_name}{active_tag}\n"
        f"🏭 کارخانه‌ها: {f_desc}\n"
        f"⚔️ ارتش مستقر شما: {military}\n"
        f"🕵️ نفوذی‌های حاضر: {spies_count:,}\n"
    )
