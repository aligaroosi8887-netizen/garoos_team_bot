import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ==========================
# تنظیمات محیطی
# ==========================
ADMIN_ID = int(os.environ.get("ADMIN_ID", "130197808"))
CHAT_ID = int(os.environ.get("CHAT_ID", "-1002655310937"))
TOPIC_THREAD_ID = int(os.environ.get("TOPIC_THREAD_ID", "40"))
TOKEN = os.environ.get("BOT_TOKEN", "")
REMINDER_INTERVAL_SECONDS = int(os.environ.get("REMINDER_INTERVAL_SECONDS", str(60*60*12)))

# ==========================
# داده‌ها
# ==========================
members = []
active_members = []
payments = {}
current_cost = 0
current_date = ""
session_active = False

# ==========================
# توابع اصلی
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("دسترسی فقط برای مدیر مجاز است.")
        return
    await update.message.reply_text("ربات فعال شد ✅\nدستور /help برای مشاهده‌ی راهنما را بزنید.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 دستورات ربات:\n\n"
        "/addmember <نام> — افزودن عضو جدید\n"
        "/members — نمایش لیست اعضا\n"
        "/selectmembers — انتخاب اعضای فعال برای دوره‌ی جدید\n"
        "/setcost <مبلغ> <تاریخ> — ثبت هزینه‌ی جدید\n"
        "/pay <نام> <مبلغ> — ثبت پرداخت عضو\n"
        "/status — نمایش وضعیت پرداخت‌ها\n"
        "/reset — پایان و ریست دوره\n"
    )
    await update.message.reply_text(text)

async def add_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        name = " ".join(context.args)
        if not name:
            await update.message.reply_text("❗ نام عضو را بنویسید. مثال: /addmember علی")
            return
        if name in members:
            await update.message.reply_text("این عضو قبلاً اضافه شده است.")
        else:
            members.append(name)
            await update.message.reply_text(f"✅ عضو «{name}» اضافه شد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در افزودن عضو: {e}")

async def show_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not members:
        await update.message.reply_text("هنوز عضوی اضافه نشده است.")
    else:
        text = "👥 اعضا:\n" + "\n".join([f"• {m}" for m in members])
        await update.message.reply_text(text)

async def select_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not members:
        await update.message.reply_text("ابتدا با /addmember اعضا را اضافه کنید.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{'✅' if m in active_members else '⬜️'} {m}", callback_data=f"toggle_{m}")]
        for m in members
    ]
    keyboard.append([InlineKeyboardButton("تأیید", callback_data="confirm_selection")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اعضای فعال را انتخاب کنید:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    global active_members
    if data.startswith("toggle_"):
        name = data.split("_",1)[1]
        if name in active_members:
            active_members.remove(name)
        else:
            active_members.append(name)
        await select_members(update, context)
    elif data == "confirm_selection":
        if not active_members:
            await query.edit_message_text("هیچ عضوی انتخاب نشده است.")
            return
        await query.edit_message_text("✅ اعضای فعال انتخاب شدند:\n" + "\n".join(active_members))

async def set_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_cost, current_date, payments, session_active
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        amount = int(context.args[0])
        date = " ".join(context.args[1:]) if len(context.args) > 1 else "نامشخص"
        current_cost = amount
        current_date = date
        payments = {m:0 for m in active_members}
        session_active = True
        if not active_members:
            await update.message.reply_text("هیچ عضو فعالی انتخاب نشده است.")
            return
        share = amount / len(active_members)
        text = f"💰 هزینه جدید ثبت شد:\nمبلغ کل: {amount:,} تومان\nتاریخ: {date}\nتعداد اعضا: {len(active_members)}\nسهم هر نفر: {share:,.0f} تومان"
        await update.message.reply_text(text)
    except Exception:
        await update.message.reply_text("فرمت اشتباه است.\nمثال: /setcost 550000 چهارشنبه 22 مهر")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global payments, current_cost
    if not session_active:
        await update.message.reply_text("هیچ هزینه‌ای فعال نیست.")
        return
    try:
        name = context.args[0]
        amount = int(context.args[1])
        if name not in active_members:
            await update.message.reply_text("این نام در بین اعضای فعال نیست.")
            return
        payments[name] += amount
        await update.message.reply_text(f"💵 پرداخت ثبت شد: {name} → {amount:,} تومان")
        await status(update, context)
        share = current_cost / len(active_members)
        if all(payments[m] >= share for m in active_members):
            await update.message.reply_text(f"✅ همه پرداخت کردند. هزینه‌ی {current_cost:,} تومان در تاریخ {current_date} تسویه شد.")
    except Exception:
        await update.message.reply_text("فرمت اشتباه است.\nمثال: /pay علی 100000")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session_active:
        await update.message.reply_text("فعلاً هیچ هزینه‌ای ثبت نشده است.")
        return
    share = current_cost / len(active_members)
    text = f"📊 وضعیت پرداخت‌ها ({current_date}):\n\n"
    for m in active_members:
        paid = payments[m]
        remaining = share - paid
        if remaining <= 0:
            text += f"✅ {m} تسویه کرده ({paid:,.0f})\n"
        else:
            text += f"💸 {m} — پرداخت: {paid:,.0f} / مانده: {remaining:,.0f}\n"
    await update.message.reply_text(text)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global payments, current_cost, current_date, session_active
    if update.effective_user.id != ADMIN_ID:
        return
    payments = {}
    current_cost = 0
    current_date = ""
    session_active = False
    await update.message.reply_text("🔄 دوره‌ی فعلی پایان یافت و داده‌ها ریست شد.")

# ==========================
# یادآوری خودکار
# ==========================
async def reminder_loop(app):
    while True:
        if session_active:
            share = current_cost / len(active_members)
            text = "⏰ یادآوری پرداخت:\n\n"
            for m in active_members:
                remaining = share - payments[m]
                if remaining > 0:
                    text += f"🔹 {m} — مانده: {remaining:,.0f}\n"
            if text.strip() != "⏰ یادآوری پرداخت:":
                await app.bot.send_message(chat_id=CHAT_ID, text=text, message_thread_id=TOPIC_THREAD_ID)
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)

# ==========================
# اجرای برنامه
# ==========================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addmember", add_member))
    app.add_handler(CommandHandler("members", show_members))
    app.add_handler(CommandHandler("selectmembers", select_members))
    app.add_handler(CommandHandler("setcost", set_cost))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button_handler))

    # شروع حلقه یادآوری خودکار
    app.job_queue.run_once(lambda ctx: asyncio.create_task(reminder_loop(app)), 5)

    print("🤖 ربات اجرا شد ...")
    app.run_polling()
