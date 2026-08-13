import datetime
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import database as db
from content import declension, format_date_ru

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["figure.dpi"] = 150


def _text_bar(value, total, length=10):
    if total == 0:
        return "░" * length + " 0/0"
    filled = round(value / total * length)
    return "█" * filled + "░" * (length - filled) + f" {value}/{total}"


def _display_name(username, first_name):
    if username:
        return f"@{username}"
    return first_name or "???"


def yesterday_stats():
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    answers = db.get_answers_for_date(yesterday)
    if not answers:
        return None
    attended = sum(1 for a in answers if a["option_id"] in (0, 1))
    total = len(answers)
    active = db.get_active_members()
    total_members = max(len(active), total)
    pct = round(attended / total_members * 100) if total_members else 0
    return f"📊 Вчера было: {attended} из {total_members} ({pct}%)"


def weekly_text_stats(monday_iso):
    monday = datetime.date.fromisoformat(monday_iso)
    friday = monday + datetime.timedelta(days=4)
    weekly_data = db.get_weekly_data(monday_iso)
    active_members = db.get_active_members()
    active_ids = {m["user_id"] for m in active_members}
    member_names = {m["user_id"]: _display_name(m["username"], m["first_name"]) for m in active_members}
    total_members = len(active_ids)

    absences = {uid: 0 for uid in active_ids}
    days_with_polls = 0

    parts = []
    parts.append(f"📊 Итоги недели ({monday.strftime('%d.%m')} — {friday.strftime('%d.%m')})\n")

    day_lines = []
    for day_data in weekly_data:
        days_with_polls += 1
        d = datetime.date.fromisoformat(day_data["date"])
        answers = day_data["answers"]
        voted_ids = {a["user_id"] for a in answers}
        attended = sum(1 for a in answers if a["option_id"] in (0, 1))

        for uid in active_ids:
            if uid not in voted_ids:
                absences[uid] += 1
            else:
                ans = next(a for a in answers if a["user_id"] == uid)
                if ans["option_id"] == 2:
                    absences[uid] += 1

        day_name = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт"}[d.weekday()]
        bar = _text_bar(attended, total_members)
        day_lines.append(f"  {day_name} {d.strftime('%d.%m')}: {bar}")

    if not weekly_data:
        return "📊 На этой неделе не было опросов."

    if day_lines:
        parts.append("📈 Посещаемость по дням:")
        parts.extend(day_lines)
        parts.append("")

    sorted_absences = sorted(absences.items(), key=lambda x: x[1], reverse=True)
    top = [(uid, cnt) for uid, cnt in sorted_absences if cnt > 0]

    if top:
        parts.append("🏆 Топ прогульщиков недели:")
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, cnt) in enumerate(top[:5]):
            medal = medals[i] if i < 3 else f"{i + 1}."
            name = member_names.get(uid, "???")
            skip_text = declension(cnt, "пропуск", "пропуска", "пропусков")
            parts.append(f"  {medal} {name} — {skip_text}")
        parts.append("")

        champion_uid, champion_cnt = top[0]
        champion_name = member_names.get(champion_uid, "???")
        parts.append(f"👑 Главный прогульщик: {champion_name}")
    else:
        parts.append("🎉 На этой неделе все молодцы — ни одного прогула!")

    total_attended = sum(
        sum(1 for a in day["answers"] if a["option_id"] in (0, 1))
        for day in weekly_data
    )
    total_possible = total_members * days_with_polls
    avg_pct = round(total_attended / total_possible * 100) if total_possible else 0
    parts.append(f"\n📉 Средняя посещаемость: {avg_pct}%")

    return "\n".join(parts)


def attendance_list_text(days=30):
    stats, total_polls = db.get_overall_stats()
    if not stats:
        return "📋 Пока нет данных о посещаемости."

    lines = ["📋 Статистика посещаемости\n"]
    for s in stats:
        name = _display_name(s["username"], s["first_name"])
        no_response = max(0, total_polls - s["total_votes"])
        total_absent = s["absent"] + no_response
        total_present = s["attended"]
        pct = round(total_present / total_polls * 100) if total_polls else 0
        lines.append(f"  {name}: {total_present}/{total_polls} ({pct}%)")

    return "\n".join(lines)


def generate_weekly_chart(monday_iso=None):
    if monday_iso is None:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        monday_iso = monday.isoformat()

    weekly_data = db.get_weekly_data(monday_iso)
    if not weekly_data:
        return None

    active_members = db.get_active_members()
    total_members = len(active_members)
    member_names = {m["user_id"]: _display_name(m["username"], m["first_name"]) for m in active_members}

    absences = {uid: 0 for uid in member_names}
    for day_data in weekly_data:
        voted_ids = {a["user_id"] for a in day_data["answers"]}
        for uid in member_names:
            if uid not in voted_ids:
                absences[uid] += 1
            else:
                ans = next((a for a in day_data["answers"] if a["user_id"] == uid), None)
                if ans and ans["option_id"] == 2:
                    absences[uid] += 1

    sorted_members = sorted(absences.items(), key=lambda x: x[1], reverse=True)
    names = [member_names[uid] for uid, _ in sorted_members]
    absence_counts = [cnt for _, cnt in sorted_members]
    attend_counts = [len(weekly_data) - cnt for cnt in absence_counts]

    fig, ax = plt.subplots(figsize=(10, max(4, len(names) * 0.5)))
    y_pos = range(len(names))
    ax.barh(y_pos, attend_counts, color="#4CAF50", label="Был(а)")
    ax.barh(y_pos, absence_counts, left=attend_counts, color="#F44336", label="Пропуск")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names)
    ax.set_xlabel("Дни")
    ax.set_title("Посещаемость за неделю")
    ax.legend(loc="lower right")
    ax.set_xlim(0, len(weekly_data))
    ax.invert_yaxis()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_daily_line_chart(days=30):
    data = db.get_daily_attendance(days)
    if not data:
        return None

    active_count = len(db.get_active_members())
    dates = [datetime.date.fromisoformat(d["date"]) for d in data]
    attended = [d["attended"] for d in data]
    absent = [max(0, active_count - d["attended"]) for d in data]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, attended, "o-", color="#4CAF50", label="Были", linewidth=2, markersize=6)
    ax.plot(dates, absent, "o-", color="#F44336", label="Отсутствовали", linewidth=2, markersize=6)
    ax.fill_between(dates, attended, alpha=0.2, color="#4CAF50")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
    plt.xticks(rotation=45)
    ax.set_ylabel("Человек")
    ax.set_title("Посещаемость по дням")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
