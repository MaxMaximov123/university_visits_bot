import telebot
import datetime
import schedule
import time
import os
from dotenv import load_dotenv
import threading

print('start')

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
TOPIC_ID = os.getenv("TOPIC_ID")
TOPIC_ID = int(TOPIC_ID) if TOPIC_ID not in (None, "", "None") else None

bot = telebot.TeleBot(TOKEN)

def send_poll():
    today = datetime.date.today()
    if today.weekday() < 5:
        print('sending')
        date_str = today.strftime("%d.%m.%Y")
        question = f"Придёшь на пары {date_str}?"
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
schedule.every().thursday.at("17:40").do(send_poll)
schedule.every().friday.at("05:00").do(send_poll)

@bot.message_handler(func=lambda m: True)
def debug(m):
    send_poll()
    print("chat_id:", m.chat.id, "thread_id:", m.message_thread_id)

def scheduler():
    while True:
        print('ping')
        schedule.run_pending()
        time.sleep(10)


threading.Thread(target=scheduler, daemon=True).start()


if __name__ == '__main__':
    bot.infinity_polling(timeout=10, long_polling_timeout=5)