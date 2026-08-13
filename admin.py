from telebot import types

import database as db
import stats

ADMIN_USERNAMES = ["kotik594"]

SETTING_LABELS = {
    "content_weather": "Погода",
    "content_jokes": "Шутки",
    "content_tips": "Советы",
    "content_facts": "Факты",
    "content_quotes": "Цитаты",
}


def is_admin(msg_or_call):
    if hasattr(msg_or_call, "from_user"):
        user = msg_or_call.from_user
    elif hasattr(msg_or_call, "message"):
        user = msg_or_call.from_user
    else:
        return False
    return user and user.username in ADMIN_USERNAMES


def _toggle_icon(value):
    return "✅" if value == "1" else "❌"


def main_menu_keyboard(settings):
    kb = types.InlineKeyboardMarkup(row_width=1)
    mailing = settings.get("mailing_enabled", "1")
    icon = "🟢 ВКЛ" if mailing == "1" else "🔴 ВЫКЛ"
    kb.add(
        types.InlineKeyboardButton(f"Рассылка: {icon}", callback_data="admin:toggle_mailing"),
        types.InlineKeyboardButton("📝 Контент рассылки", callback_data="admin:content"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin:stats"),
    )
    return kb


def content_menu_keyboard(settings):
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for key, label in SETTING_LABELS.items():
        icon = _toggle_icon(settings.get(key, "1"))
        buttons.append(types.InlineKeyboardButton(
            f"{label} {icon}", callback_data=f"content:toggle_{key}"
        ))
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="content:back"))
    return kb


def stats_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📋 Список посещаемости", callback_data="stats:list"),
        types.InlineKeyboardButton("📊 График за неделю", callback_data="stats:weekly_chart"),
        types.InlineKeyboardButton("📈 Посещения по дням", callback_data="stats:daily_chart"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="stats:back"),
    )
    return kb


def handle_callback(call, bot):
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if data == "admin:toggle_mailing":
        current = db.get_setting("mailing_enabled")
        new_val = "0" if current == "1" else "1"
        db.set_setting("mailing_enabled", new_val)
        settings = db.get_all_settings()
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=main_menu_keyboard(settings))
        state = "включена" if new_val == "1" else "выключена"
        bot.answer_callback_query(call.id, f"Рассылка {state}")

    elif data == "admin:content":
        settings = db.get_all_settings()
        bot.edit_message_text(
            "📝 Контент рассылки:", chat_id, message_id,
            reply_markup=content_menu_keyboard(settings),
        )
        bot.answer_callback_query(call.id)

    elif data == "admin:stats":
        bot.edit_message_text(
            "📊 Статистика:", chat_id, message_id,
            reply_markup=stats_menu_keyboard(),
        )
        bot.answer_callback_query(call.id)

    elif data.startswith("content:toggle_"):
        key = data.replace("content:toggle_", "")
        current = db.get_setting(key)
        new_val = "0" if current == "1" else "1"
        db.set_setting(key, new_val)
        settings = db.get_all_settings()
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=content_menu_keyboard(settings))
        label = SETTING_LABELS.get(key, key)
        state = "включено" if new_val == "1" else "выключено"
        bot.answer_callback_query(call.id, f"{label}: {state}")

    elif data == "content:back" or data == "stats:back":
        settings = db.get_all_settings()
        bot.edit_message_text(
            "⚙️ Панель администратора", chat_id, message_id,
            reply_markup=main_menu_keyboard(settings),
        )
        bot.answer_callback_query(call.id)

    elif data == "stats:list":
        text = stats.attendance_list_text()
        bot.send_message(chat_id, text)
        bot.answer_callback_query(call.id)

    elif data == "stats:weekly_chart":
        bot.answer_callback_query(call.id, "Генерирую график...")
        try:
            chart = stats.generate_weekly_chart()
            if chart:
                bot.send_photo(chat_id, chart, caption="📊 Посещаемость за неделю")
            else:
                bot.send_message(chat_id, "Нет данных для графика за эту неделю.")
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при генерации графика: {e}")

    elif data == "stats:daily_chart":
        bot.answer_callback_query(call.id, "Генерирую график...")
        try:
            chart = stats.generate_daily_line_chart()
            if chart:
                bot.send_photo(chat_id, chart, caption="📈 Посещения по дням (30 дней)")
            else:
                bot.send_message(chat_id, "Пока нет данных для графика.")
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка при генерации графика: {e}")

    else:
        bot.answer_callback_query(call.id, "Неизвестная команда")
