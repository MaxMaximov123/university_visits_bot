import telebot
import datetime
import schedule
import time
import os
from dotenv import load_dotenv
import threading
from telebot import types


load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
TOPIC_ID = os.getenv("TOPIC_ID")
TOPIC_ID = int(TOPIC_ID) if TOPIC_ID not in (None, "", "None") else None
ADMIN_USERNAMES = ["kotik594"]

bot = telebot.TeleBot(TOKEN)


def send_poll():
    today = datetime.date.today()
    print('sending')
    date_str = today.strftime("%d.%m.%Y")
    question = f"📌{date_str}. Придёшь сегодня 🫩🤥?"
    bot.send_poll(
        chat_id=CHAT_ID,
        question=question,
        options=["Да", "Нет"],
        is_anonymous=False,
        message_thread_id=TOPIC_ID
    )


schedule.every().monday.at("05:00").do(send_poll)
schedule.every().tuesday.at("05:00").do(send_poll)
schedule.every().wednesday.at("05:00").do(send_poll)
schedule.every().thursday.at("05:00").do(send_poll)
schedule.every().friday.at("05:00").do(send_poll)


@bot.message_handler(commands=['poll'])
def manual_poll(message):
    if message.from_user.username in ADMIN_USERNAMES:
        send_poll()
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print("Не удалось удалить /poll:", e)
    else:
        bot.reply_to(message, "У тебя нет прав на эту команду 🚫")


@bot.poll_answer_handler()
def handle_poll_answer(answer):
    username = answer.user.username if answer.user.username else answer.user.first_name
    print(f"@{username} voted {answer.option_ids}")
    if answer.option_ids and answer.option_ids[0] == 1:
        bot.send_message(CHAT_ID, f"@{username} отчислен!", message_thread_id=TOPIC_ID)


@bot.message_handler(func=lambda m: True)
def debug(m):
    # Delete any message in the configured chat/topic
    if m.chat.id == CHAT_ID and (TOPIC_ID is None or getattr(m, "message_thread_id", None) == TOPIC_ID):
        try:
            bot.delete_message(m.chat.id, m.message_id)
        except Exception as e:
            print(f"Не удалось удалить сообщение {m.message_id} в чате {m.chat.id}: {e}")


def scheduler():
    while True:
        print('ping')
        schedule.run_pending()
        time.sleep(10)


threading.Thread(target=scheduler, daemon=True).start()


if __name__ == '__main__':
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

