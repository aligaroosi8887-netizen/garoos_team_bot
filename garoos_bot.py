# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import math
import logging
import datetime

logging.basicConfig(level=logging.INFO)

# ---------- تنظیمات ----------
ADMIN_ID = 130197808               # شناسه مدیر
CHAT_ID = -1002655310937           # شناسه گروه
TOPIC_THREAD_ID = 40               # شناسه موضوع "هزینه کافه"
REMINDER_INTERVAL_SECONDS = 60*60*12  # یادآوری هر 12 ساعت
# --------------------------------

members = []
current_session = {
    "active_members": [],
    "total_cost": 0,
    "description": "",
    "per_person": 0,
    "payments": {},
    "reminder_job": None,
    "settled": False,
}

# ---------- توابع کمکی ----------
def parse_amount(s):
    try:
        return int(s.replace(",", ""))
    except:
        return None

def build_select_keyboard():
    kb = []
    for name in members:
        checked = "✅ " if name in current_session["active_members"] else ""
        kb.append([InlineKeyboardButton(f"{checked}{name}", callback_data=f"toggle|{name}")])
    kb.append([InlineKeyboardButton("تایید انتخاب‌ها ✅", callback_data="confirm_selection")])
    return InlineKeyboardMarkup(kb)

def build_status_text():
    if current_session["total_cost"] == 0:
        return "هیچ هزینه‌ای ثبت نشده."
    text = f"💰 هزینه: {current_session['total_cost']:,} تومان\n"
    if current_session["description"]:
        text += f"📝 توضیح: {current_session['description']}\n"
    text += f"👥 اعضا حاضر: {len(current_session['active_members'])}\n"
    text += f"📊 سهم هر نفر: {current_session['per_person']:,} تومان\n\n"
    text += "📋 وضعیت پرداخت:\n"
    for n in current_session["active_members"]:
        p = current_session["payments"].get(n, 0)
        text += f"• {n}: {p:,} / {current_session['per_person']:,}\n"
    total = sum(current_session["payments"].values())
    remain = current_session["total_cost"] - total
    text += f"\n💸 پرداخت‌شده: {total:,}\n🕓 مانده: {max(remain,0):,}"
    return text

async def send_in_topic(context, text):
    try:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            message_thread_id=TOPIC_THREAD_ID,
            text=text
        )
    except Exception as e:
        logging.warning(f"ارسال در موضوع خطا داد: {e}")

# ---------- دستورات ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ربات حساب‌گر هزینه کافه آماده است.\n\n"
        "دستورات:\n"
        "/addmember [نام] — اضافه کردن عضو\n"
        "/members — لیست اعضا\n"
        "/selectmembers — انتخاب اعضای حاضر در دوره\n"
        "/setcost [مبلغ] [توضیح و تاریخ] — ثبت هزینه\n"
        "/pay [نام] [مبلغ] — ثبت پرداخت\n"
        "/share — نمایش وضعیت پرداخت\n"
        "/reset — پاک کردن دوره و شروع جدید\n"
        "/gettopic — دریافت شناسه تاپیک"
    )

async def gettopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.is_topic_message:
        topic_id = update.message.message_thread_id
        await update.message.reply_text(f"📌 Topic ID این گفت‌وگو: {topic_id}")
    else:
        await update.message.reply_text("❗ این دستور را باید داخل یک تاپیک (topic) در گروه ارسال کنید.")

async def add_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت: /addmember علی")
        return
    name = " ".join(context.args)
    if name in members:
        await update.message.reply_text(f"{name} از قبل وجود دارد.")
        return
    members.append(name)
    await update.message.reply_text(f"✅ {name} افزوده شد.")

async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not members:
        await update.message.reply_text("لیست اعضا خالی است.")
        return
    text = "\n".join(f"{i+1}. {n}" for i,n in enumerate(members))
    await update.message.reply_text("👥 اعضا:\n"+text)

async def select_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not members:
        await update.message.reply_text("اول با /addmember اعضا را بساز.")
        return
    await update.message.reply_text(
        "✅ اعضای حاضر را تیک بزن:",
        reply_markup=build_select_keyboard(),
        message_thread_id=TOPIC_THREAD_ID
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data.startswith("toggle|"):
        name = data.split("|")[1]
        if name in current_session["active_members"]:
            current_session["active_members"].remove(name)
        else:
            current_session["active_members"].append(name)
        await q.edit_message_reply_markup(build_select_keyboard())
    elif data=="confirm_selection":
        current_session["payments"] = {n:0 for n in current_session["active_members"]}
        current_session["total_cost"] = 0
        current_session["settled"] = False
        await q.edit_message_text("✅ انتخاب اعضا ثبت شد. حالا /setcost مبلغ و توضیح را وارد کنید.")

async def set_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("فرمت: /setcost مبلغ توضیح و تاریخ")
        return
    amount = parse_amount(context.args[0])
    desc = " ".join(context.args[1:]) if len(context.args)>1 else ""
    if amount is None:
        await update.message.reply_text("مبلغ را درست وارد کنید.")
        return
    current_session["total_cost"] = amount
    current_session["description"] = desc
    current_session["per_person"] = math.ceil(amount/len(current_session["active_members"]))
    current_session["settled"] = False
    await update.message.reply_text(
        f"💰 {amount:,} ثبت شد ({desc})\nسهم هر نفر: {current_session['per_person']:,} تومان",
        message_thread_id=TOPIC_THREAD_ID
    )
    # یادآوری خودکار
    job = context.job_queue.run_repeating(reminder_job, REMINDER_INTERVAL_SECONDS, first=REMINDER_INTERVAL_SECONDS, data={"chat_id": CHAT_ID})
    current_session["reminder_job"] = job

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    if not current_session["total_cost"] or current_session["settled"]:
        return
    unpaid = []
    for n in current_session["active_members"]:
        p = current_session["payments"].get(n,0)
        if p < current_session["per_person"]:
            unpaid.append((n,current_session["per_person"]-p))
    if unpaid:
        text = "🔔 یادآوری پرداخت هزینه کافه:\n"
        for n,r in unpaid:
            text += f"• {n}: مانده {r:,}\n"
        await send_in_topic(context, text)

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("فرمت: /pay نام مبلغ")
        return
    name, amount = context.args[0], parse_amount(context.args[1])
    if name not in current_session["active_members"]:
        await update.message.reply_text("این فرد در لیست فعلی نیست.")
        return
    current_session["payments"][name] += amount
    text = build_status_text()
    total = sum(current_session["payments"].values())
    if total >= current_session["total_cost"]:
        current_session["settled"] = True
        await send_in_topic(context, f"✅ کل هزینه تسویه شد!\n\n{text}")
    else:
        await send_in_topic(context, f"💸 پرداخت ثبت شد ({name} — {amount:,})\n\n{text}")

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_status_text(), message_thread_id=TOPIC_THREAD_ID)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    for k in current_session.keys():
        if isinstance(current_session[k], (list,dict)):
            current_session[k].clear()
        elif isinstance(current_session[k], (int,bool)):
            current_session[k]=0 if isinstance(current_session[k],int) else False
    await update.message.reply_text("♻️ دوره پاک شد.", message_thread_id=TOPIC_THREAD_ID)

# ---------- راه‌اندازی ----------
if __name__=="__main__":
    app = ApplicationBuilder().token("8412760078:AAHXNbpPRleSxEqWdKubedI3YukfPOY9Y7Q").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gettopic", gettopic))
    app.add_handler(CommandHandler("addmember", add_member))
    app.add_handler(CommandHandler("members", list_members))
    app.add_handler(CommandHandler("selectmembers", select_members))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CommandHandler("setcost", set_cost))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("reset", reset))
    print("🤖 ربات آماده کار در تاپیک هزینه کافه...")
    app.run_polling()
