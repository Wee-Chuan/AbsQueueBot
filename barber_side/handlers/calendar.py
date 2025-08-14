# Standard library imports
import datetime
from datetime import timedelta, datetime as dt
import pytz
from pytz import timezone as pytz_timezone, UTC
import calendar
import re
from zoneinfo import ZoneInfo
import asyncio

# Third-party imports
from firebase_admin import auth
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler, CallbackQueryHandler

# Local imports
from barber_side.handlers.menu_handlers import menu
from barber_side.utils.storage_actions import cleanup_expired_open_slots
from barber_side.utils.globals import *  # Custom global utilities (ensure it's properly imported)

timezone = pytz.timezone('Asia/Singapore')  # Or whatever your timezone is

DATE_SELECTION, TIME_SELECTION = range(2)  # Define a new state

## 1
# entry point
async def ask_for_date(update: Update, context: CallbackContext) -> int:
    email = context.user_data.get('current_user').email
    await cleanup_expired_open_slots(email)
    
    if update.callback_query:
        first_prompt = await update.callback_query.edit_message_text( "Manage your appointments! Open or close slots! \nType '/cancel' to cancel the process"
        )
        messages_to_delete = context.user_data.get('messages_to_delete', [])
    else:
        first_prompt = await update.message.edit_message_text( "Manage your appointments! Open or close slots! \nType '/cancel' to cancel the process"
        )
        messages_to_delete = context.user_data.get('messages_to_delete', [])

    # Show calendar for the current month
    now = dt.now()
    calendar_markup = build_calendar(now.year, now.month) ## use the helper function
    
    query = update.callback_query
    try:
        # try to edit the old message
        calendar_message = await query.edit_message_text(
            "📅 Please choose a date:", 
            reply_markup=calendar_markup
        )
    except Exception as e:
        print(f"Could not edit message: {e}")
        # send a fresh message instead
        calendar_message = await query.message.reply_text(
            "📅 Please choose a date:", 
            reply_markup=calendar_markup
        )   
    
    return DATE_SELECTION

# helper function to build the calendar 
def build_calendar(year, month):
    keyboard = []

    # Get today's date
    today = dt.today().date()

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
                    button_text = f"{day}✅"  # Green checkmark next to the day
                else:
                    button_text = str(day)
                button = InlineKeyboardButton(button_text, callback_data=f"select_date_{date_str}")
                row.append(button)
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🏠", callback_data="back_to_home")])
    return InlineKeyboardMarkup(keyboard)
## 1 END

## 2
# helper function to generate time slots with 30-minute intervals
def generate_time_slots(date: datetime.datetime):
    time_slots = []
    start_time = datetime.datetime(date.year, date.month, date.day, 0, 0)  # Start at 9:00 AM
    start_time = timezone.localize(start_time)
    for _ in range(26):  
        end_time = start_time + timedelta(minutes=50)
        time_slots.append((start_time, end_time))
        start_time = end_time + timedelta(minutes=10) # Move to the next slot
    return time_slots

# handle the date chosen by user + displays the next timeslots
async def handle_calendar_selection(update: Update, context: CallbackContext) -> int:
    print("in handler_calendar_selection")

    multi_select_mode = context.user_data.get("multi_select_mode", False)
    multi_close_mode = context.user_data.get("multi_close_mode", False)
    back = context.user_data.get("back", False)
    from_confirmed = context.user_data.get("from_confirmed", False)

    query = update.callback_query
    await query.answer()

    # Initialize date_str
    date_str = None  # Default value to avoid UnboundLocalError

    # when canceling multi select mode
    if not multi_select_mode and back:
        selected_data = context.user_data.get("selected_date")

        # Set date_str from selected data
        date_str = selected_data.strftime("%Y-%m-%d")
    
    # when confirmed slot openings
    elif not multi_select_mode and from_confirmed:
        selected_data = context.user_data.get("selected_date")
        menu_messages = context.user_data.get('menu_message', [])
        
        # Set date_str from selected data
        date_str = selected_data.strftime("%Y-%m-%d")
    
    # when not in multi select mode, just seeing for the first time
    elif not multi_select_mode and not multi_close_mode:
        selected_data = query.data
        if selected_data.startswith("select_date_"):
            date_str = selected_data.replace("select_date_", "")
        else:
            return DATE_SELECTION
    
    elif multi_select_mode or multi_close_mode:
        selected_data = context.user_data.get("selected_date")
        if not selected_data: # shd not happen
            error_msg = await query.message.reply_text("❌ Please select a date first.")
            context.user_data.setdefault("messages_to_delete", []).append(error_msg.message_id)
            return DATE_SELECTION

        # Set date_str from selected data
        date_str = selected_data.strftime("%Y-%m-%d")
        
    # Process selected date
    fetch = None
    fetch_id = None
    if date_str:
        slot_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        try:
            fetch = await query.edit_message_text(f"Fetching your data for {slot_date.strftime("%A, %d %B %Y")}...")
            fetch_id = fetch.message_id
        except Exception as e:
            fetch = await query.message.reply_text(f"Fetching your data for {slot_date.strftime("%A, %d %B %Y")}...")
            fetch_id = fetch.message_id
    else:
        print(slot_date)
    # Store selected date in user_data for later use if needed
    context.user_data["selected_date"] = slot_date

    # Generate time slots for that day
    firebase_user_id = user_sessions[query.from_user.id]
    user = auth.get_user(firebase_user_id)
    email = user.email

    time_slots = generate_time_slots(slot_date)
    uuid = context.user_data['current_user'].uuid
    
    print(f"UUID: {uuid}")
    
    open_slots, booked_slots, completed_slots, noshow_slots, pending_slots = await get_slot_statuses(uuid, slot_date) # getting slot statuses for da dayyyyyyyyyyyyyyyyy

    time_slot_statuses = {}
    now = datetime.datetime.now(timezone)
    for start_time, end_time in time_slots:
        slot_str = start_time.strftime('%Y-%m-%d %H:%M')
        if slot_str in open_slots:
            time_slot_statuses[slot_str] = "open"
        elif slot_str in booked_slots:
            time_slot_statuses[slot_str] = "booked"
        elif slot_str in completed_slots:
            time_slot_statuses[slot_str] = "completed"
        elif slot_str in noshow_slots:
            time_slot_statuses[slot_str] = "noshow"
        elif slot_str in pending_slots:
            time_slot_statuses[slot_str] = "pending"
        elif start_time < now:
            pass
        else:
            time_slot_statuses[slot_str] = "closed"

    context.user_data["time_slot_statuses"] = time_slot_statuses # save it to user_data

    # Generate the keyboard with time slots
    keyboard = []
    openable_slots_present_flag = False # to determine whether open slots button exists
    closable_slots_present_flag = False
    
    counter = 1
    slots_line = []
    for start_time, end_time in time_slots:
        if counter > 2:
            keyboard.append(slots_line)
            slots_line = []
            counter = 1
        
        slot_str = start_time.strftime('%Y-%m-%d %H:%M')
        # label = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
        label = f"{start_time.strftime('%I:%M %p')}" # no longer show end times (not necessary)
        
        # flags
        expired_slot_flag = False
        
        # Add status labels and appropriate callback data 
        if slot_str in open_slots:
            cb_data = f"open_{slot_str}" if multi_close_mode else "noop"
            button = InlineKeyboardButton("💈 " + label, callback_data=cb_data)  # closable
            closable_slots_present_flag = True
        elif slot_str in completed_slots:
            button = InlineKeyboardButton("✅ " + label, callback_data=f"completed_{slot_str}")  # ------------------
        elif slot_str in noshow_slots:
            button = InlineKeyboardButton("❌ " + label, callback_data=f"noshow_{slot_str}")  # ------------------
        elif slot_str in pending_slots:
            button = InlineKeyboardButton("❔ " + label, callback_data=f"pending_{slot_str}")
        elif slot_str in booked_slots:
            button = InlineKeyboardButton("🤝 " + label, callback_data=f"booked_{slot_str}")  # MUST COME AFTER PENDING
        elif start_time < now: # dont show 
            expired_slot_flag = True
            pass
        else:  # Blocked slots are togglable
            cb_data = f"toggle_{slot_str}" if multi_select_mode else "noop_close"
            button = InlineKeyboardButton("💤 " + label, callback_data=cb_data)  # Actionable for blocked slots
            openable_slots_present_flag = True
        if expired_slot_flag == False:
            slots_line.append(button)
        counter+=1

    if len(keyboard) == 0:
        keyboard.append([InlineKeyboardButton("No appointments to show!", callback_data="none")])
    
    # Append the confirm and back buttons
    if openable_slots_present_flag:
        if not multi_select_mode:
            keyboard.append([InlineKeyboardButton("Open Slots", callback_data="open_multi")])
        elif multi_select_mode:
            keyboard.append([InlineKeyboardButton("✅ Confirm", callback_data="confirm_slots"), 
                             InlineKeyboardButton("🚫 Cancel", callback_data="not_open_multi")])

    if closable_slots_present_flag:
        if not multi_close_mode:
            keyboard.append([InlineKeyboardButton("Close Slots", callback_data="close_multi")])
        elif multi_close_mode:
            keyboard.append([InlineKeyboardButton("✅ Confirm", callback_data="confirm_close_slots"), 
                             InlineKeyboardButton("🚫 Cancel", callback_data="not_close_multi")])
            

    keyboard.append([
        InlineKeyboardButton("🔙 Back to calendar", callback_data="back_to_calendar"),
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = None
    try:
        bot = context.bot
        message = await bot.edit_message_text(f"📆 {slot_date.strftime("%A, %d %B %Y")}", chat_id = query.message.chat_id, message_id = fetch_id, reply_markup=reply_markup)
    except Exception as e:
        print(f"ERROR: {e}")
        message = await bot.edit_message_text(f"📆 {slot_date.strftime("%A, %d %B %Y")}", chat_id = query.message.chat_id, message_id = fetch_id, reply_markup=reply_markup)

    context.user_data.setdefault('messages_to_delete', []).append(query.message.message_id)
    if from_confirmed:
        from_confirmed = False
        menu_messages.append(message.message_id)
    
    return TIME_SELECTION

# turn on/off for opening/closing slots
async def toggle_multi_mode(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data  # one of: "open_multi", "not_open_multi", "close_multi", "not_close_multi"

    # Clear any prior selection
    if action in ("not_open_multi", "not_close_multi"):
        context.user_data["selected_slots"] = set()

    # Set flags based on action
    if action == "open_multi":
        context.user_data["multi_select_mode"] = True
        context.user_data["multi_close_mode"] = False
        context.user_data["back"] = False

    elif action == "not_open_multi":
        context.user_data["multi_select_mode"] = False
        context.user_data["back"] = True

    elif action == "close_multi":
        context.user_data["multi_close_mode"] = True
        context.user_data["multi_select_mode"] = False

    elif action == "not_close_multi":
        context.user_data["multi_close_mode"] = False

    # Rebuild the calendar keyboard with the new mode
    await handle_calendar_selection(update, context)

async def get_slot_statuses(uuid: str, date: datetime.datetime):
    print("in get_slot_statuses")
    sg_tz = pytz_timezone("Asia/Singapore")
    now_utc = dt.now(UTC)
    now = now_utc.astimezone(sg_tz)

    open_ref = db.collection("open slots").where("barber_id", "==", uuid).where("`start time`", ">=", now)
    booked_ref = db.collection("booked slots").where("barber_id", "==", uuid).where('no_show', '==', False).where('completed', '==', False).where('`start time`', '>=', now)
    noshow_ref = db.collection("booked slots").where("barber_id", "==", uuid).where('no_show', '==', True)
    completed_ref = db.collection("booked slots").where("barber_id", "==", uuid).where('completed', '==', True)
    pending_ref =  db.collection('booked slots')\
        .where('barber_id', '==', uuid).where('`start time`', '<=', now).where('completed', '==', False).where('no_show', '==', False)

    open_docs = list(open_ref.stream())
    booked_docs = list(booked_ref.stream())
    noshow_docs = list(noshow_ref.stream())
    completed_docs = list(completed_ref.stream())
    pending_docs = list(pending_ref.stream())

    open_slots = set()
    booked_slots = set() 
    completed_slots = set()
    noshow_slots = set()
    pending_slots = set()

    slot_docs = [open_docs, booked_docs, completed_docs, noshow_docs, pending_docs]
    slot_sets = [open_slots, booked_slots, completed_slots, noshow_slots, pending_slots]

    for docs, slot_set in zip(slot_docs, slot_sets):
        for doc in docs:
            start_time = doc.to_dict().get("start time")

            if start_time.tzinfo is None:
                start_time = sg_tz.localize(start_time)
            else:
                start_time = start_time.astimezone(sg_tz)

            if start_time.date() == date.date():
                slot_set.add(start_time.strftime('%Y-%m-%d %H:%M'))

    return open_slots, booked_slots, completed_slots, noshow_slots, pending_slots

# handle the pagination of the calendar
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
## 2 END

## 3
# handle the timeslots chosen
async def manage_time_slot_actions(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data

    # Shared state
    slot_date = context.user_data["selected_date"]
    statuses = context.user_data["time_slot_statuses"]
    selected = context.user_data.setdefault("selected_slots", set())
    open_mode  = context.user_data.get("multi_select_mode", False)
    close_mode = context.user_data.get("multi_close_mode", False)

    # ───── Selection toggles ─────────────────────────────────
    if action.startswith("toggle_") and open_mode:
        # open-mode toggles closed slots
        slot = action.removeprefix("toggle_")
        selected.symmetric_difference_update({slot})
    elif action.startswith("open_") and close_mode:
        # close-mode toggles open slots
        slot = action.removeprefix("open_")
        selected.symmetric_difference_update({slot})

    # ───── Confirm opening new slots ─────────────────────────
    elif action == "confirm_slots":
        if not selected:
            await query.message.reply_text("❌ You haven't selected any slots.")
            return TIME_SELECTION

        firebase_id = user_sessions[query.from_user.id]
        email = auth.get_user(firebase_id).email
        uuid = context.user_data['current_user'].uuid
        for slot_str in list(selected):
            start = timezone.localize(
                datetime.datetime.strptime(slot_str, "%Y-%m-%d %H:%M")
            )
            end = start + timedelta(minutes=30)
            db.collection("open slots").add({
                "barber_id": uuid,
                "barber_email": email,
                "start time":   start,
                "end time":     end
            })

        msg = await query.message.reply_text(
            f"✅ {len(selected)} slot(s) created successfully!"
        )
        context.user_data.setdefault("messages_to_delete", []).append(msg.message_id)
        context.user_data["multi_select_mode"] = False
        context.user_data["from_confirmed"]    = True
        selected.clear()

        # Ask to notify followers
        await asyncio.sleep(1)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes", callback_data="notify_yes"),
            InlineKeyboardButton("No",  callback_data="notify_no")
        ]])
        await query.message.reply_text("Notify your followers?", reply_markup=kb)
        return TIME_SELECTION

    # ───── Confirm closing existing slots ────────────────────
    elif action == "confirm_close_slots":
        if not selected:
            await query.message.reply_text("❌ You haven't selected any slots.")
            return TIME_SELECTION

        firebase_id = user_sessions[query.from_user.id]
        uuid = context.user_data['current_user'].uuid
        for slot_str in list(selected):
            start = timezone.localize(
                datetime.datetime.strptime(slot_str, "%Y-%m-%d %H:%M")
            )
            docs = db.collection("open slots") \
                     .where("barber_id","==",uuid) \
                     .where("`start time`","==",start).stream()
            for doc in docs:
                db.collection("open slots").document(doc.id).delete()

        msg = await query.message.reply_text(
            f"✅ {len(selected)} slot(s) deleted successfully!"
        )
        context.user_data.setdefault("messages_to_delete", []).append(msg.message_id)
        context.user_data["multi_close_mode"] = False
        context.user_data["from_confirmed"]   = True
        selected.clear()

        await asyncio.sleep(0.5)
        # clean up and reload calendar
        try:
            await context.bot.delete_messages(
                chat_id=query.message.chat_id,
                message_ids=context.user_data["messages_to_delete"]
            )
        except:
            pass
        return await handle_calendar_selection(update, context)

    # ───── Otherwise: rebuild keyboard for toggles ──────────
    time_slots = generate_time_slots(slot_date)
    buttons = []
    now = datetime.datetime.now(timezone)

    counter = 1
    slots_line = []
    for start, end in time_slots:
        
        if counter > 2:
            buttons.append(slots_line)
            slots_line = []
            counter = 1
        
        key    = start.strftime('%Y-%m-%d %H:%M')
        label  = f"{start.strftime('%I:%M %p')}"
        status = statuses.get(key, None)
        cb     = "noop"
        expired = False
        
        # status icons
        if status == "open":
            label = f"💈 {label}"
            if close_mode:
                cb = f"open_{key}"
        elif status == "closed":
            label = f"💤 {label}"
            if open_mode:
                cb = f"toggle_{key}"
        elif status == "booked":
            label = f"🤝 {label}"
        elif status == "pending":
            label = f"❔ {label}"
        elif status == "completed":
            label = f"✅ {label}"
        elif status == "noshow":
            label = f"❌ {label}"
        else:
            expired = True

        # mark selected
        if key in selected:
            label = f"{label} ✅"
            # cb remains toggle_ or open_ so user can un-toggle

        if expired == False:
            slots_line.append(InlineKeyboardButton(label, callback_data=cb))
            counter += 1

    # Back button
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_calendar")])

    # Confirm / Cancel row
    if open_mode:
        buttons.append([
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_slots"),
            InlineKeyboardButton("🚫 Cancel",  callback_data="not_open_multi"),
        ])
    elif close_mode:
        buttons.append([
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_close_slots"),
            InlineKeyboardButton("🚫 Cancel",  callback_data="not_close_multi"),
        ])

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return TIME_SELECTION

async def notify_followers(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    user_choice = query.data  # either "notify_yes" or "notify_no"
    
    email = context.user_data.get('current_user', None).email

    messages_to_delete = context.user_data.get('messages_to_delete', [])

    if user_choice == "notify_yes":
        try:
            current_user = context.user_data['current_user']
            print(current_user.uuid)
            doc_ref = db.collection('followers').document(current_user.uuid).collection('users')
            users_docs = doc_ref.stream()

            user_ids = [doc.id for doc in users_docs]
            
            for telegram_user_id in user_ids:
                print(telegram_user_id)
                try:
                    await context.bot.send_message(
                        chat_id=int(telegram_user_id),
                        text=f"{current_user.name} just opened new slots! Check them out!"
                    )
                    print("sent")
                except Exception as e:
                    print(f"Failed to message user {telegram_user_id}: {e}")

        except Exception as e:
            print(f"Error: {e}")

    # Delete previous bot messages (if any)
    try:
        await context.bot.delete_messages(
            chat_id=query.message.chat_id,
            message_ids=messages_to_delete
        )
    except Exception as e:
        print(f"Error deleting messages: {e}")

    # Continue to calendar selection
    await handle_calendar_selection(update, context)
## 3 END

# handlers to ignore unclickable slots
async def noop(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer(text="This slot is open for booking.", show_alert=True)

# shows booked details
async def noop_booked(update: Update, context: CallbackContext) -> None:
    callback_query = update.callback_query
    callback_data = callback_query.data  # e.g., "booked_2025-04-10 13:00" or "noshow_2025-04-10 13:00"

    # Extract prefix and datetime using regex
    match = re.match(r"(booked|noshow|completed|pending)_(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", callback_data)
    prefix = match.group(1)        # "booked" or "noshow" or "completed"
    date_time_str = match.group(2) # "2025-04-10 13:00"

    try:
        # Parse and convert to UTC-aware datetime
        slot_datetime = timezone.localize(dt.strptime(date_time_str, "%Y-%m-%d %H:%M")).astimezone(pytz.UTC)
    except ValueError:
        print("Error: Invalid datetime format.")
        return

    # Get barber email from user context
    current_user = context.user_data.get('current_user')
    uuid = current_user.uuid
    email = current_user.email

    # Firestore query
    collection_ref = db.collection('booked slots')
    firestore_query = collection_ref.where("barber_id", "==", uuid).where("`start time`", "==", slot_datetime)
    print(f"{email}, {slot_datetime}")
    
    
    # Debug: print the query before executing
    print(f"Firestore query: {firestore_query}")

    results = firestore_query.stream()

    # Convert the results into a list and check if there are any results
    results_list = list(results)
    if not results_list:
        print("No results found for the query.")
        return  # Exit if no results are found

    # Since there's only one result, we don't need to loop
    doc = results_list[0]
    data = doc.to_dict()

    barber_email = data.get("barber_email")
    barber_name = data.get("barber_name")
    customer_id = data.get("booked_by", {}).get("customer_id")
    phone_number = data.get("booked_by", {}).get("phone_number")
    username = data.get("booked_by", {}).get("username")
    service_name = data.get("service_name")
    service_price = data.get("service_price")
    start_time = data.get("start time")
    end_time = data.get("end time")
    

    def convert_to_sg_time(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))  # Firestore timestamps are in UTC
        return dt.astimezone(ZoneInfo("Asia/Singapore"))

    start_time = convert_to_sg_time(start_time)
    end_time = convert_to_sg_time(end_time)

    start_time_str = start_time.strftime("%B %d, %Y at %I:%M:%S %p") if start_time else "N/A"
    end_time_str = end_time.strftime("%B %d, %Y at %I:%M:%S %p") if end_time else "N/A"

    status_line = ("❌ NO SHOW\n" if prefix == "noshow" else "✅ COMPLETED\n" if prefix == "completed" else "❔ PENDING\n" if prefix == "pending" else "")


    message = f"""
{status_line}✨ Service Details:
🔧 Service: {service_name} - ${service_price}
⏰ Start Time: {start_time_str}

👤 Customer Info:
📝 Username: {username}
📞 Phone: {phone_number}
"""


    url = f"tg://user?id={customer_id}"
    
    keyboard = []
    if prefix == "pending": # option for pending appts
        keyboard.append([
                InlineKeyboardButton("❌ No Show", callback_data=f"NO_SHOW:{doc.id}"),
                InlineKeyboardButton("✅ Completed", callback_data=f"COMPLETED:{doc.id}")
            ])

    keyboard.append([InlineKeyboardButton("💬 Contact Client", url=url),InlineKeyboardButton("🔙 Back", callback_data="not_open_multi")])
    keyboard = InlineKeyboardMarkup(keyboard)
    # Send the message as an alert
    msg = await callback_query.edit_message_text(text=message, reply_markup=keyboard)
    context.user_data['booked_msg_id'] = msg.message_id

async def noop_close(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer(text="This slot is closed.", show_alert=True)

async def handle_appointment_status(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    status, doc_id = query.data.split(":")

    # pull out any existing alert
    prev = context.user_data.get('alert')  # { 'status': str, 'chat_id': int, 'msg_id': int }

    # build the Yes/No keyboard
    if status in ('NO_SHOW', 'COMPLETED'):
        text = ("Mark this appointment as 'No Show'?"
                if status == 'NO_SHOW'
                else "Mark this appointment as 'Completed'?")
        kb = [[
            InlineKeyboardButton("Yes", callback_data=f"CONFIRM_{status}:{doc_id}"),
            InlineKeyboardButton("No", callback_data=f"cancel:{doc_id}")
        ]]
        # if same alert is up, edit it
        if prev and prev['status'] == status:
            msg = await context.bot.edit_message_text(
                text=text,
                chat_id=prev['chat_id'],
                message_id=prev['msg_id'],
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            # delete old alert if it’s a different type
            if prev:
                await context.bot.delete_message(
                    chat_id=prev['chat_id'],
                    message_id=prev['msg_id']
                )
            msg = await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

        # save new alert info
        context.user_data['alert'] = {
            'status': status,
            'chat_id': msg.chat.id,
            'msg_id': msg.message_id
        }
        return

    # CONFIRM or CANCEL
    if status.startswith('CONFIRM_'):
        field = 'no_show' if 'NO_SHOW' in status else 'completed'
        db.collection('booked slots').document(doc_id).update({field: True})
        # delete the prompt alert
        if prev:
            await context.bot.delete_message(
                chat_id=prev['chat_id'],
                message_id=prev['msg_id']
            )
        # clear alert state
        context.user_data.pop('alert', None)

        # send the “marked” message and auto-expire
        done_text = ("Appointment marked as 'No Show'."
                     if field == 'no_show'
                     else "Appointment marked as 'Completed'.")
        done_msg = await query.message.reply_text(done_text)

        # delete existing calendar message to show the time slots instead
        msg_id = context.user_data.get('booked_msg_id',None)
        if msg_id:
           await context.bot.delete_message(
                        chat_id = update.effective_chat.id,
                        message_id=msg_id
                    )
           context.user_data['msg_id'] = None

        context.user_data["back"] = True
        await handle_calendar_selection(update, context)
        await asyncio.sleep(1)
        await context.bot.delete_message(
            chat_id=done_msg.chat.id,
            message_id=done_msg.message_id
        )
        

    if status == 'cancel':
        # just delete whatever alert is up
        if prev:
            await context.bot.delete_message(
                chat_id=prev['chat_id'],
                message_id=prev['msg_id']
            )
            context.user_data.pop('alert', None)
        return

# ------------------------ FALLBACKS ------------------------
async def back_to_home(update:Update, context:CallbackContext) -> None:
    await menu(update, context)
    return ConversationHandler.END
    
async def back_to_calendar(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # Optionally, clear any data that shouldn't be carried over to the new flow
    context.user_data["selected_slots"] = set()  # Clear selected slots
    
    context.user_data["multi_select_mode"] = False  # disable multi-select mode

    context.user_data["from_confirmed"] = False
    context.user_data["multi_close_mode"] = False

    # Debugging: Print out the callback data to confirm it's being caught
    print(f"Back to Calendar callback received: {query.data}")
    
    context.user_data["back"] = False
    context.user_data.pop("selected_date", None)
    
    # Go back to the entry point by calling `ask_for_date`
    return await ask_for_date(update, context)


# handler to add to app
calendar_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(ask_for_date, pattern = r"^calendar$")],
    states={
        DATE_SELECTION: [
            CommandHandler("calendar", ask_for_date), # incase its called again
            CallbackQueryHandler(handle_calendar_selection, pattern=r"^select_date_\d{4}-\d{2}-\d{2}$"),
            CallbackQueryHandler(navigate_calendar, pattern=r"^(prev|next)_\d{4}_\d{2}$"),
        ],
        TIME_SELECTION: [
            CallbackQueryHandler(noop, pattern="^noop$"),
            CallbackQueryHandler(toggle_multi_mode, pattern=r"^(?:open_multi|not_open_multi|close_multi|not_close_multi)$"),
            CallbackQueryHandler(noop_booked, pattern=r"^(?:booked|noshow|completed|pending)_\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
            CallbackQueryHandler(noop_close, pattern="^noop_close$"),
            CallbackQueryHandler(manage_time_slot_actions,pattern=r"^(?:toggle_|open_|confirm_slots|confirm_close_slots)"),
            CallbackQueryHandler(handle_appointment_status, pattern="^(NO_SHOW|CONFIRM_NO_SHOW|COMPLETED|cancel|CONFIRM_COMPLETED):"),
            CallbackQueryHandler(notify_followers, pattern=r"^notify_(yes|no)"),
        ]
    },
    fallbacks=[CommandHandler("menu", back_to_home), 
               CallbackQueryHandler(back_to_home, pattern=r"^back_to_home$"),
               CallbackQueryHandler(back_to_calendar, pattern=r"^back_to_calendar$"),],
    per_user=True,
    allow_reentry=True
)
