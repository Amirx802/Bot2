import math
import time
from database import conn, log, get_setting
from config import UNITS

def ratio_battle(ap, dp):
    if ap <= 0: return "defender", 0.0, 1.0
    if dp <= 0: return "attacker", 1.0, 0.0
    if ap == dp: return "draw", 0.5, 0.5
    if ap >= 4 * dp: return "attacker", 1.0, 0.0
    if dp >= 2 * ap: return "defender", 0.0, 1.0
    if ap > 3 * dp: return "attacker", 0.9, 0.25
    if ap >= 2 * dp: return "attacker", 0.75, 0.5
    return ("attacker", 0.75, 0.5) if ap > dp else ("defender", 0.5, 0.75)

def declare_war(attacker, defender, region_id):
    if get_setting("peace_time", "0") == "1":
        return False, "🕊 هم‌اکنون زمان صلح عمومی است و حملات مستقیم قفل هستند!"

    if attacker == defender:
        return False, "نمی‌توانید به قلمرو خود حمله کنید."
    c = conn()
    try:
        def_ctry = c.execute("SELECT player_id FROM countries WHERE id=?", (defender,)).fetchone()
        if not def_ctry or not def_ctry["player_id"]:
            return False, "این کشور هنوز بدون بازیکن و غیرفعال است!"

        r = c.execute("SELECT * FROM regions WHERE id=? AND owner_country_id=?", (region_id, defender)).fetchone()
        if not r:
            return False, "این منطقه در تصرف این کشور نیست."

        active = c.execute("SELECT id FROM wars WHERE region_id=? AND status='active'", (region_id,)).fetchone()
        if active:
            return False, f"این منطقه درگیر نبرد فعال #{active['id']} است."

        mins_row = c.execute("SELECT value FROM settings WHERE key='battle_minutes'").fetchone()
        mins = int(mins_row[0]) if mins_row else 20
        now = int(time.time())

        cursor = c.cursor()
        cursor.execute(
            "INSERT INTO wars(attacker_country_id, defender_country_id, region_id, status, started_at, ends_at, created_at) "
            "VALUES(?, ?, ?, 'active', ?, ?, ?)",
            (attacker, defender, region_id, now, now + mins * 60, now)
        )
        wid = cursor.lastrowid

        def_armies = c.execute(
            "SELECT * FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND amount>0",
            (defender, region_id)
        ).fetchall()
        for row in def_armies:
            c.execute(
                "INSERT INTO war_forces(war_id, side, owner_type, owner_id, from_region_id, unit_type, amount) "
                "VALUES(?, 'defender', 'country', ?, ?, ?, ?)",
                (wid, defender, region_id, row["unit_type"], row["amount"])
            )
            c.execute("DELETE FROM armies WHERE id=?", (row["id"],))

        c.commit()
        log("war", f"نبرد {wid} در منطقه {region_id} آغاز شد.")
        return True, wid
    except Exception as e:
        return False, f"خطا در ایجاد نبرد: {str(e)}"
    finally:
        c.close()

def add_force(war_id, side, country_id, from_region_id, unit_type, amount):
    if side not in ("attacker", "defender"): return False, "طرف نبرد نامعتبر است."
    if unit_type not in ("soldier", "helicopter", "warship"): return False, "نوع نیرو نامعتبر است."
    if amount <= 0: return False, "تعداد باید مثبت باشد."

    c = conn()
    try:
        w = c.execute("SELECT * FROM wars WHERE id=? AND status='active'", (war_id,)).fetchone()
        if not w: return False, "نبرد فعال پیدا نشد."

        row = c.execute(
            "SELECT id, amount FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND unit_type=?",
            (country_id, from_region_id, unit_type)
        ).fetchone()

        if not row or row["amount"] < amount:
            return False, "تعداد نیروی مستقر در این منطقه کافی نیست."

        c.execute("UPDATE armies SET amount=amount-? WHERE id=?", (amount, row["id"]))
        c.execute("DELETE FROM armies WHERE id=? AND amount<=0", (row["id"],))

        wf = c.execute(
            "SELECT id FROM war_forces WHERE war_id=? AND side=? AND owner_id=? AND from_region_id=? AND unit_type=?",
            (war_id, side, country_id, from_region_id, unit_type)
        ).fetchone()

        if wf:
            c.execute("UPDATE war_forces SET amount=amount+? WHERE id=?", (amount, wf["id"]))
        else:
            c.execute(
                "INSERT INTO war_forces(war_id, side, owner_type, owner_id, from_region_id, unit_type, amount) "
                "VALUES(?, ?, 'country', ?, ?, ?, ?)",
                (war_id, side, country_id, from_region_id, unit_type, amount)
            )
        c.commit()
        return True, "نیروها به میدان نبرد اعزام شدند."
    except Exception as e:
        return False, f"خطا: {str(e)}"
    finally:
        c.close()

def _loss(c, rows, fraction):
    for r in rows:
        lose = min(r["amount"], math.ceil(r["amount"] * fraction))
        if lose > 0:
            c.execute("UPDATE war_forces SET amount=amount-? WHERE id=?", (lose, r["id"]))

def _return_force(c, row):
    if row["amount"] <= 0: return
    rid = row["from_region_id"] if row["from_region_id"] else 1
    ex = c.execute(
        "SELECT id FROM armies WHERE owner_type=? AND owner_id=? AND region_id=? AND unit_type=?",
        (row["owner_type"], row["owner_id"], rid, row["unit_type"])
    ).fetchone()
    if ex:
        c.execute("UPDATE armies SET amount=amount+? WHERE id=?", (row["amount"], ex["id"]))
    else:
        c.execute(
            "INSERT INTO armies(owner_type, owner_id, region_id, unit_type, amount) VALUES(?, ?, ?, ?, ?)",
            (row["owner_type"], row["owner_id"], rid, row["unit_type"], row["amount"])
        )

def resolve_war(wid):
    c = conn()
    try:
        w = c.execute("SELECT * FROM wars WHERE id=? AND status='active'", (wid,)).fetchone()
        if not w or int(time.time()) < w["ends_at"]:
            return None

        atk = c.execute("SELECT * FROM war_forces WHERE war_id=? AND side='attacker' AND amount>0", (wid,)).fetchall()
        deff = c.execute("SELECT * FROM war_forces WHERE war_id=? AND side='defender' AND amount>0", (wid,)).fetchall()

        ap = sum(r["amount"] * UNITS[r["unit_type"]]["power"] for r in atk)
        dp = sum(r["amount"] * UNITS[r["unit_type"]]["power"] for r in deff)

        winner, af, df = ratio_battle(ap, dp)

        if winner == "draw":
            for r in atk + deff: _return_force(c, r)
            c.execute("DELETE FROM war_forces WHERE war_id=?", (wid,))
            c.execute("UPDATE wars SET status='finished', winner_country_id=NULL WHERE id=?", (wid,))
            c.commit()
            return {"winner": None, "ap": ap, "dp": dp, "region": w["region_id"]}

        _loss(c, atk, 1.0 - af)
        _loss(c, deff, 1.0 - df)

        if winner == "attacker":
            c.execute("UPDATE regions SET owner_country_id=? WHERE id=?", (w["attacker_country_id"], w["region_id"]))
            win_country = w["attacker_country_id"]
        else:
            win_country = w["defender_country_id"]

        survivors = c.execute("SELECT * FROM war_forces WHERE war_id=? AND amount>0", (wid,)).fetchall()
        for r in survivors: _return_force(c, r)

        c.execute("DELETE FROM war_forces WHERE war_id=?", (wid,))
        c.execute("UPDATE wars SET status='finished', winner_country_id=? WHERE id=?", (win_country, wid))
        c.commit()
        return {"winner": win_country, "ap": ap, "dp": dp, "region": w["region_id"]}
    except Exception as e:
        log("error", f"resolve_war error: {str(e)}")
        return None
    finally:
        c.close()

def process_wars():
    c = conn()
    try:
        rows = c.execute("SELECT id FROM wars WHERE status='active' AND ends_at<=?", (int(time.time()),)).fetchall()
    finally:
        c.close()

    out = []
    for r in rows:
        x = resolve_war(r["id"])
        if x: out.append(x)
    return out
