import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from datetime import datetime

# گرفتن توکن از Environment Variable
TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    raise ValueError("توکن ربات تنظیم نشده! لطفاً BOT_TOKEN را در Environment Variable قرار دهید.")

# داده‌ها را داخل دیکشنری نگه می‌داریم
members = {}
costs = []
paid = {}

# ======== دستورات ربات ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! ربات هزینه کافه آماده است.\n"
        "دستورات:\n"
        "/addmember نام\n"
        "/listmembers\n"
        "/addcost مبلغ [تاریخ]\n"
        "/pay نام\n"
        "/status\n"
        "/reset"
    )

# افزودن عضو
async def add_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("لطفاً نام عضو را بنویسید: /addmember علی")
        return
    name = context.args[0]
    if name not in members:
        members[name] = 0
        paid[name] = 0
        await update.message.reply_text(f"عضو {name} اضافه شد.")
    else:
        await update.message.reply_text(f"{name} قبلاً اضافه شده است.")

# نمایش لیست اعضا
async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not members:
        await update.message.reply_text("هیچ عضوی اضافه نشده است.")
        return
    text = "اعضا:\n"
    for name in members:
        text += f"- {name}\n"
    await update.message.reply_text(text)

# افزودن هزینه
async def add_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("لطفاً مبلغ را وارد کنید: /addcost 550000 [22-07-1402]")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("مبلغ باید عدد باشد.")
        return
    date_str = " ".join(context.args[1:]) if len(context.args) > 1 else datetime.now().strftime("%Y-%m-%d")
    costs.append({"amount": amount, "date": date_str})
    # به صورت مساوی بین اعضا تقسیم می‌کنیم
    if members:
        share = amount / len(members)
        for name in members:
            members[name] += share
        await update.message.reply_text(f"هزینه {amount} ثبت شد.\nهر نفر {share} پرداخت دارد.")
    else:
        await update.message.reply_text("ابتدا اعضا را اضافه کنید.")

# ثبت پرداخت
async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("لطفاً نام خود را وارد کنید: /pay علی")
        return
    name = context.args[0]
    if name not in members:
        await update.message.reply_text(f"{name} عضو ثبت شده نیست.")
        return
    # پرداخت کل سهم
    paid[name] += members[name]
    members[name] = 0
    await update.message.reply_text(f"{name} پرداخت انجام داد.")
    # نمایش وضعیت
    text = "وضعیت پرداخت:\n"
    total_remaining = 0
    for n, amt in members.items():
        text += f"{n}: {amt} مانده، پرداخت شده: {paid[n]}\n"
        total_remaining += amt
    if total_remaining == 0:
        text += "\n✅ کل هزینه تسویه شد!"
    await update.message.reply_text(text)

# نمایش وضعیت کل اعضا
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not members:
        await update.message.reply_text("هیچ عضوی اضافه نشده است.")
        return
    text = "وضعیت فعلی:\n"
    total_remaining = 0
    for n, amt in members.items():
        text += f"{n}: {amt} مانده، پرداخت شده: {paid[n]}\n"
        total_remaining += amt
    if total_remaining == 0 and members:
        text += "\n✅ کل هزینه تسویه شد!"
    await update.message.reply_text(text)

# ریست کردن همه داده‌ها
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    members.clear()
    costs.clear()
    paid.clear()
    await update.message.reply_text("تمام اطلاعات ریست شد.")

# ======== راه‌اندازی ربات ========
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addmember", add_member))
app.add_handler(CommandHandler("listmembers", list_members))
app.add_handler(CommandHandler("addcost", add_cost))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("reset", reset))

print("🤖 ربات اجرا شد...")

app.run_polling()
