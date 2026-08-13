import datetime
import os
import threading
import time

import schedule
import telebot
from dotenv import load_dotenv

import admin
import content
import database as db
import stats

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
TOPIC_ID = os.getenv("TOPIC_ID")
TOPIC_ID = int(TOPIC_ID) if TOPIC_ID not in (None, "", "None") else None

bot = telebot.TeleBot(TOKEN)

db.init_db()


def send_daily_message():
    if db.get_setting("mailing_enabled") != "1":
        return

    today = datetime.date.today()
    settings = db.get_all_settings()

    parts = [content.get_random_greeting(), ""]
    parts.append(f"📅 {content.format_date_ru(today)}")

    if settings.get("content_weather") == "1":
        weather = content.get_weather_moscow()
        if weather:
            parts.append(f"🌤 Москва: {weather}")

    parts.append("")

    random_item = content.get_random_content(settings)
    if random_item:
        label, text = random_item
        parts.append(f"💬 {label}:\n{text}")
        parts.append("")

    yesterday_text = stats.yesterday_stats()
    if yesterday_text:
        parts.append(yesterday_text)

    message_text = "\n".join(parts).strip()
    bot.send_message(CHAT_ID, message_text, message_thread_id=TOPIC_ID)

    date_str = today.strftime("%d.%m.%Y")
    sent = bot.send_poll(
        chat_id=CHAT_ID,
        question=f"📌 {date_str}. Придёшь сегодня?",
        options=["Буду! 💪", "Опоздаю 🏃", "Не приду 😴"],
        is_anonymous=False,
        type="regular",
        message_thread_id=TOPIC_ID,
    )
    db.save_poll(sent.poll.id, sent.message_id, today.isoformat())


def send_weekly_stats():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    monday_iso = monday.isoformat()

    text = stats.weekly_text_stats(monday_iso)
    bot.send_message(CHAT_ID, text, message_thread_id=TOPIC_ID)

    try:
        chart = stats.generate_weekly_chart(monday_iso)
        if chart:
            bot.send_photo(CHAT_ID, chart, message_thread_id=TOPIC_ID)
    except Exception as e:
        print(f"Weekly chart error: {e}")


schedule.every().monday.at("05:00").do(send_daily_message)
schedule.every().tuesday.at("05:00").do(send_daily_message)
schedule.every().wednesday.at("05:00").do(send_daily_message)
schedule.every().thursday.at("05:00").do(send_daily_message)
schedule.every().friday.at("05:00").do(send_daily_message)
schedule.every().saturday.at("09:00").do(send_weekly_stats)


@bot.message_handler(commands=["poll"])
def manual_poll(message):
    if message.from_user.username in admin.ADMIN_USERNAMES:
        send_daily_message()
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
    else:
        bot.reply_to(message, "У тебя нет прав на эту команду 🚫")


@bot.message_handler(commands=["stats"])
def manual_stats(message):
    if message.from_user.username in admin.ADMIN_USERNAMES:
        send_weekly_stats()
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass


@bot.message_handler(commands=["start", "admin"])
def admin_start(message):
    if message.chat.type != "private":
        return
    if not admin.is_admin(message):
        bot.reply_to(message, "У тебя нет доступа к панели администратора 🚫")
        return
    settings = db.get_all_settings()
    kb = admin.main_menu_keyboard(settings)
    bot.send_message(message.chat.id, "⚙️ Панель администратора", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if not admin.is_admin(call):
        bot.answer_callback_query(call.id, "Нет доступа 🚫")
        return
    admin.handle_callback(call, bot)


@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    user = poll_answer.user
    if poll_answer.option_ids:
        db.save_answer(
            poll_id=poll_answer.poll_id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            option_id=poll_answer.option_ids[0],
        )
    else:
        db.retract_answer(poll_answer.poll_id, user.id)


@bot.message_handler(func=lambda m: True)
def delete_in_topic(m):
    if m.chat.id == CHAT_ID and (TOPIC_ID is None or getattr(m, "message_thread_id", None) == TOPIC_ID):
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except Exception:
            pass


def scheduler_loop():
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"Scheduler error: {e}")
        time.sleep(10)


threading.Thread(target=scheduler_loop, daemon=True).start()

if __name__ == "__main__":
    print("Bot starting...")
    bot.infinity_polling(
        timeout=10,
        long_polling_timeout=5,
        allowed_updates=["message", "poll_answer", "callback_query"],
    )
