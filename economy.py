import math
import time
from database import conn, get_setting, set_setting, log
from config import FACTORIES, BONUS_PER_1000_POP, POP_GROWTH_PERCENT, UNITS, FACTIONS

def tick_once():
    c = conn()
    try:
        cur = c.cursor()
        rows = cur.execute("SELECT * FROM countries WHERE eliminated=0 AND player_id IS NOT NULL").fetchall()
        for r in rows:
            pop = max(0, r['population'])
            food = max(0, r['food'])

            if food >= pop * 2 and pop > 0:
                pop += math.floor(pop * POP_GROWTH_PERCENT / 100)
            if food < pop:
                pop = 100 if food <= 0 else food
                food = 0
            else:
                food -= pop
            cur.execute("UPDATE countries SET population=?, food=? WHERE id=?", (pop, food, r['id']))

            factories = cur.execute(
                "SELECT f.*, r.owner_country_id FROM factories f JOIN regions r ON r.id=f.region_id WHERE r.owner_country_id=?",
                (r['id'],)
            ).fetchall()
            bonus = 1 + (pop // 1000) * BONUS_PER_1000_POP / 100

            gold = cur.execute("SELECT gold FROM countries WHERE id=?", (r['id'],)).fetchone()[0]
            oil = cur.execute("SELECT oil FROM countries WHERE id=?", (r['id'],)).fetchone()[0]
            iron = cur.execute("SELECT iron FROM countries WHERE id=?", (r['id'],)).fetchone()[0]
            food = cur.execute("SELECT food FROM countries WHERE id=?", (r['id'],)).fetchone()[0]

            for f in factories:
                spec = FACTORIES[f['kind']]
                if oil < spec['run_oil']:
                    continue
                oil -= spec['run_oil']
                amount = math.floor(spec['amount'] * bonus)
                if spec['output'] == 'gold': gold += amount
                elif spec['output'] == 'oil': oil += amount
                elif spec['output'] == 'iron': iron += amount
                elif spec['output'] == 'food': food += amount
            cur.execute("UPDATE countries SET gold=?, oil=?, iron=?, food=? WHERE id=?", (gold, oil, iron, food, r['id']))

            for unit in ('soldier', 'helicopter', 'warship'):
                a = cur.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM armies WHERE owner_type='country' AND owner_id=? AND unit_type=?",
                    (r['id'], unit)
                ).fetchone()[0]
                if a <= 0:
                    continue
                rateg = UNITS[unit]['maint_gold']
                ratei = UNITS[unit]['maint_iron']
                paid = min(gold // rateg if rateg else a, iron // ratei if ratei else a, a)
                gold -= paid * rateg
                iron -= paid * ratei

                if paid < a:
                    lose = a - paid
                    left = lose
                    ar = cur.execute(
                        "SELECT id, amount FROM armies WHERE owner_type='country' AND owner_id=? AND unit_type=? ORDER BY id",
                        (r['id'], unit)
                    ).fetchall()
                    for row in ar:
                        take = min(row['amount'], left)
                        left -= take
                        if take == row['amount']:
                            cur.execute("DELETE FROM armies WHERE id=?", (row['id'],))
                        else:
                            cur.execute("UPDATE armies SET amount=amount-? WHERE id=?", (take, row['id']))
                        if left <= 0:
                            break
            cur.execute("UPDATE countries SET gold=?, iron=? WHERE id=?", (gold, iron, r['id']))

        c.commit()
        set_setting('last_economy', int(time.time()))
        log('economy', 'واریز اقتصادی انجام شد')
    except Exception as e:
        log('error', f'tick_once error: {e}')
    finally:
        c.close()

def catch_up(max_ticks=48):
    last = int(get_setting('last_economy', int(time.time())))
    now = int(time.time())
    elapsed = (now - last) // 3600
    n = min(elapsed, max_ticks)
    for _ in range(n):
        tick_once()
    return n

def build_factory(cid, rid, kind, count=1):
    if count <= 0: return False, "تعداد نامعتبر است."
    if kind not in FACTORIES: return False, 'نوع کارخانه نامعتبر است.'

    fac_spec = FACTIONS.get(cid, {})
    if fac_spec.get("type") == "faction":
        return False, "گروهک‌ها کارخانه ندارند!"

    c = conn()
    try:
        cur = c.cursor()
        r = cur.execute("SELECT * FROM regions WHERE id=? AND owner_country_id=?", (rid, cid)).fetchone()
        if not r:
            return False, 'این منطقه تحت کنترل شما نیست.'

        allowed_cap = fac_spec.get("caps", {}).get(kind, 10)
        current_built = cur.execute(
            "SELECT COUNT(*) FROM factories f JOIN regions rg ON rg.id=f.region_id WHERE rg.owner_country_id=? AND f.kind=?",
            (cid, kind)
        ).fetchone()[0]

        if current_built + count > allowed_cap:
            return False, f"سقف مجاز این کارخانه {allowed_cap} عدد است."

        spec = FACTORIES[kind]
        total_gold = spec['gold'] * count
        total_iron = spec['iron'] * count
        total_oil = spec['oil'] * count

        co = cur.execute("SELECT * FROM countries WHERE id=?", (cid,)).fetchone()
        if co['gold'] < total_gold or co['iron'] < total_iron or co['oil'] < total_oil:
            return False, 'منابع شما کافی نیست!'

        cur.execute("UPDATE countries SET gold=gold-?, iron=iron-?, oil=oil-? WHERE id=?", (total_gold, total_iron, total_oil, cid))
        for _ in range(count):
            cur.execute("INSERT INTO factories(region_id, kind) VALUES(?, ?)", (rid, kind))
        c.commit()
        return True, f'{count} عدد {spec["name"]} احداث شد.'
    finally:
        c.close()
