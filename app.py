import logging
import re
from datetime import datetime, timedelta
from config import TELEGRAM_SECRET
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from models import User, session, MedicineInterval
from sqlalchemy.exc import IntegrityError

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

async def add_new_medicine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add new medicine"""
    if len(context.args) != 3:
        await update.message.reply_text("Invalid number of arguments. Please provide the medicine name, day interval, and day hour in the format `/new_medicine <medicine_name> <day_interval> <day_hour>`.")
        return
    chat_id = update.effective_message.chat_id
    user = session.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        await update.message.reply_text("Please call /start command first")

    medicine_name = context.args[0]
    day_interval = context.args[1]
    day_hour = context.args[2]
    
    # Validate medicine name
    if not isinstance(medicine_name, str):
        await update.message.reply_text("Invalid medicine name. Please provide a valid string.")
        return

    # Validate day interval
    if not day_interval.isdigit() or int(day_interval) < 1 or int(day_interval) > 15:
        await update.message.reply_text("Invalid day interval. Please provide a number between 1 and 15.")
        return

    # Validate day hour format
    hour_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$"
    if not re.match(hour_pattern, day_hour):
        await update.message.reply_text("Invalid day hour format. Please provide the hour in the format 'HH:MM' (e.g., '21:00', '06:00', '21:56', '11:59', '13:00').")
        return
    current_time = datetime.now().replace(second=0, microsecond=0)
    hour, minute = map(int, day_hour.split(':'))
    next_run_time = current_time.replace(hour=hour, minute=minute)

    # Check if the next_run_time is in the past
    if next_run_time < current_time:
        # Add the day_interval to the next_run_time
        next_run_time += timedelta(days=int(day_interval))
    
    # Calculate the time difference until the next_run_time
    time_difference = next_run_time - current_time

    # Extract the hours and minutes from the time difference
    hours = time_difference.days * 24 + time_difference.seconds // 3600
    minutes = (time_difference.seconds % 3600) // 60

    # Format the time difference as HH:MM
    time_difference_str = f"{hours:02d}:{minutes:02d}"

    #Create the MedicineInterval object
    try:
        medicine_interval = MedicineInterval(
            medicine_name=medicine_name,
            user_id=user.id,
            hour=day_hour,
            interval=day_interval,
            next_run=int(next_run_time.timestamp())
        )
        session.add(medicine_interval)
        session.commit()

        await update.message.reply_text(
            f"Medicine '{medicine_name}' has been added.\n"
            f"Next run: {next_run_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"Time difference: {time_difference_str}"
        )
    except IntegrityError:
        # Handle the unique constraint violation error
        session.rollback()
        await update.message.reply_text("A medicine with the same combination of name, hour, and interval already exists.")

async def help_(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    
    # Check if the user already exists in the database
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if not user:
        # If the user doesn't exist, create a new User object and add it to the session
        user = User(chat_id=chat_id)
        session.add(user)
        session.commit()

    """Sends explanation on how to use the bot."""
    reply_text = "<b>Welcome to the Medicine Reminder Bot!</b>\n\n"
    reply_text += "<b>You can use the following commands:</b>\n\n"
    reply_text += "/help - Show the list of available commands\n\n"
    reply_text += "/list - List all your medicine intervals\n"
    reply_text += "<i>Example:</i> /list\n"
    reply_text += "This command will display all your medicine intervals.\n\n"
    reply_text += "/new_medicine - Add a new medicine interval\n"
    reply_text += "<i>Example:</i> /new_medicine xanax 2 09:00\n"
    reply_text += "This command adds a new medicine interval. Provide the medicine name, day interval (1-15), and day hour (HH:MM format).\n\n"
    reply_text += "/delete_medicine - Delete a medicine interval\n"
    reply_text += "<i>Example:</i> /delete_medicine Headache 1 09:00\n"
    reply_text += "This command deletes a medicine interval. Provide the medicine name, day interval (1-15), and day hour (HH:MM format).\n\n"
    reply_text += "Please note that the time format for medicine intervals should be HH:MM (24-hour format).\n"
    reply_text += "For example, to set a medicine interval for 9:00 PM, use '21:00'."
    
    await update.message.reply_text(reply_text, parse_mode='HTML')

async def check_overdue_medicines(context: ContextTypes.DEFAULT_TYPE):
    now = int(datetime.now().timestamp())
    medicines = session.query(MedicineInterval).all()

    for medicine in medicines:
        next_take_time = medicine.next_run
        if next_take_time <= now:
            # Send notification to the user
            chat_id = medicine.user.chat_id
            message = f"It's time to take your medicine: {medicine.medicine_name}!"
            await context.bot.send_message(chat_id=chat_id, text=message)

            # Update the next take time for the medicine
            next_take_time += timedelta(days=int(medicine.interval))
            medicine.next_run = int(next_take_time.timestamp())

    # Commit the changes to the database
    session.commit()

async def delete_medicine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the medicine prompts are same as new_medicine"""
    if len(context.args) != 3:
        await update.message.reply_text("Invalid number of arguments. Please provide the medicine name, day interval, and day hour in the format `/delete_medicine <medicine_name> <day_interval> <day_hour>`.")
        return
    chat_id = update.effective_message.chat_id
    user = session.query(User).filter_by(chat_id=chat_id).first()
    if not user:
        await update.message.reply_text("Please call /start command first")
        return

    medicine_name = context.args[0]
    day_interval = context.args[1]
    day_hour = context.args[2]

    # Validate medicine name, day interval, and day hour
    if not isinstance(medicine_name, str):
        await update.message.reply_text("Invalid medicine name. Please provide a valid string.")
        return
    if not day_interval.isdigit() or int(day_interval) < 1 or int(day_interval) > 15:
        await update.message.reply_text("Invalid day interval. Please provide a number between 1 and 15.")
        return
    hour_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$"
    if not re.match(hour_pattern, day_hour):
        await update.message.reply_text("Invalid day hour format. Please provide the hour in the format 'HH:MM' (e.g., '21:00', '06:00', '21:56', '11:59', '13:00').")
        return

    # Find the medicine to delete
    medicine_to_delete = session.query(MedicineInterval).filter_by(
        user=user,
        medicine_name=medicine_name,
        interval=day_interval,
        hour=day_hour
    ).first()

    if not medicine_to_delete:
        await update.message.reply_text("The specified medicine does not exist.")
        return

    # Delete the medicine
    session.delete(medicine_to_delete)
    session.commit()

    await update.message.reply_text(f"Medicine '{medicine_name}' has been deleted.")

async def list_medicines(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists medicines for message sender"""
    chat_id = update.effective_message.chat_id
    user = session.query(User).filter_by(chat_id=chat_id).first()
    
    if not user:
        await update.message.reply_text("Please call /start command first")
        return
    
    medicines = session.query(MedicineInterval).filter_by(user=user).all()

    if not medicines:
        await update.message.reply_text("You have no medicines added.")
        return
    now = datetime.now()
    next_take_arr = []
    for medicine in medicines:
        next_take_time = datetime.fromtimestamp(medicine.next_run)
        if next_take_time < now:
            next_take_time += timedelta(days=int(medicine.interval))
        next_take_time_formatted = next_take_time.strftime("%Y-%m-%d %H:%M")
        next_take_arr.append(next_take_time_formatted)

    medicine_list = "\n".join([f"- {medicine.medicine_name}: every {medicine.interval} days at {medicine.hour}, next take on {next_take_arr[index]}" for index,medicine in enumerate(medicines)])
    await update.message.reply_text(medicine_list)

    table_header = "ID  | Medicine Name   | Interval (days) | Hour\n"
    table_separator = "-" * 40 + "\n"
    table_rows = [
        f"{medicine.id:<3} | {medicine.medicine_name:<15} | {medicine.interval:<15} | {medicine.hour}"
        for medicine in medicines
    ]
    medicine_table = table_header + table_separator + "\n".join(table_rows)

    message = f"\n```\n{medicine_table}\n```"
    await update.message.reply_text(message, parse_mode='Markdown')

def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_SECRET).build()
    application.job_queue.run_repeating(check_overdue_medicines, interval=60, first=0)
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler(["help","start"], help_))
    application.add_handler(CommandHandler("new_medicine", add_new_medicine))
    application.add_handler(CommandHandler("delete_medicine", delete_medicine))
    application.add_handler(CommandHandler("list", list_medicines))


    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()