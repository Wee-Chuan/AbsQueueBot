# Standard library imports
from datetime import datetime, timedelta
import calendar

# Third-party imports
import pytz
from firebase_admin import firestore

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler, CallbackContext

# Local imports
from barber_side.utils.globals import db, timezone, auth, user_sessions
from barber_side.handlers.menu_handlers import menu

# Conversation states
APPOINTMENTS_MENU = 0
DATE_SELECTION = 1
TIME_SELECTION = 2

# --- Helpers for cleaning up messages ---
# async def _delete_messages(update: Update, context: CallbackContext, key: str):
#     try:
#         msgs = context.user_data.pop(key, [])
#         if msgs:
#             chat_id = (
#                 update.callback_query.message.chat_id
#                 if update.callback_query
#                 else update.message.chat_id
#             )
#             await context.bot.delete_messages(chat_id=chat_id, message_ids=msgs)
#     except Exception as e:
#         print(f"Error deleting {key}: {e}")

# async def clear_conversation(update: Update, context: CallbackContext):
#     await _delete_messages(update, context, 'messages_to_delete')

# async def cleanup_chat_flow(update: Update, context: CallbackContext):
#     await _delete_messages(update, context, 'chat_flow')

# --- /appointments menu ---
async def appointments_menu(update: Update, context: CallbackContext) -> int:
    keyboard = [
        # [InlineKeyboardButton("📅 Today's Appointments", callback_data="today")],
        [InlineKeyboardButton("🗓️ Pending Appointments", callback_data="pending")],
        [InlineKeyboardButton("🚫 No Show Appointments", callback_data="no_show")],
        [InlineKeyboardButton("✅ Completed Appointments", callback_data="completed")],
        # [InlineKeyboardButton("📒 Day View", callback_data="day_view")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        message = await update.message.edit_text("Please choose an option:", reply_markup=reply_markup)
    else:
        message = await update.callback_query.message.edit_text("Please choose an option:", reply_markup=reply_markup)

    return APPOINTMENTS_MENU

# --- Cancel handler ---
async def cancel(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        # await clear_conversation(update, context)
        # await cleanup_chat_flow(update, context
        await menu(update, context)
        return ConversationHandler.END

# --- Today's appointments ---
# async def show_todays_appointments(update: Update, context: CallbackContext):
#     # remove loading from query
#     query = update.callback_query
#     await query.answer()
#     # await cleanup_chat_flow(update, context)

#     # login check
#     user = context.user_data.get('current_user')
#     if not user:
#         await query.message.reply_text("User not logged in.")
#         return

#     # query to firestore for todays appts
#     email = user.email
#     now = datetime.now(pytz.UTC)
#     start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
#     end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

#     results = (
#         db.collection('booked slots')
#           .where('barber_email', '==', email)
#           .where('`start time`', '>=', start_of_day)
#           .where('`start time`', '<=', end_of_day)
#           .stream()
#     )
    
#     appointments = []
#     for doc in results:
#         data = doc.to_dict()
#         st = data.get('start time')
#         if isinstance(st, datetime):
#             data['doc_id'] = doc.id
#             appointments.append(data)

#     # build message to display appts
#     if appointments:
#         reply_markup = build_appointments_keyboard(appointments)
#         message = await query.message.edit_text(
#             "📅 *Today's Appointments:*\n_Select one for more info!_",
#             reply_markup=reply_markup,
#             parse_mode='Markdown'
#         )
#     else:
#         reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")]])
#         message = await query.message.edit_text("No appointments found for today.", reply_markup=reply_markup)

# --- Build single appointments information keyboard ---
def build_appointments_keyboard(appointments):
    keyboard = []
    for i, appt in enumerate(appointments, start=1):
        time_str = appt['start time'].astimezone().strftime("%H:%M")
        name = appt.get('booked_by', {}).get('username', 'Unknown')
        svc = appt.get('service_name', 'Unknown Service')
        doc_id = appt.get('doc_id', str(i))
        text = f"{i}. {name} - {svc} at {time_str}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"appointment_{doc_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_appt_menu")])
    return InlineKeyboardMarkup(keyboard)

# --- Single appointment details ---
from datetime import datetime as dt
from zoneinfo import ZoneInfo
import pytz
import re

async def handle_single_appointment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # e.g., query.data = "COMPLETED_appointment_abc123" or "appointment_def456"
    match = re.match(r"^(COMPLETED|NOSHOW)?appointment_(.+)", query.data)
    if not match:
        await query.message.reply_text("Invalid callback data format.")
        return

    prefix = match.group(1) or ""  # "COMPLETED", "NOSHOW", or "" (empty string if no prefix)
    doc_id = match.group(2)        # The actual Firestore document ID

    doc_ref = firestore.client().collection('booked slots').document(doc_id)
    doc = doc_ref.get()
    if not doc.exists:
        await query.message.reply_text("Appointment not found. It might have been removed.")
        return

    data = doc.to_dict()

    # pull out fields
    barber_email   = data.get("barber_email", "Unknown")
    barber_name    = data.get("barber_name", "Unknown")
    service_name   = data.get("service_name", "Unknown")
    service_price  = data.get("service_price", "N/A")
    start_time_utc = data.get("start time")    # Firestore timestamp
    end_time_utc   = data.get("end time")

    booked_by = data.get("booked_by", {})
    customer_id   = booked_by.get("customer_id", "")
    username      = booked_by.get("username", "Unknown")
    phone_number  = booked_by.get("phone_number", "Unknown")

    # helper to convert UTC timestamp to Asia/Singapore
    def to_sg(dt_obj):
        if dt_obj is None:
            return None
        # ensure tz-aware
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=ZoneInfo("UTC"))
        return dt_obj.astimezone(ZoneInfo("Asia/Singapore"))

    start_sg = to_sg(start_time_utc)
    end_sg   = to_sg(end_time_utc)

    start_str = start_sg.strftime("%B %d, %Y at %I:%M %p") if start_sg else "N/A"
    end_str   = end_sg.strftime("%B %d, %Y at %I:%M %p")   if end_sg   else "N/A"

    status_line = ("❌ NO SHOW\n" if prefix == "NOSHOW" else "✅ COMPLETED\n" if prefix == "COMPLETED" else "")

    # build the message
    message = f"""
{status_line}✨ Service Details:
🔧 Service: {service_name} — ${service_price}
⏰ Start Time: {start_str}
End Time: {end_str}

👤 Customer Info:
📝 Username: {username}
📞 Phone: {phone_number}
    """

    back_cb = ""
    if prefix == "COMPLETED":
        back_cb = "completed"
    elif prefix == "NOSHOW":
        back_cb = "no_show"
    
    # inline keyboard: Contact Client + Back
    url = f"tg://user?id={customer_id}"
    keyboard = [
        [InlineKeyboardButton("💬 Contact Client", url=url),
         InlineKeyboardButton("🔙 Back", callback_data=back_cb)]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # replace the message in-place (like noop_booked)
    await query.edit_message_text(text=message, reply_markup=markup)

# --- Pending appointments ---
async def handle_pending_appointments(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    # await cleanup_chat_flow(update, context)

    email = context.user_data.get('current_user').email
    now = datetime.now(pytz.UTC)
    results = (
        db.collection('booked slots')
          .where('barber_email', '==', email)
          .where('`start time`', '<=', now)
          .where('completed', '==', False)
          .where('no_show', '==', False)
          .stream()
    )
    keyboard = []
    for doc in results:
        d = doc.to_dict()
        tm = d.get('start time').astimezone().strftime('%H:%M')
        name = d.get('booked_by', {}).get('username', 'Unknown')
        label = f"📅 {d.get('start time').astimezone().strftime('%d %b')} | 🕰️ {tm} | 👤 {name}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"pending_appt:{doc.id}")])
        keyboard.append([
            InlineKeyboardButton("❌ No Show", callback_data=f"NO_SHOW:{doc.id}"),
            InlineKeyboardButton("✅ Completed", callback_data=f"COMPLETED:{doc.id}")
        ])
    if keyboard:
        keyboard.append([InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")])
        msg = await query.message.edit_text(
            "🔔 *Pending Appointments:* Choose below to manage:",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")]])
        msg = await query.message.edit_text("✅ No pending appointments found.", reply_markup=reply_markup, parse_mode='Markdown')

# --- Appointment status actions ---
async def handle_appointment_status(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    # await cleanup_chat_flow(update, context)

    status, doc_id = query.data.split(":")
    if status == 'NO_SHOW':
        kb = [[InlineKeyboardButton("Yes", callback_data=f"CONFIRM_NO_SHOW:{doc_id}"), InlineKeyboardButton("No", callback_data="cancel")]]
        msg = await query.message.reply_text("Mark this appointment as 'No Show'?", reply_markup=InlineKeyboardMarkup(kb))
    elif status == 'CONFIRM_NO_SHOW':
        db.collection('booked slots').document(doc_id).update({'no_show': True})
        msg = await query.message.reply_text("Appointment marked as 'No Show'.")
    elif status == 'COMPLETED':
        db.collection('booked slots').document(doc_id).update({'completed': True})
        msg = await query.message.reply_text("Appointment marked as 'Completed'.")
    else:
        msg = await query.message.reply_text("Action canceled.")

    context.user_data.setdefault('chat_flow', []).append(msg.message_id)
    await appointments_menu(update, context)

# --- Pagination keyboard for completed/no-show ---
def generate_appointment_keyboard(appointments, prefix, page=0, per_page=5):
    total = len(appointments)
    start = page * per_page
    sliced = appointments[start:start+per_page]
    kb = []
    for doc in sliced:
        d = doc.to_dict()
        ts = d['start time'].astimezone().strftime('%d %b %H:%M')
        name = d.get('booked_by', {}).get('username', '')
        price = d.get('service_price', '')
        kb.append([InlineKeyboardButton(f"{ts} -- Client: {name}", callback_data=f"{prefix}appointment_{doc.id}")])
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}_PAGE:{page-1}"))
    if start+per_page < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}_PAGE:{page+1}"))
    if nav:
        kb.append(nav)
    return InlineKeyboardMarkup(kb)

async def handle_completed_appointments(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer(); #await cleanup_chat_flow(update, context)
    email = context.user_data.get('current_user').email
    docs = list(db.collection('booked slots').where('barber_email','==',email).where('completed','==',True).stream())
    if docs:
        reply_markup = generate_appointment_keyboard(docs, prefix="COMPLETED")
        keyboard = list(reply_markup.inline_keyboard)
        keyboard.append([InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")])
        msg = await query.message.edit_text("✅ *Completed Appointments:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['completed_appointments'] = docs
    else:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")]])
        msg = await query.message.edit_text("❌ No completed appointments.", reply_markup=reply_markup, parse_mode='Markdown')
    return APPOINTMENTS_MENU

async def handle_no_show_appointments(update: Update, context: CallbackContext):
    query = update.callback_query; await query.answer(); #await cleanup_chat_flow(update, context)
    email = context.user_data.get('current_user').email
    docs = list(db.collection('booked slots').where('barber_email','==',email).where('no_show','==',True).stream())
    if docs:
        reply_markup = generate_appointment_keyboard(docs, prefix="NOSHOW")
        keyboard = list(reply_markup.inline_keyboard)
        keyboard.append([InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")])
        msg = await query.message.edit_text("⚠️ *No-Show Appointments:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['no_show_appointments'] = docs
    else:
        msg = await query.message.edit_text("✅ No no-show appointments.", parse_mode='Markdown')
    context.user_data.setdefault('chat_flow', []).append(msg.message_id)
    return APPOINTMENTS_MENU

async def handle_appointment_pagination(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    prefix, page = query.data.split(":")
    page = int(page)

    key = 'completed_appointments' if prefix.startswith('COMPLETED') else 'no_show_appointments'
    appts = context.user_data.get(key, [])

    # Generate the keyboard
    reply_markup = generate_appointment_keyboard(appts, page=page, prefix=prefix.split('_')[0])

    kb_rows = list(reply_markup.inline_keyboard)
    
    # Add the back button
    kb_rows.append([InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")])

    # Create the new markup
    reply_markup = InlineKeyboardMarkup(kb_rows)

    # Update the message
    await query.message.edit_reply_markup(reply_markup=reply_markup)


# go back to appt menu
async def back_to_appt_menu(update:Update, context:CallbackContext) -> None:
    await appointments_menu(update, context)

# --- Conversation handlers registration ---
appointments_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(appointments_menu, pattern = r"^appointments$")],
    states={
        APPOINTMENTS_MENU: [
            CommandHandler("appointments", appointments_menu),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            # CallbackQueryHandler(show_todays_appointments, pattern="^today$"),
            CallbackQueryHandler(handle_pending_appointments, pattern="^pending$"),
            CallbackQueryHandler(handle_no_show_appointments, pattern="^no_show$"),
            CallbackQueryHandler(handle_completed_appointments, pattern="^completed$"),
            CallbackQueryHandler(handle_single_appointment, pattern=r"^(COMPLETED|NOSHOW)?appointment_"),
            CallbackQueryHandler(handle_appointment_status, pattern="^(NO_SHOW|CONFIRM_NO_SHOW|COMPLETED|cancel):"),
            CallbackQueryHandler(handle_appointment_pagination, pattern="^(COMPLETED_PAGE|NOSHOW_PAGE):"),
            CallbackQueryHandler(back_to_appt_menu, pattern=r"^back_to_appt_menu$"),
        ],
    },
    fallbacks=[],
    per_user=True,
    per_chat=True,
    allow_reentry=True
)














# ### Day View Handlers ###
# # --- Day view handlers ---
# async def ask_for_date(update: Update, context: CallbackContext) -> int:
#     # await cleanup_chat_flow(update, context)
#     query = update.callback_query; await query.answer()
#     if not context.user_data.get('logged_in'):
#         await query.message.reply_text("Please log in first!")
#         return
#     now = datetime.now()
#     cal = build_calendar(now.year, now.month)
#     cal_msg = await query.message.edit_text(f"📅 Choose a date you want to view:", reply_markup=cal)
    
#     return DATE_SELECTION

# # ... (other day view code remains unchanged)

# def build_calendar(year, month):
#     kb = []
#     today = datetime.today().date()
#     kb.append([
#         InlineKeyboardButton("«", callback_data=f"prev_{year}_{month:02d}"),
#         InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore"),
#         InlineKeyboardButton("»", callback_data=f"next_{year}_{month:02d}")
#     ])
#     kb.append([InlineKeyboardButton(d, callback_data="ignore") for d in ["Mo","Tu","We","Th","Fr","Sa","Su"]])
#     for week in calendar.monthcalendar(year, month):
#         row = []
#         for day in week:
#             if day == 0:
#                 row.append(InlineKeyboardButton(" ", callback_data="ignore"))
#             else:
#                 ds = f"{year}-{month:02d}-{day:02d}";
#                 txt = f"{day} ✅" if today == datetime(year, month, day).date() else str(day)
#                 row.append(InlineKeyboardButton(txt, callback_data=f"select_date_{ds}"))
#         kb.append(row)
#     kb.append([InlineKeyboardButton("🏠", callback_data="cancel"), InlineKeyboardButton("🔙", callback_data="back_to_appt_menu")])
#     return InlineKeyboardMarkup(kb)

# async def navigate_calendar(update: Update, context: CallbackContext):
#     query = update.callback_query; await query.answer()
#     dir, y, m = query.data.split("_"); y, m = int(y), int(m)
#     if dir == "prev": y, m = (y-1, 12) if m == 1 else (y, m-1)
#     else: y, m = (y+1, 1) if m == 12 else (y, m+1)
#     await query.edit_message_reply_markup(reply_markup=build_calendar(y, m))

# def generate_time_slots(date: datetime):
#     slots = []
#     st = timezone.localize(datetime(date.year, date.month, date.day, 9, 0))
#     for _ in range(16):
#         et = st + timedelta(minutes=30)
#         slots.append((st, et))
#         st = et
#     return slots

# async def handle_calendar_selection(update: Update, context: CallbackContext) -> int:
#     print("in handler_calendar_selection")

#     query = update.callback_query
#     await query.answer()

#     # Initialize date_str
#     selected_data = query.data
#     if selected_data.startswith("select_date_"):
#         date_str = selected_data.replace("select_date_", "")
    
#     print(date_str)
#     print(selected_data)
        
#     # Process selected date
#     if date_str:
#         slot_date = datetime.strptime(date_str, "%Y-%m-%d")

#     # Store selected date in user_data for later use if needed
#     context.user_data["selected_date"] = slot_date

#     # Generate time slots for that day
#     firebase_user_id = user_sessions[query.from_user.id]
#     user = auth.get_user(firebase_user_id)
#     email = user.email

#     time_slots = generate_time_slots(slot_date)
    
#     ## getting the slot status
#     no_show_slots, completed_slots = await get_slot_statuses(email, slot_date)

#     time_slot_statuses = {}
#     now = datetime.now(timezone)

#     for start_time, end_time in time_slots:
#         slot_str = start_time.strftime('%Y-%m-%d %H:%M')
#         if slot_str in no_show_slots:
#             time_slot_statuses[slot_str] = "no_show"
#         elif slot_str in completed_slots:
#             time_slot_statuses[slot_str] = "completed"
#         elif start_time < now:
#             time_slot_statuses[slot_str] = "past"
#         else:
#             time_slot_statuses[slot_str] = "blocked"


#     context.user_data["time_slot_statuses"] = time_slot_statuses
#     print(no_show_slots)
#     # Generate the keyboard with time slots
#     keyboard = []
#     for start_time, end_time in time_slots:
#         slot_str = start_time.strftime('%Y-%m-%d %H:%M')
#         label = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
#         if slot_str in no_show_slots:
#             print(slot_str)
#             label += " 🚫"
#             button = InlineKeyboardButton("🚫 " + label, callback_data="noop_noshow")
#             keyboard.append([button])
#         elif slot_str in completed_slots:
#             label += " ✅"
#             button = InlineKeyboardButton("✅ " + label, callback_data="noop_completed")
#             keyboard.append([button])
    
#     # if nothing to show
#     if len(keyboard) == 0:
#         button = InlineKeyboardButton("No slots to show", callback_data="noop")
#         keyboard.append([button])
#     # Append the confirm and back buttons
#     keyboard.append([
#         InlineKeyboardButton("🔙 Back", callback_data="back_to_calendar"),
#     ])

#     reply_markup = InlineKeyboardMarkup(keyboard)

#     # Edit the existing calendar message to show the time slots instead
#     await query.edit_message_text(f"📆 {slot_date.strftime("%A, %d %B %Y")}", reply_markup=reply_markup)

#     context.user_data.setdefault("messages_to_delete", []).append(query.message.message_id)
    
#     return TIME_SELECTION

# async def get_slot_statuses(email: str, date: datetime):
#     print("getting slot statuses")

#     # Create start and end of day in SGT
#     sod = timezone.localize(datetime(date.year, date.month, date.day, 0, 0, 0))
#     eod = timezone.localize(datetime(date.year, date.month, date.day, 23, 59, 59))

#     # Query Firestore with Singapore Time
#     no_show_docs = db.collection('booked slots')\
#         .where('barber_email', '==', email)\
#         .where('no_show', '==', True)\
#         .where('`start time`', '>=', sod)\
#         .where('`start time`', '<=', eod)\
#         .stream()

#     comp_docs = db.collection('booked slots')\
#         .where('barber_email', '==', email)\
#         .where('completed', '==', True)\
#         .where('`start time`', '>=', sod)\
#         .where('`start time`', '<=', eod)\
#         .stream()

#     ns, cs = set(), set()

#     for d in no_show_docs:
#         ts = d.to_dict()['start time']
#         if isinstance(ts, datetime):
#             if ts.tzinfo is None:
#                 ts = timezone.localize(ts)  # Assume SGT if naive
#             else:
#                 ts = ts.astimezone(timezone)  # Convert to SGT
#             ns.add(ts.strftime('%Y-%m-%d %H:%M'))

#     for d in comp_docs:
#         ts = d.to_dict()['start time']
#         if isinstance(ts, datetime):
#             if ts.tzinfo is None:
#                 ts = timezone.localize(ts)  # Assume SGT if naive
#             else:
#                 ts = ts.astimezone(timezone)  # Convert to SGT
#             cs.add(ts.strftime('%Y-%m-%d %H:%M'))

#     return ns, cs


# async def back_to_calendar(update: Update, context: CallbackContext) -> int:
#     query = update.callback_query; await query.answer()
#     context.user_data.pop('selected_slots', None)
#     context.user_data['multi_select_mode'] = False
#     return await ask_for_date(update, context)

# # Day view conversation handler
# # day_view_handler = ConversationHandler(
# #     entry_points=[CallbackQueryHandler(ask_for_date, pattern="^day_view$")],
# #     states={
# #         DATE_SELECTION: [
# #             CallbackQueryHandler(ask_for_date, pattern="^day_view$"),
# #             CallbackQueryHandler(handle_calendar_selection, pattern="^select_date_\d{4}-\d{2}-\d{2}$"),
# #             CallbackQueryHandler(navigate_calendar, pattern="^(prev|next)_\d{4}_\d{2}$"),
# #             CallbackQueryHandler(back_to_appt_menu, pattern=r"^back_to_appt_menu$"),
# #         ],
# #         TIME_SELECTION: [
# #             CallbackQueryHandler(ask_for_date, pattern="^day_view$"),
# #             CallbackQueryHandler(back_to_calendar, pattern="^back_to_calendar$"),
# #         ],
# #     },
# #     fallbacks=[],
# #     per_user=True,
# #     allow_reentry=True
# # )
