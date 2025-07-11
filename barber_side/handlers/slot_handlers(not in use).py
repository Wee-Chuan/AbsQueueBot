# Telegram imports
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# Firebase imports
from firebase_admin import auth

# Standard library imports
import datetime
from datetime import timedelta

# Third-party imports
import pytz
import calendar

# Local imports
from barber_side.utils.globals import *  # Custom global utilities (ensure it's properly imported)


timezone = pytz.timezone('Asia/Singapore')  # Or whatever your timezone is


# VIEWING AND CREATING SLOTS -----------------------------------
async def view_my_slots(update: Update, context: CallbackContext) -> None:
    logged_in = context.user_data.get('logged_in')
    if not logged_in:
        await update.message.reply_text("Please log in first!")
        return

    try:
        email = context.user_data.get('current_user').email

        # Reference to the 'open slots' collection
        collection_ref = db.collection('open slots')

        # Perform the query to find slots matching the user's email
        field_name = "barber_email"  # The field name for email in the collection
        value = email  # The logged-in user's email
        query = collection_ref.where(field_name, "==", value)

        # Get the results from the query
        results = query.stream()

        # Debugging: Check if any results are found
        results_list = list(results)
        if not results_list:  # If no results, send a message
            await update.message.reply_text("You don't have any open slots.")
            return

        # Prepare the response message
        slot_details = "Your open slots:\n"
        for doc in results_list:
            data = doc.to_dict()

            # Get start time and end time from the document (assumes timestamp fields)
            start_time = data.get('start time')
            end_time = data.get('end time')

            # Convert timestamps to readable strings
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.replace(tzinfo=pytz.utc).astimezone(timezone).strftime("%Y-%m-%d %H:%M:%S")

            if isinstance(end_time, datetime.datetime):
                end_time = end_time.replace(tzinfo=pytz.utc).astimezone(timezone).strftime("%Y-%m-%d %H:%M:%S")

            # Add the slot information to the response
            slot_details += f"Start Time: {start_time} | End Time: {end_time}\n"

        # Send the results as a reply
        await update.message.reply_text(slot_details)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

DATE_SELECTION, TIME_SELECTION = range(2)  # Define a new state

#########  /create_slot
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Operation cancelled!")
    messages_to_delete = context.user_data.get('messages_to_delete', [])
    try:
    # Use context.bot instead of update.bot
        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=messages_to_delete)
    except Exception as e:
        print(f"Error deleting message: {e}")
    return ConversationHandler.END

async def ask_for_date(update: Update, context: CallbackContext) -> int:
    logged_in = context.user_data.get('logged_in')
    if not logged_in:
        await update.message.reply_text("Please log in first!")
        return

    # Initial prompt
    first_prompt = await update.message.reply_text(
        "Open up new slots for your clients to book!\nType '/cancel' to cancel the process"
    )

    # Show calendar for the current month
    now = datetime.datetime.now()
    calendar_markup = build_calendar(now.year, now.month)
    calendar_message = await update.message.reply_text("📅 Please choose a date:", reply_markup=calendar_markup)

    context.user_data.setdefault('messages_to_delete', []).extend([
        first_prompt.message_id,
        calendar_message.message_id
    ])

    return DATE_SELECTION

# handle the date given
async def handle_calendar_selection(update: Update, context: CallbackContext) -> int:
    print("in handler_calendar_selection")
    query = update.callback_query
    await query.answer()

    selected_data = query.data
    if selected_data.startswith("select_date_"):
        date_str = selected_data.replace("select_date_", "")
        try:
            slot_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            error_msg = await query.message.reply_text("❌ Invalid date format.")
            context.user_data.setdefault("messages_to_delete", []).append(error_msg.message_id)
            return DATE_SELECTION

        today = datetime.datetime.now().date()
        if slot_date.date() < today:
            error_msg = await query.message.reply_text("❌ You cannot select a past date.")
            context.user_data.setdefault("messages_to_delete", []).append(error_msg.message_id)
            return DATE_SELECTION

        # Store selected date in user_data for later use if needed
        context.user_data["selected_date"] = slot_date

        # Generate time slots for that day
        time_slots = generate_time_slots(slot_date)
        keyboard = [
            [InlineKeyboardButton(f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}",
                                  callback_data=f"toggle_{start_time.strftime('%Y-%m-%d %H:%M')}")]
            for start_time, end_time in time_slots
        ]

        # 👇 Append the confirm button at the end
        keyboard.append([
            InlineKeyboardButton("✅ Confirm Selection", callback_data="confirm_slots")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the time selection message
        time_prompt = await query.message.reply_text("🕒 Please select a time slot:", reply_markup=reply_markup)
        context.user_data.setdefault("messages_to_delete", []).append(time_prompt.message_id)

        return TIME_SELECTION

    return DATE_SELECTION

# Generate time slots with 30-minute intervals
def generate_time_slots(date: datetime.datetime):
    time_slots = []
    start_time = datetime.datetime(date.year, date.month, date.day, 9, 0)  # Start at 9:00 AM
    start_time = timezone.localize(start_time)
    for _ in range(16):  # Generate 16 slots (9 AM to 5 PM)
        end_time = start_time + timedelta(minutes=30)
        time_slots.append((start_time, end_time))
        start_time = end_time  # Move to the next slot
    return time_slots

async def handle_time_slot_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    selected_slot = query.data.replace("toggle_", "")
    print(f"Debug: Selected slot data: {selected_slot}")  # <-- Added debug log

    # Retrieve or initialize selected slots
    selected_slots = context.user_data.get("selected_slots", set())
    print(f"Debug: Current selected slots: {selected_slots}")  # <-- Added debug log

    if selected_slot in selected_slots:
        selected_slots.remove(selected_slot)
        print(f"Debug: Removed slot: {selected_slot}")  # <-- Added debug log
    else:
        selected_slots.add(selected_slot)
        print(f"Debug: Added slot: {selected_slot}")  # <-- Added debug log

    context.user_data["selected_slots"] = selected_slots

    # Rebuild the inline keyboard
    slot_date = context.user_data.get("selected_date")
    keyboard = []

    time_slots = generate_time_slots(slot_date)
    for start_time, end_time in time_slots:
        slot_str = start_time.strftime('%Y-%m-%d %H:%M')
        text = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
        if slot_str in selected_slots:
            text = f"✅ {text}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"toggle_{slot_str}")])

    keyboard.append([InlineKeyboardButton("✅ Confirm", callback_data="confirm_slots")])

    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    return TIME_SELECTION

# handler for 'confirm' button
async def confirm_selected_slots(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # set of chosen time slots
    selected = context.user_data.get("selected_slots", set())
    if not selected:
        await query.message.reply_text("❌ You haven't selected any slots.")
        return TIME_SELECTION

    try:
        firebase_user_id = user_sessions[query.from_user.id]
        user = auth.get_user(firebase_user_id)
        email = user.email

        for slot_str in selected:
            start_time = timezone.localize(datetime.datetime.strptime(slot_str, "%Y-%m-%d %H:%M"))
            end_time = start_time + timedelta(minutes=30)

            db.collection("open slots").add({
                "barber_email": email,
                "start time": start_time,
                "end time": end_time
            })

        await query.message.reply_text(f"✅ {len(selected)} slot(s) created successfully!")
    except Exception as e:
        await query.message.reply_text(f"❌ Error creating slots: {str(e)}")

    context.user_data["selected_slots"] = set()
    messages_to_delete = context.user_data.get('messages_to_delete', [])
    try:
    # Use context.bot instead of update.bot
        await context.bot.delete_messages(chat_id=update.callback_query.message.chat_id, message_ids=messages_to_delete)
    except Exception as e:
        print(f"Error deleting message: {e}")
    return ConversationHandler.END

# builds the calendar to show the date options
def build_calendar(year, month):
    keyboard = []

    # Get today's date
    today = datetime.datetime.today().date()

    # Header row with month and navigation
    header = [
        InlineKeyboardButton("«", callback_data=f"prev_{year}_{month:02d}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton("»", callback_data=f"next_{year}_{month:02d}")
    ]
    keyboard.append(header)

    # Weekday headers
    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in days])

    # Generate the calendar weeks
    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if today.year == year and today.month == month and today.day == day:
                    # Highlight the current day with a green checkmark
                    button_text = f"{day} ✅"  # Green checkmark next to the day
                else:
                    button_text = str(day)
                button = InlineKeyboardButton(button_text, callback_data=f"select_date_{date_str}")
                row.append(button)
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)

# Handle the pagination of the calendar
async def navigate_calendar(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    data = query.data
    print(f"Callback data received: {data}")  # Debugging line

    if data.startswith("prev_") or data.startswith("next_"):
        # Split the callback data and ensure we extract year and month correctly
        parts = data.split("_")
        if len(parts) == 3:
            direction, year, month = parts[0], int(parts[1]), int(parts[2])

            # Debugging line to check if year and month are extracted correctly
            print(f"Year: {year}, Month: {month}")

            # Determine if we're moving to the previous or next month
            if direction == "prev":
                if month == 1:
                    month = 12
                    year -= 1  # Move to the previous year
                else:
                    month -= 1
            elif direction == "next":
                if month == 12:
                    month = 1
                    year += 1  # Move to the next year
                else:
                    month += 1

            # Generate the new calendar
            new_calendar = build_calendar(year, month)

            # Update the message with the new calendar
            await query.edit_message_reply_markup(reply_markup=new_calendar)
        else:
            print("Error: Invalid callback data format.")
            await query.message.reply_text("❌ Invalid date format. Please try again.")
    else:
        print("Error: Callback data does not match expected format.")
        await query.message.reply_text("❌ Invalid action.")

# handler to add to app
date_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("create_slot", ask_for_date)],
    states={
        DATE_SELECTION: [
            CallbackQueryHandler(handle_calendar_selection, pattern=r"^select_date_\d{4}-\d{2}-\d{2}$"),
            CallbackQueryHandler(navigate_calendar, pattern=r"^(prev|next)_\d{4}_\d{2}$")
        ],
        TIME_SELECTION: [
            CallbackQueryHandler(handle_time_slot_selection, pattern=r"^toggle_\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
            CallbackQueryHandler(confirm_selected_slots, pattern=r"^confirm_slots$")
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
