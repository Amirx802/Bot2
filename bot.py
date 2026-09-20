import asyncio
import os
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import config
from database import (
    init_db,
    conn,
    log,
    set_setting,
    get_setting
)
from game import *
from economy import (
    catch_up,
    build_factory
)
from combat import (
    declare_war,
    add_force,
    process_wars
)

init_db()

def is_admin(uid):
    return uid in config.ADMIN_IDS

def kb(rows):
    return InlineKeyboardMarkup(rows)

async def safe_edit(q, text, reply_markup=None, parse_mode="HTML"):
    try:
        return await q.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        if "Message is not modified" in str(e):
            return
        try:
            return await q.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass

def main_kb(uid=None):
    rows = [
        [
            InlineKeyboardButton("🎖 داشبورد جامع", callback_data="refresh_dashboard"),
            InlineKeyboardButton("📦 منابع ملی", callback_data="resources")
        ],
        [
            InlineKeyboardButton("🗺 نقشه قلمرو", callback_data="map"),
            InlineKeyboardButton("🏭 کارخانه‌ها", callback_data="factories")
        ],
        [
            InlineKeyboardButton("⚔️ خرید ارتش", callback_data="buy_army_menu"),
            InlineKeyboardButton("🚩 اتاق عملیات جنگ", callback_data="wars")
        ],
        [
            InlineKeyboardButton("🚚 کاروان تجاری / حمله", callback_data="caravan"),
            InlineKeyboardButton("📢 بیانیه رسمی", callback_data="statement")
        ]
    ]
    if uid and is_admin(uid):
        rows.append([InlineKeyboardButton("👑 پنل مدیریت و صلح", callback_data="admin_panel")])
    return kb(rows)

def selection_buttons():
    c = conn()
    try:
        rows = c.execute("SELECT * FROM countries WHERE player_id IS NULL AND eliminated=0 ORDER BY id").fetchall()
    finally:
        c.close()

    country_list = []
    faction_list = []

    for r in rows:
        btn = InlineKeyboardButton(f"{r['flag']} {r['name']}", callback_data=f"join_info:{r['id']}")
        if config.FACTIONS[r['id']]["type"] == "country":
            country_list.append([btn])
        else:
            faction_list.append([btn])

    out = []
    if country_list:
        out.append([InlineKeyboardButton("🏛 ── کشورهای صنعتی ──", callback_data="noop")])
        out.extend(country_list)
    if faction_list:
        out.append([InlineKeyboardButton("🏴 ── گروهک‌ها و جنبش‌ها ──", callback_data="noop")])
        out.extend(faction_list)

    return kb(out)

async def send_dashboard(target, cid, uid=None, edit=False):
    text = dashboard_text(cid, uid)
    markup = main_kb(uid)
    if edit:
        try:
            return await target.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            return
    return await target.reply_text(text, reply_markup=markup, parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = player(uid)

    if p and p["is_banned"]:
        return await update.message.reply_text("⛔ دسترسی شما مسدود است.")

    if not p:
        u = update.effective_user
        c = conn()
        try:
            c.execute(
                "INSERT INTO players(user_id, username, name, created_at) VALUES(?, ?, ?, ?)",
                (u.id, u.username or "", u.full_name, int(time.time()))
            )
            c.commit()
        finally:
            c.close()
        p = player(uid)

    catch_up()

    if not p["country_id"]:
        return await update.message.reply_text(
            "🌍 <b>به بازی استراتژیک جنگ جهانی خوش آمدید!</b>\n\nجناح خود را انتخاب کنید:",
            reply_markup=selection_buttons(),
            parse_mode="HTML"
        )

    return await send_dashboard(update.message, p["country_id"], uid=uid)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = player(uid)
    if not p or not p["country_id"]:
        return await start(update, context)
    return await send_dashboard(update.message, p["country_id"], uid=uid)

async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return await update.message.reply_text("⛔ شما دسترسی ادمین ندارید.")
    return await show_admin_panel(update.message)

async def show_admin_panel(target, edit=False):
    peace_mode = get_setting("peace_time", "0")
    peace_text = "🟢 زمان صلح: فعال (حملات قفل)" if peace_mode == "1" else "🔴 زمان صلح: غیرفعال (جنگ آزاد)"

    txt = (
        "👑 <b>پنل کنترل و مدیریت سرور:</b>\n\n"
        f"وضعیت جاری: <b>{peace_text}</b>\n"
        "<i>در زمان صلح حملات مستقیم قفل هستند ولی حمله با کاروان باز است.</i>"
    )
    buttons = [
        [InlineKeyboardButton(f"🕊 تغییر وضعیت صلح ({'خاموش کردن' if peace_mode=='1' else 'روشن کردن'})", callback_data="adm_toggle_peace")],
        [InlineKeyboardButton("👥 بازیکنان فعال", callback_data="adm_view_players"),
         InlineKeyboardButton("📊 منابع کشورها", callback_data="adm_view_countries")],
        [InlineKeyboardButton("💰 اهدای منابع به کشور", callback_data="adm_give_res_step1"),
         InlineKeyboardButton("⚔️ اهدای ارتش به منطقه", callback_data="adm_give_units_step1")],
        [InlineKeyboardButton("📥 دریافت فایل دیتابیس", callback_data="adm_get_db"),
         InlineKeyboardButton("📤 بازگردانی دیتابیس", callback_data="adm_restore_db_prompt")],
        [InlineKeyboardButton("📢 پیام همگانی به کانال", callback_data="adm_broadcast_btn")],
        [InlineKeyboardButton("♻️ ریست کامل بازی", callback_data="adm_reset_confirm")],
        [InlineKeyboardButton("🏠 بازگشت به منوی بازی", callback_data="home")]
    ]
    if edit:
        return await safe_edit(target, txt, reply_markup=kb(buttons))
    return await target.reply_text(txt, reply_markup=kb(buttons), parse_mode="HTML")

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass

    uid = q.from_user.id
    data = q.data

    if data == "noop": return

    p = player(uid)
    if p and p["is_banned"]: return

    # --- پنل مدیریت ---
    if data == "admin_panel":
        if not is_admin(uid): return
        return await show_admin_panel(q, edit=True)

    if data == "adm_toggle_peace":
        if not is_admin(uid): return
        curr = get_setting("peace_time", "0")
        new_val = "0" if curr == "1" else "1"
        set_setting("peace_time", new_val)
        status_msg = "🕊 زمان صلح عمومی در سراسر نقشه فعال شد! (حملات مستقیم متوقف شدند)" if new_val == "1" else "⚔️ زمان صلح به پایان رسید! حملات نظامی مستقیم آزاد شدند."
        await publish(context, f"📢 <b>بیانیه مدیریت سرور:</b>\n\n{status_msg}")
        return await show_admin_panel(q, edit=True)

    if data == "adm_get_db":
        if not is_admin(uid): return
        if os.path.exists(config.DB_PATH):
            with open(config.DB_PATH, "rb") as doc:
                await context.bot.send_document(
                    chat_id=uid,
                    document=doc,
                    caption=f"📦 فایل پشتیبان دیتابیس سرور ({time.strftime('%Y-%m-%d %H:%M:%S')})"
                )
            return await q.message.reply_text("✅ فایل بکاپ ارسال شد.", reply_markup=main_kb(uid))
        return await q.message.reply_text("❌ دیتابیس یافت نشد.")

    if data == "adm_restore_db_prompt":
        if not is_admin(uid): return
        context.user_data["await"] = "upload_db_file"
        return await safe_edit(
            q,
            "📤 لطفاً فایل <code>database.db</code> را ارسال کنید:",
            reply_markup=kb([[InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]])
        )

    if data == "adm_view_players":
        if not is_admin(uid): return
        c = conn()
        try:
            rs = c.execute("SELECT p.user_id, p.name, c.name cn, p.is_banned FROM players p LEFT JOIN countries c ON c.id=p.country_id").fetchall()
        finally:
            c.close()
        txt = "👥 <b>فهرست بازیکنان:</b>\n\n"
        if rs:
            txt += "\n".join(f"• {r['name']} (<code>{r['user_id']}</code>) | {r['cn'] or 'بدون کشور'} | مسدود: {r['is_banned']}" for r in rs)
        else:
            txt += "هیچ بازیکنی وجود ندارد."
        return await safe_edit(q, txt, reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))

    if data == "adm_view_countries":
        if not is_admin(uid): return
        c = conn()
        try:
            rs = c.execute("SELECT id, name, gold, oil, iron, food, population, player_id FROM countries").fetchall()
        finally:
            c.close()
        txt = "📊 <b>وضعیت کشورها:</b>\n\n"
        for r in rs:
            active_info = "🟢 بازیکن دارد" if r["player_id"] else "⚪ بدون بازیکن"
            txt += f"🚩 #{r['id']} <b>{r['name']}</b> ({active_info}):\n💰{r['gold']:,} | 🛢{r['oil']:,} | ⛓{r['iron']:,} | 🌾{r['food']:,}\n"
        return await safe_edit(q, txt, reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))

    if data == "adm_give_res_step1":
        if not is_admin(uid): return
        c = conn()
        try:
            cs = c.execute("SELECT id, flag, name FROM countries WHERE player_id IS NOT NULL").fetchall()
        finally:
            c.close()
        if not cs:
            return await safe_edit(q, "هیچ کشوری دارای بازیکن فعال نیست!", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))
        buttons = [[InlineKeyboardButton(f"{r['flag']} {r['name']}", callback_data=f"adm_gr_c:{r['id']}")] for r in cs]
        buttons.append([InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")])
        return await safe_edit(q, "کشور مقصد دریافت منبع:", reply_markup=kb(buttons))

    if data.startswith("adm_gr_c:"):
        if not is_admin(uid): return
        cid = int(data.split(":")[1])
        context.user_data["adm_target_cid"] = cid
        buttons = [
            [InlineKeyboardButton("💰 طلا", callback_data="adm_gr_res:gold"), InlineKeyboardButton("🛢 نفت", callback_data="adm_gr_res:oil")],
            [InlineKeyboardButton("⛓ آهن", callback_data="adm_gr_res:iron"), InlineKeyboardButton("🌾 غذا", callback_data="adm_gr_res:food")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]
        ]
        return await safe_edit(q, "نوع منبع اهدایی:", reply_markup=kb(buttons))

    if data.startswith("adm_gr_res:"):
        if not is_admin(uid): return
        res = data.split(":")[1]
        context.user_data["adm_target_res"] = res
        context.user_data["await"] = "adm_res_amt"
        return await safe_edit(q, f"مقدار ({res}) را به عدد ارسال فرمایید:")

    if data == "adm_give_units_step1":
        if not is_admin(uid): return
        c = conn()
        try:
            cs = c.execute("SELECT id, flag, name FROM countries WHERE player_id IS NOT NULL").fetchall()
        finally:
            c.close()
        if not cs:
            return await safe_edit(q, "هیچ کشوری بازیکن ندارد!", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))
        buttons = [[InlineKeyboardButton(f"{r['flag']} {r['name']}", callback_data=f"adm_gu_c:{r['id']}")] for r in cs]
        buttons.append([InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")])
        return await safe_edit(q, "کشور مقصد برای اهدای ارتش:", reply_markup=kb(buttons))

    if data.startswith("adm_gu_c:"):
        if not is_admin(uid): return
        cid = int(data.split(":")[1])
        context.user_data["adm_target_cid"] = cid
        c = conn()
        try:
            regs = c.execute("SELECT id, name FROM regions WHERE country_id=?", (cid,)).fetchall()
        finally:
            c.close()
        buttons = [[InlineKeyboardButton(f"📍 {r['name']}", callback_data=f"adm_gu_reg:{r['id']}")] for r in regs]
        buttons.append([InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")])
        return await safe_edit(q, "منطقه استقرار ارتش:", reply_markup=kb(buttons))

    if data.startswith("adm_gu_reg:"):
        if not is_admin(uid): return
        rid = int(data.split(":")[1])
        context.user_data["adm_target_rid"] = rid
        buttons = [
            [InlineKeyboardButton("🪖 سرباز", callback_data="adm_gu_u:soldier"), InlineKeyboardButton("🚁 هلیکوپتر", callback_data="adm_gu_u:helicopter")],
            [InlineKeyboardButton("🚢 ناو", callback_data="adm_gu_u:warship")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]
        ]
        return await safe_edit(q, "نوع واحد نظامی:", reply_markup=kb(buttons))

    if data.startswith("adm_gu_u:"):
        if not is_admin(uid): return
        utype = data.split(":")[1]
        context.user_data["adm_target_utype"] = utype
        context.user_data["await"] = "adm_unit_amt"
        return await safe_edit(q, "تعداد نیرو را ارسال کنید:")

    if data == "adm_broadcast_btn":
        if not is_admin(uid): return
        context.user_data["await"] = "adm_bcast_text"
        return await safe_edit(q, "متن پیام همگانی مدیریت برای کانال را ارسال کنید:")

    if data == "adm_reset_confirm":
        if not is_admin(uid): return
        buttons = [
            [InlineKeyboardButton("⚠️ بله، کاملاً ریست شود", callback_data="adm_reset_do")],
            [InlineKeyboardButton("🔙 خیر، انصراف", callback_data="admin_panel")]
        ]
        return await safe_edit(q, "آیا از ریست کامل سرور اطمینان دارید؟", reply_markup=kb(buttons))

    if data == "adm_reset_do":
        if not is_admin(uid): return
        c = conn()
        try:
            for t in ("armies", "spies", "wars", "war_forces", "factories", "caravans", "statements", "players"):
                c.execute(f"DELETE FROM {t}")
            c.execute("UPDATE countries SET player_id=NULL")
            c.execute("UPDATE regions SET owner_country_id=country_id")
            c.commit()
        finally:
            c.close()
        return await safe_edit(q, "♻️ سرور بازی ریست شد.", reply_markup=kb([[InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin_panel")]]))

    # --- بخش‌های بازی عمومی ---
    if data.startswith("join_info:"):
        cid = int(data.split(":")[1])
        fac = config.FACTIONS[cid]
        txt = (
            f"🎯 <b>معرفی {fac['flag']} {fac['name']}</b>\n\n"
            f"📌 {fac['desc']}\n\n"
            f"⚔️ <b>قوای اولیه مستقر در پایتخت:</b>\n"
            f"• پیاده‌نظام: {fac['init_army'].get('soldier', 0):,}\n"
            f"• هلیکوپتر: {fac['init_army'].get('helicopter', 0):,}\n"
            f"• ناو جنگی: {fac['init_army'].get('warship', 0):,}\n"
            f"• نفوذی: {fac['init_army'].get('spy', 0):,}\n\n"
            f"آیا هدایت این جناح را به عهده می‌گیرید؟"
        )
        buttons = [
            [InlineKeyboardButton("✅ انتخاب و ورود به بازی", callback_data=f"join_confirm:{cid}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="join_back")]
        ]
        return await safe_edit(q, txt, reply_markup=kb(buttons))

    if data == "join_back":
        return await safe_edit(q, "یک جناح را انتخاب کنید:", reply_markup=selection_buttons())

    if data.startswith("join_confirm:"):
        cid = int(data.split(":")[1])
        c = conn()
        try:
            row = c.execute("SELECT * FROM countries WHERE id=? AND player_id IS NULL", (cid,)).fetchone()
            if not row:
                return await safe_edit(q, "این جناح قبلاً انتخاب شده است!")
            c.execute("UPDATE countries SET player_id=? WHERE id=?", (uid, cid))
            c.execute("UPDATE players SET country_id=? WHERE user_id=?", (cid, uid))
            c.commit()
        finally:
            c.close()

        fac = config.FACTIONS[cid]
        await publish(context, f"🌐 <b>کشور جدید رسمیت یافت!</b>\nجناح {fac['flag']} <b>{fac['name']}</b> فعال شد.")
        return await send_dashboard(q, cid, uid=uid, edit=True)

    if not p or not p["country_id"]:
        return await safe_edit(q, "ابتدا با /start جناح خود را مشخص کنید.")

    cid = p["country_id"]
    ctry = country(cid)

    if data in ("home", "refresh_dashboard"):
        return await send_dashboard(q, cid, uid=uid, edit=True)

    if data == "resources":
        return await safe_edit(q, f"📦 <b>ذخایر ملی:</b>\n\n{fmt_resources(ctry)}", reply_markup=main_kb(uid))

    if data == "map":
        return await safe_edit(
            q,
            "🗺 <b>نقشه قلمرو:</b>\n🟢 = قلمرو شما | 🔴 = مناطق رقیب\nروی منطقه کلیک کنید:",
            reply_markup=map_keyboard(cid)
        )

    if data == "buy_army_menu":
        txt = (
            "⚔️ <b>مرکز خرید مستقیم ارتش:</b>\n\n"
            "واحد مورد نظر را انتخاب و سپس <b>تعداد را تایپ کنید</b>:\n\n"
            "• <b>سرباز:</b> 👥۱۰ | 💰۲۰ طلا | ⛓۳۰ آهن\n"
            "• <b>هلیکوپتر:</b> 👥۵۰ | 💰۲۰۰ طلا | ⛓۱۵۰ آهن | 🛢۱۰۰ نفت\n"
            "• <b>ناو جنگی:</b> 👥۱۰۰ | 💰۴۰۰ طلا | ⛓۵۰۰ آهن | 🛢۳۰۰ نفت\n"
            "• <b>جاسوس:</b> 👥۵ | 💰۵۰۰ طلا | ⛓۲۵۰ آهن | 🛢۱۰۰ نفت"
        )
        buttons = [
            [InlineKeyboardButton("🪖 سرباز", callback_data="buy_unit_select:soldier"),
             InlineKeyboardButton("🚁 هلیکوپتر", callback_data="buy_unit_select:helicopter")],
            [InlineKeyboardButton("🚢 ناو", callback_data="buy_unit_select:warship"),
             InlineKeyboardButton("🕵️ نفوذی", callback_data="buy_unit_select:spy")],
            [InlineKeyboardButton("🏠 داشبورد اصلی", callback_data="home")]
        ]
        return await safe_edit(q, txt, reply_markup=kb(buttons))

    if data.startswith("buy_unit_select:"):
        utype = data.split(":")[1]
        context.user_data["buy_unit_type"] = utype
        context.user_data["await"] = "buy_unit_count"
        uname = config.UNITS[utype]["name"]
        return await safe_edit(
            q,
            f"🛒 چه تعداد <b>{uname}</b> می‌خواهید خریداری کنید؟\n\nعدد را ارسال کنید:",
            reply_markup=kb([[InlineKeyboardButton("🔙 انصراف", callback_data="buy_army_menu")]])
        )

    if data == "wars":
        return await war_menu(q, cid)

    if data == "war_targets":
        return await war_targets_menu(q, cid)

    if data.startswith("attack_country:"):
        target_cid = int(data.split(":")[1])
        return await war_regions_select(q, cid, target_cid)

    if data.startswith("start_attack:"):
        _, rid_str, target_cid_str = data.split(":")
        rid = int(rid_str)
        target_cid = int(target_cid_str)
        ok, res = declare_war(cid, target_cid, rid)
        if ok:
            r_info = region(rid)
            def_country = country(target_cid)
            r_name = r_info['name'] if r_info else 'منطقه'
            d_name = def_country['name'] if def_country else 'دشمن'
            d_flag = def_country['flag'] if def_country else '🏴'
            await publish(
                context,
                f"🚨 <b>اعلان جنگ فوری!</b>\n"
                f"{ctry['flag']} <b>{ctry['name']}</b> به منطقه <b>{r_name}</b> از {d_flag} <b>{d_name}</b> حمله کرد!\n"
                f"شناسه جنگ: <code>{res}</code>"
            )
            return await safe_edit(
                q,
                f"⚔️ تهاجم آغاز شد!\nشناسه نبرد: <code>#{res}</code>",
                reply_markup=kb([[InlineKeyboardButton("🚩 اتاق عملیات جنگ", callback_data="wars")]])
            )
        else:
            return await safe_edit(q, f"❌ خطا: {res}", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="wars")]]))

    if data.startswith("war_reinforce:"):
        wid = int(data.split(":")[1])
        context.user_data["war_deploy_id"] = wid
        c = conn()
        try:
            w = c.execute("SELECT * FROM wars WHERE id=?", (wid,)).fetchone()
            my_regs = c.execute("SELECT id, name FROM regions WHERE owner_country_id=?", (cid,)).fetchall()
        finally:
            c.close()

        if not w: return await safe_edit(q, "این جنگ فعال نیست.")
        side = "attacker" if w["attacker_country_id"] == cid else "defender"
        context.user_data["war_deploy_side"] = side

        buttons = [[InlineKeyboardButton(f"📍 اعزام از {r['name']}", callback_data=f"war_dep_reg:{r['id']}")] for r in my_regs]
        buttons.append([InlineKeyboardButton("🔙 انصراف", callback_data="wars")])
        return await safe_edit(q, "نیروها از کدام منطقه اعزام شوند؟:", reply_markup=kb(buttons))

    if data.startswith("war_dep_reg:"):
        from_rid = int(data.split(":")[1])
        context.user_data["war_deploy_from_rid"] = from_rid

        buttons = [
            [InlineKeyboardButton("🪖 سرباز", callback_data="war_dep_u:soldier"),
             InlineKeyboardButton("🚁 هلیکوپتر", callback_data="war_dep_u:helicopter")],
            [InlineKeyboardButton("🚢 ناو جنگی", callback_data="war_dep_u:warship")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="wars")]
        ]
        return await safe_edit(q, "کدام نیرو را اعزام می‌کنید؟", reply_markup=kb(buttons))

    if data.startswith("war_dep_u:"):
        utype = data.split(":")[1]
        context.user_data["war_deploy_utype"] = utype
        context.user_data["await"] = "war_deploy_amount"
        uname = config.UNITS[utype]["name"]
        return await safe_edit(q, f"چه تعداد <b>{uname}</b> اعزام شود؟ عدد را بفرستید:")

    if data.startswith("transfer_start:"):
        from_rid = int(data.split(":")[1])
        context.user_data["transfer_from"] = from_rid
        c = conn()
        try:
            my_regs = c.execute("SELECT id, name FROM regions WHERE owner_country_id=? AND id!=?", (cid, from_rid)).fetchall()
        finally:
            c.close()
        if not my_regs:
            return await safe_edit(q, "منطقه دیگری ندارید!", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"region:{from_rid}")]]))

        buttons = [[InlineKeyboardButton(f"📍 به {r['name']}", callback_data=f"transfer_dest:{r['id']}")] for r in my_regs]
        buttons.append([InlineKeyboardButton("🔙 انصراف", callback_data=f"region:{from_rid}")])
        return await safe_edit(q, "مقصد جابه‌جایی را انتخاب کنید:", reply_markup=kb(buttons))

    if data.startswith("transfer_dest:"):
        dest_rid = int(data.split(":")[1])
        context.user_data["transfer_dest"] = dest_rid
        from_rid = context.user_data.get("transfer_from")

        buttons = [
            [InlineKeyboardButton("🪖 سرباز", callback_data="transfer_unit:soldier"),
             InlineKeyboardButton("🚁 هلیکوپتر", callback_data="transfer_unit:helicopter")],
            [InlineKeyboardButton("🚢 ناو", callback_data="transfer_unit:warship")],
            [InlineKeyboardButton("🔙 انصراف", callback_data=f"region:{from_rid}")]
        ]
        return await safe_edit(q, "کدام یگان منتقل شود؟", reply_markup=kb(buttons))

    if data.startswith("transfer_unit:"):
        utype = data.split(":")[1]
        context.user_data["transfer_unit"] = utype
        context.user_data["await"] = "transfer_amount"
        uname = config.UNITS[utype]["name"]
        return await safe_edit(q, f"چه تعداد <b>{uname}</b> جابه‌جا شوند؟ عدد را بفرستید:")

    if data.startswith("region:"):
        rid = int(data.split(":")[1])
        return await region_menu(q, cid, rid)

    if data.startswith("build_factory_reg:"):
        _, kind, rid_str = data.split(":")
        rid = int(rid_str)
        ok, msg = build_factory(cid, rid, kind, 1)
        return await safe_edit(
            q,
            ("✅ " if ok else "❌ ") + msg,
            reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت به منطقه", callback_data=f"region:{rid}")]])
        )

    if data == "factories":
        return await factory_menu(q, cid)

    if data == "caravan":
        return await caravan_menu(q, cid)

    if data == "caravan_create":
        return await caravan_select_target(q, cid)

    if data.startswith("cartarget:"):
        target_country_id = int(data.split(":")[1])
        context.user_data["car_to"] = target_country_id
        buttons = [
            [InlineKeyboardButton("💰 طلا", callback_data="car_type:gold"), InlineKeyboardButton("🛢 نفت", callback_data="car_type:oil")],
            [InlineKeyboardButton("⛓ آهن", callback_data="car_type:iron"), InlineKeyboardButton("🌾 غذا", callback_data="car_type:food")],
            [InlineKeyboardButton("🪖 سرباز", callback_data="car_type:soldier"), InlineKeyboardButton("🚁 هلیکوپتر", callback_data="car_type:helicopter")],
            [InlineKeyboardButton("🚢 ناو", callback_data="car_type:warship"), InlineKeyboardButton("🕵️ نفوذی", callback_data="car_type:spy")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="caravan")]
        ]
        return await safe_edit(q, "نوع محموله کاروان تجاری یا تهاجمی را انتخاب کنید:", reply_markup=kb(buttons))

    if data.startswith("car_type:"):
        k = data.split(":")[1]
        context.user_data["cargo_kind"] = k
        context.user_data["await"] = "cargo_amount"
        return await safe_edit(q, f"مقدار یا تعداد محموله <b>{k}</b> را ارسال کنید:")

    if data == "statement":
        context.user_data["await"] = "statement"
        return await safe_edit(
            q,
            "📢 بیانیه رسمی خود را ارسال فرمایید (مستقیماً در کانال منتشر خواهد شد):",
            reply_markup=kb([[InlineKeyboardButton("🔙 انصراف", callback_data="home")]])
        )

async def region_menu(q, cid, rid):
    r = region(rid)
    if not r: return await safe_edit(q, "منطقه پیدا نشد.")

    txt = region_text(cid, rid)
    buttons = []
    fac_info = config.FACTIONS.get(cid, {})
    owner = country(r["owner_country_id"])

    if r["owner_country_id"] == cid:
        buttons.append([InlineKeyboardButton("🔄 انتقال نیرو به منطقه دیگر", callback_data=f"transfer_start:{rid}")])
        if fac_info.get("type") == "country":
            txt += "\n<b>🏭 احداث کارخانه:</b>\n"
            b_row = []
            for k, spec in config.FACTORIES.items():
                b_row.append(InlineKeyboardButton(f"➕ {spec['name']}", callback_data=f"build_factory_reg:{k}:{rid}"))
                if len(b_row) == 2:
                    buttons.append(b_row)
                    b_row = []
            if b_row: buttons.append(b_row)
    else:
        if owner and owner["player_id"]:
            buttons.append([InlineKeyboardButton("⚔️ حمله به این منطقه", callback_data=f"start_attack:{rid}:{r['owner_country_id']}")])
        else:
            txt += "\n⚠️ <i>این کشور هنوز بدون حاکم است و امکان تهاجم به آن وجود ندارد.</i>"

    buttons.append([InlineKeyboardButton("🔙 بازگشت به نقشه", callback_data="map")])
    return await safe_edit(q, txt, reply_markup=kb(buttons))

async def war_menu(q, cid):
    c = conn()
    try:
        rows = c.execute(
            "SELECT w.*, r.name rn, d.name dn, a.name an FROM wars w "
            "JOIN regions r ON r.id=w.region_id "
            "JOIN countries d ON d.id=w.defender_country_id "
            "JOIN countries a ON a.id=w.attacker_country_id "
            "WHERE (w.attacker_country_id=? OR w.defender_country_id=?) AND w.status='active'",
            (cid, cid)
        ).fetchall()
    finally:
        c.close()

    now = int(time.time())
    buttons = []
    txt = "🚩 <b>اتاق عملیات جنگ:</b>\n\n"
    if rows:
        for r in rows:
            rem = max(0, r['ends_at'] - now) // 60
            txt += (
                f"⚔️ <b>نبرد #{r['id']} در {r['rn']}</b>\n"
                f"مهاجم: <b>{r['an']}</b> | مدافع: <b>{r['dn']}</b>\n"
                f"زمان باقی‌مانده: <b>{rem} دقیقه</b>\n\n"
            )
            buttons.append([InlineKeyboardButton(f"➕ اعزام نیرو به نبرد #{r['id']}", callback_data=f"war_reinforce:{r['id']}")])
    else:
        txt += "در حال حاضر درگیر هیچ نبردی نیستید.\n"

    buttons.append([InlineKeyboardButton("⚔️ تهاجم و حمله جدید", callback_data="war_targets")])
    buttons.append([InlineKeyboardButton("🏠 بازگشت به داشبورد", callback_data="home")])
    return await safe_edit(q, txt, reply_markup=kb(buttons))

async def war_targets_menu(q, cid):
    c = conn()
    try:
        targets = c.execute("SELECT id, flag, name FROM countries WHERE id!=? AND player_id IS NOT NULL AND eliminated=0", (cid,)).fetchall()
    finally:
        c.close()

    if not targets:
        return await safe_edit(
            q,
            "⚠️ در حال حاضر هیچ کشور رقیبی با بازیکن فعال در بازی وجود ندارد!",
            reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="wars")]])
        )

    buttons = [[InlineKeyboardButton(f"{r['flag']} {r['name']}", callback_data=f"attack_country:{r['id']}")] for r in targets]
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="wars")])
    return await safe_edit(q, "کشور فعال مورد نظر جهت تهاجم را انتخاب کنید:", reply_markup=kb(buttons))

async def war_regions_select(q, cid, target_cid):
    c = conn()
    try:
        t_country = c.execute("SELECT name, flag FROM countries WHERE id=?", (target_cid,)).fetchone()
        r_rows = c.execute("SELECT id, name FROM regions WHERE owner_country_id=?", (target_cid,)).fetchall()
    finally:
        c.close()

    if not r_rows:
        return await safe_edit(q, "این کشور منطقه‌ای ندارد!", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="war_targets")]]))

    buttons = [
        [InlineKeyboardButton(f"🎯 تهاجم به منطقه {r['name']}", callback_data=f"start_attack:{r['id']}:{target_cid}")]
        for r in r_rows
    ]
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="war_targets")])
    t_flag = t_country['flag'] if t_country else '🏴'
    t_name = t_country['name'] if t_country else 'کشور'
    return await safe_edit(q, f"کدام منطقه از {t_flag} <b>{t_name}</b> مورد حمله قرار گیرد؟", reply_markup=kb(buttons))

async def factory_menu(q, cid):
    c = conn()
    try:
        rows = c.execute(
            "SELECT r.name, f.kind, COUNT(*) n FROM factories f JOIN regions r ON r.id=f.region_id "
            "WHERE r.owner_country_id=? GROUP BY r.id, f.kind", (cid,)
        ).fetchall()
    finally:
        c.close()

    txt = "🏭 <b>مراکز تولیدی و کارخانه‌ها:</b>\n\n"
    if rows:
        txt += "\n".join(f"📍 {r['name']}: {config.FACTORIES[r['kind']]['name']} × {r['n']}" for r in rows)
    else:
        txt += "هیچ کارخانه‌ای در قلمرو ندارید."

    return await safe_edit(
        q,
        txt,
        reply_markup=kb([[InlineKeyboardButton("🗺 نقشه و احداث", callback_data="map")], [InlineKeyboardButton("🏠 داشبورد", callback_data="home")]])
    )

async def caravan_menu(q, cid):
    c = conn()
    try:
        rows = c.execute(
            "SELECT v.*, s.name sn, r.name rn FROM caravans v "
            "JOIN countries s ON s.id=v.sender_country_id "
            "JOIN countries r ON r.id=v.receiver_country_id "
            "WHERE v.sender_country_id=? OR v.receiver_country_id=? "
            "ORDER BY v.id DESC LIMIT 5",
            (cid, cid)
        ).fetchall()
    finally:
        c.close()

    txt = "🚚 <b>سیستم بازرگانی و کاروان:</b>\n\n"
    txt += "<i>کاروان‌ها در تمام زمان‌ها (حتی زمان صلح) قابل ارسال هستند.</i>\n\n"
    if rows:
        txt += "\n".join(f"#{r['id']} {r['sn']} ➔ {r['rn']} | {r['cargo_amount']:,} {r['cargo_kind']} ({r['status']})" for r in rows)
    else:
        txt += "هیچ کاروانی در حرکت نیست."

    buttons = [
        [InlineKeyboardButton("🚚 اعزام کاروان جدید", callback_data="caravan_create")],
        [InlineKeyboardButton("🏠 بازگشت به داشبورد", callback_data="home")]
    ]
    return await safe_edit(q, txt, reply_markup=kb(buttons))

async def caravan_select_target(q, cid):
    c = conn()
    try:
        countries = c.execute("SELECT id, flag, name FROM countries WHERE id!=? AND player_id IS NOT NULL AND eliminated=0", (cid,)).fetchall()
    finally:
        c.close()

    if not countries:
        return await safe_edit(q, "⚠️ کشور دیگری با بازیکن فعال در بازی حضور ندارد!", reply_markup=kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="caravan")]]))

    buttons = [[InlineKeyboardButton(f"{r['flag']} {r['name']}", callback_data=f"cartarget:{r['id']}")] for r in countries]
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="caravan")])
    return await safe_edit(q, "مقصد کاروان را مشخص کنید:", reply_markup=kb(buttons))

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return

    st = context.user_data.get("await")
    if st == "upload_db_file":
        doc = update.message.document
        if not doc.file_name.endswith(".db"):
            return await update.message.reply_text("❌ لطفاً یک فایل با پسوند .db ارسال کنید.")
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(config.DB_PATH)
        context.user_data.pop("await", None)
        return await update.message.reply_text("✅ دیتابیس با موفقیت جایگزین و لود شد.", reply_markup=main_kb(uid))

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    p = player(uid)
    if not p or p["is_banned"]: return

    st = context.user_data.get("await")

    if st == "adm_bcast_text" and is_admin(uid):
        text = update.message.text.strip()
        context.user_data.pop("await", None)
        ok, err = await publish(context, f"📢 <b>پیام رسمی مدیریت سرور:</b>\n\n{text}")
        if ok:
            return await update.message.reply_text("✅ پیام همگانی ارسال شد.", reply_markup=main_kb(uid))
        else:
            return await update.message.reply_text(f"❌ ارسال ناموفق:\n{err}", reply_markup=main_kb(uid))

    if st == "adm_res_amt" and is_admin(uid):
        try:
            amt = int(update.message.text.strip())
        except:
            return await update.message.reply_text("❌ عدد نامعتبر است.")
        cid = context.user_data.pop("adm_target_cid", None)
        res = context.user_data.pop("adm_target_res", None)
        context.user_data.pop("await", None)
        if not cid or not res:
            return await update.message.reply_text("❌ فرآیند منقضی شده است.")
        c = conn()
        try:
            c.execute(f"UPDATE countries SET {res}={res}+? WHERE id=?", (amt, cid))
            c.commit()
        finally:
            c.close()
        return await update.message.reply_text(f"✅ مقدار {amt:,} {res} به کشور #{cid} اهدا شد.", reply_markup=main_kb(uid))

    if st == "adm_unit_amt" and is_admin(uid):
        try:
            amt = int(update.message.text.strip())
        except:
            return await update.message.reply_text("❌ عدد نامعتبر است.")
        cid = context.user_data.pop("adm_target_cid", None)
        rid = context.user_data.pop("adm_target_rid", None)
        utype = context.user_data.pop("adm_target_utype", None)
        context.user_data.pop("await", None)
        if not cid or not rid or not utype:
            return await update.message.reply_text("❌ فرآیند منقضی شده است.")
        c = conn()
        try:
            old = c.execute("SELECT id FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND unit_type=?", (cid, rid, utype)).fetchone()
            if old:
                c.execute("UPDATE armies SET amount=amount+? WHERE id=?", (amt, old["id"]))
            else:
                c.execute("INSERT INTO armies(owner_type, owner_id, region_id, unit_type, amount) VALUES('country', ?, ?, ?, ?)", (cid, rid, utype, amt))
            c.commit()
        finally:
            c.close()
        return await update.message.reply_text(f"✅ تعداد {amt:,} {utype} با موفقیت افزوده شد.", reply_markup=main_kb(uid))

    if st == "cargo_amount":
        try:
            amt = int(update.message.text.strip())
            if amt <= 0: raise ValueError()
        except:
            return await update.message.reply_text("❌ یک عدد مثبت وارد کنید.")
        to = context.user_data.pop("car_to", None)
        k = context.user_data.pop("cargo_kind", None)
        context.user_data.pop("await", None)
        if not to or not k:
            return await update.message.reply_text("❌ عملیات نامعتبر است.")

        cid = p["country_id"]
        c = conn()
        try:
            target = c.execute("SELECT id FROM regions WHERE country_id=? LIMIT 1", (to,)).fetchone()
            now = int(time.time())
            c.execute(
                "INSERT INTO caravans(sender_country_id, receiver_country_id, from_region_id, to_region_id, status, cargo_kind, cargo_amount, departed_at, arrive_at) "
                "VALUES(?, ?, 1, ?, 'moving', ?, ?, ?, ?)",
                (cid, to, target["id"], k, amt, now, now + 15 * 60)
            )
            c.commit()
        finally:
            c.close()
        return await update.message.reply_text(f"🚚 کاروان حامل {amt:,} واحد {k} اعزام شد و ۱۵ دقیقه دیگر می‌رسد.", reply_markup=main_kb(uid))

    if st == "war_deploy_amount":
        try:
            amt = int(update.message.text.strip())
            if amt <= 0: raise ValueError()
        except:
            return await update.message.reply_text("❌ لطفاً یک عدد مثبت تایپ کنید.")

        wid = context.user_data.pop("war_deploy_id", None)
        side = context.user_data.pop("war_deploy_side", None)
        from_rid = context.user_data.pop("war_deploy_from_rid", None)
        utype = context.user_data.pop("war_deploy_utype", None)
        context.user_data.pop("await", None)

        if not all([wid, side, from_rid, utype]):
            return await update.message.reply_text("❌ فرآیند منقضی شده است. مجدداً از منوی جنگ اقدام کنید.", reply_markup=main_kb(uid))

        ok, msg = add_force(wid, side, p["country_id"], from_rid, utype, amt)
        return await update.message.reply_text(("✅ " if ok else "❌ ") + msg, reply_markup=main_kb(uid))

    if st == "buy_unit_count":
        try:
            amt = int(update.message.text.strip())
            if amt <= 0: raise ValueError()
        except:
            return await update.message.reply_text("❌ لطفاً عدد صحیح مثبت تایپ کنید.")

        utype = context.user_data.pop("buy_unit_type", None)
        context.user_data.pop("await", None)
        if not utype:
            return await update.message.reply_text("❌ عملیات منقضی شده است.")

        cid = p["country_id"]
        u = config.UNITS[utype]
        total_pop = u["population"] * amt
        total_gold = u["gold"] * amt
        total_iron = u["iron"] * amt
        total_oil = u["oil"] * amt

        c = conn()
        try:
            co = c.execute("SELECT * FROM countries WHERE id=?", (cid,)).fetchone()
            cap = c.execute("SELECT id FROM regions WHERE owner_country_id=? AND code='capital'", (cid,)).fetchone()

            if not cap:
                return await update.message.reply_text("❌ پایتخت در اشغال است!")

            if co["population"] < total_pop or co["gold"] < total_gold or co["iron"] < total_iron or co["oil"] < total_oil:
                return await update.message.reply_text(
                    f"❌ منابع کافی نیست!\n"
                    f"نیاز: 👥 {total_pop} | 💰 {total_gold} | ⛓ {total_iron} | 🛢 {total_oil}\n"
                    f"موجودی: 👥 {co['population']} | 💰 {co['gold']} | ⛓ {co['iron']} | 🛢 {co['oil']}"
                )

            c.execute(
                "UPDATE countries SET population=population-?, gold=gold-?, iron=iron-?, oil=oil-? WHERE id=?",
                (total_pop, total_gold, total_iron, total_oil, cid)
            )

            if utype == "spy":
                for _ in range(amt):
                    c.execute("INSERT INTO spies(owner_country_id, region_id, status, created_at) VALUES(?, ?, 'ready', ?)",
                              (cid, cap["id"], int(time.time())))
            else:
                old = c.execute("SELECT id FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND unit_type=?",
                                (cid, cap["id"], utype)).fetchone()
                if old:
                    c.execute("UPDATE armies SET amount=amount+? WHERE id=?", (amt, old["id"]))
                else:
                    c.execute("INSERT INTO armies(owner_type, owner_id, region_id, unit_type, amount) VALUES('country', ?, ?, ?, ?)",
                              (cid, cap["id"], utype, amt))

            c.commit()
            return await update.message.reply_text(
                f"✅ تعداد <b>{amt:,}</b> واحد <b>{u['name']}</b> در پایتخت مستقر شد.",
                reply_markup=main_kb(uid),
                parse_mode="HTML"
            )
        finally:
            c.close()

    if st == "transfer_amount":
        try:
            amt = int(update.message.text.strip())
            if amt <= 0: raise ValueError()
        except:
            return await update.message.reply_text("❌ عدد صحیح بفرستید.")

        from_rid = context.user_data.pop("transfer_from", None)
        dest_rid = context.user_data.pop("transfer_dest", None)
        utype = context.user_data.pop("transfer_unit", None)
        context.user_data.pop("await", None)

        if not from_rid or not dest_rid or not utype:
            return await update.message.reply_text("❌ اطلاعات جابه‌جایی نامعتبر است.")

        cid = p["country_id"]
        c = conn()
        try:
            row = c.execute("SELECT id, amount FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND unit_type=?",
                            (cid, from_rid, utype)).fetchone()

            if not row or row["amount"] < amt:
                return await update.message.reply_text("❌ نیروی مستقر کافی نیست.")

            c.execute("UPDATE armies SET amount=amount-? WHERE id=?", (amt, row["id"]))
            c.execute("DELETE FROM armies WHERE id=? AND amount<=0", (row["id"],))

            dest = c.execute("SELECT id FROM armies WHERE owner_type='country' AND owner_id=? AND region_id=? AND unit_type=?",
                             (cid, dest_rid, utype)).fetchone()
            if dest:
                c.execute("UPDATE armies SET amount=amount+? WHERE id=?", (amt, dest["id"]))
            else:
                c.execute("INSERT INTO armies(owner_type, owner_id, region_id, unit_type, amount) VALUES('country', ?, ?, ?, ?)",
                          (cid, dest_rid, utype, amt))

            r_dest = c.execute("SELECT name FROM regions WHERE id=?", (dest_rid,)).fetchone()
            c.commit()
            return await update.message.reply_text(
                f"✅ تعداد <b>{amt:,}</b> {config.UNITS[utype]['name']} به <b>{r_dest['name']}</b> اعزام شد.",
                reply_markup=main_kb(uid),
                parse_mode="HTML"
            )
        finally:
            c.close()

    if st == "statement":
        text = update.message.text.strip()
        co = my_country(uid)
        context.user_data.pop("await", None)
        if not co: return
        msg = f"📢 <b>بیانیه رسمی {co['flag']} {co['name']}:</b>\n\n{text}"
        ok, err = await publish(context, msg)
        if ok:
            return await update.message.reply_text("📢 بیانیه رسمی شما در کانال منتشر گردید.", reply_markup=main_kb(uid))
        else:
            return await update.message.reply_text(f"❌ بیانیه ارسال نشد!\nعلت: <code>{err}</code>", reply_markup=main_kb(uid), parse_mode="HTML")

async def publish(context, text):
    if not config.NEWS_CHANNEL_ID:
        return False, "شناسه کانال در config.py تنظیم نشده است."
    try:
        await context.bot.send_message(config.NEWS_CHANNEL_ID, text, parse_mode="HTML")
        return True, None
    except Exception as e:
        return False, str(e)

async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(config.DB_PATH) and config.ADMIN_IDS:
        try:
            main_admin = config.ADMIN_IDS[0]
            with open(config.DB_PATH, "rb") as doc:
                await context.bot.send_document(
                    chat_id=main_admin,
                    document=doc,
                    caption="🔄 بکاپ خودکار دوره‌ای دیتابیس سرور"
                )
        except Exception as e:
            log("error", f"Auto backup error: {e}")

async def background(context: ContextTypes.DEFAULT_TYPE):
    try:
        catch_up()
        results = process_wars()
        for r in results:
            if not r: continue
            rg = region(r.get("region"))
            r_name = rg["name"] if rg else "منطقه"
            w_country = country(r.get("winner")) if r.get("winner") else None
            wname = w_country["name"] if w_country else "مساوی و عقب‌نشینی قوا"
            msg = f"⚔️ <b>پایان جنگ در منطقه {r_name}:</b>\nمهاجم: {r['ap']:.1f} | مدافع: {r['dp']:.1f} | برنده: <b>{wname}</b>"
            log("battle", msg)
            await publish(context, msg)
    except Exception as e:
        log("error", f"background task error: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log("error", f"Update {update} caused error {context.error}")
    print(f"[Handled Error]: {context.error}")

async def setup_commands(application):
    commands = [
        BotCommand("start", "شروع مجدد و راه‌اندازی بازی"),
        BotCommand("menu", "نمایش داشبورد کامل"),
        BotCommand("admin", "پنل مدیریت و زمان صلح")
    ]
    await application.bot.set_my_commands(commands)

def main():
    app = Application.builder().token(config.BOT_TOKEN).post_init(setup_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("admin", admin_panel_cmd))

    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(background, interval=60, first=10)
    app.job_queue.run_repeating(auto_backup_job, interval=1800, first=120)

    print("WorldWarBot started successfully.")
    app.run_polling()

if __name__ == "__main__":
    main()
