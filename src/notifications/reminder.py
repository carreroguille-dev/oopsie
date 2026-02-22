import logging
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)

async def send_due_soon_reminder(context) -> None:
    """Job callback: fetch tasks due in reminder_days_ahead days and send a Telegram reminder."""
    data = context.job.data
    notion = data["notion"]
    user_id = data["user_id"]
    tz = pytz.timezone(data["timezone"])
    reminder_days_ahead = data["reminder_days_ahead"]

    now = datetime.now(tz)
    target_dt = now + timedelta(days=reminder_days_ahead)
    target_date = target_dt.strftime("%Y-%m-%d")
    target_display = target_dt.strftime("%d/%m/%Y")

    logger.info("Running due-soon reminder for date=%s", target_date)

    try:
        tasks = notion.get_all_tasks(fecha_inicio=target_date, fecha_fin=target_date)
    except Exception:
        logger.error("Failed to fetch tasks for due-soon reminder", exc_info=True)
        return

    pending = [t for t in tasks if t.get("status") != "Completada"]

    if not pending:
        logger.info("No pending tasks due on %s — skipping reminder", target_date)
        return

    lines = [f"⏰ Tareas con vencimiento en {reminder_days_ahead} días ({target_display}):\n"]
    for task in pending:
        space = task.get("space_name", "")
        priority = task.get("priority", "Media")
        status = task.get("status", "")

        line = f"• {task['title']}"
        if space:
            line += f" ({space})"
        line += f" — {priority}"
        if status and status != "Pendiente":
            line += f" [{status}]"
        lines.append(line)

    message = "\n".join(lines)

    try:
        await context.bot.send_message(chat_id=user_id, text=message)
        logger.info("Due-soon reminder sent: %d task(s) due on %s", len(pending), target_date)
    except Exception:
        logger.error("Failed to send due-soon reminder message", exc_info=True)
