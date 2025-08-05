# ==================== IMPORTS ====================
import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# telegram imports
from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

# global imports
from client_side.utils.globals import *
from client_side.utils.core_commands import *
from client_side.utils.keyboards import Keyboards
from client_side.utils.messages import Messages

# classes imports
from shared.utils import HelperUtils
from client_side.classes.booking import Booking

from datetime import datetime, timedelta

# ==================== CONSTANTS ====================
VIEW_BOOKINGS_OPTIONS, VIEW_UPCOMING_BOOKINGS, VIEW_PAST_BOOKINGS, VIEW_CALENDAR, CONFIRM_CANCEL, CONFIRM_COMPLETE, RATE_SERVICE, LEAVE_REVIEW  = range(8)

# ==================== VIEW BOOKINGS FLOW ====================
@HelperUtils.check_conversation_active
async def start_bookings(update: Update, context: CallbackContext) -> int:
    """Show options for viewing bookings (upcoming, past, calendar)."""
    Booking.initialize_booking(context)
    query = update.callback_query

    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📅 Upcoming Bookings", callback_data="view_upcoming")],
        [InlineKeyboardButton("📝 Past Bookings", callback_data="view_past")],
        [InlineKeyboardButton("🗓 Calendar View", callback_data="view_calendar")],
        [InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "📖 How would you like to view your bookings?"

    msg = await query.edit_message_text(message, reply_markup=reply_markup)
    HelperUtils.store_message_id(context, msg.message_id)

    return VIEW_BOOKINGS_OPTIONS

@HelperUtils.check_conversation_active
async def view_upcoming_bookings(update: Update, context: CallbackContext) -> int:
    """Show only upcoming bookings."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    # Get all upcoming bookings (not completed, not no-show, in future)
    upcoming_bookings = Booking.get_upcoming_bookings(user_id, db)

    upcoming_bookings = sorted(upcoming_bookings, key=lambda x: x[1])  # x[1] is the start_time

    if not upcoming_bookings:
        message = "📭 You don't have any upcoming bookings."
        keyboard = [
            [InlineKeyboardButton("◀ Back to Options", callback_data="back_to_options")],
            [InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")]
        ]
    else:
        message = "📅 <b>Your Upcoming Bookings:</b>\n\n"
        keyboard = []

        # Group bookings by date
        bookings_by_date = {}
        for booking_id, start_time, details in upcoming_bookings:
            date_str = start_time.strftime("%A, %d %b %Y")
            if date_str not in bookings_by_date:
                bookings_by_date[date_str] = []
            bookings_by_date[date_str].append((start_time, booking_id, details))
        
        # Create buttons for each date group
        for date_str, bookings in bookings_by_date.items():
            # Add time slots for this date (hidden initially)
            for start_time, booking_id, details in bookings:
                keyboard.append([InlineKeyboardButton(
                    f" 📅 {start_time.strftime('%A, %d %b %Y at %I:%M %p')}",
                    callback_data=f"show_detail_{booking_id}"
                )])

                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Cancel",
                        callback_data=f"cancel_{booking_id}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton("◀ Back to Options", callback_data="back_to_options"),
            InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
        ])

    msg = await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    HelperUtils.store_message_id(context, msg.message_id)
    
    return VIEW_UPCOMING_BOOKINGS

@HelperUtils.check_conversation_active
async def show_upcoming_booking_detail(update: Update, context: CallbackContext) -> int:
    """Show details of a specific upcoming booking."""
    query = update.callback_query

    booking_id = query.data.replace("show_detail_", "")
    
    # Find the booking in upcoming bookings
    user_id = query.from_user.id
    upcoming_bookings = Booking.get_upcoming_bookings(user_id, db)
    
    # Find the specific booking
    booking_details = None
    for booking in upcoming_bookings:
        if booking[0] == booking_id:  # booking_id is first element in tuple
            booking_details = booking
            break

    if booking_details:
        _, start_time, details = booking_details
        popup_message = (
            f"🔵 {start_time.strftime('%A, %d %b %Y at %I:%M %p')}\n"
            f"{details}"
        )
        await query.answer(popup_message, show_alert=True)
    else:
        await query.answer("Booking details not found!", show_alert=True)

    return VIEW_UPCOMING_BOOKINGS

@HelperUtils.check_conversation_active
async def view_past_bookings(update: Update, context: CallbackContext) -> int:
    """Show past bookings with their status."""
    query = update.callback_query
    await query.answer()

    HelperUtils.clear_user_data(context, "selected_date")  # Clear any previously selected date

    user_id = query.from_user.id
    six_months_ago = datetime.now() - timedelta(days=180)
    
    # Get completed and no-show bookings
    completed_bookings = Booking.get_completed_bookings(user_id, db)
    no_show_bookings = Booking.get_no_show_bookings(user_id, db)
    
    # Combine and sort by date (newest first)
    past_bookings = []
    for booking_id, start_time, details, _, _ in completed_bookings:
        if start_time >= six_months_ago:
            past_bookings.append((start_time, booking_id, details, "✅ Completed"))
    
    for booking_id, start_time, details in no_show_bookings:
        if start_time >= six_months_ago:
            past_bookings.append((start_time, booking_id, details, "❌ No Show"))
    
    # Sort by date (newest first)
    past_bookings.sort(reverse=True)

    if not past_bookings:
        message = "📭 You don't have any past bookings."
        keyboard = [
            [InlineKeyboardButton("◀ Back to Options", callback_data="back_to_options")],
            [InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")]
        ]
    else:
        message = "📖 <b>Your Past Bookings:</b>\n\n"
        keyboard = []
        
        # Group bookings by date
        bookings_by_date = {}
        for start_time, booking_id, details, status in past_bookings:
            date_str = start_time.strftime("%d %b %Y, %A")
            if date_str not in bookings_by_date:
                bookings_by_date[date_str] = []
            bookings_by_date[date_str].append((start_time, booking_id, details, status))
        
        # Create buttons for each date group
        for date_str, bookings in bookings_by_date.items():
            keyboard.append([InlineKeyboardButton(
                f"📅 {date_str}",
                callback_data=f"show_date_{date_str}"  # Using date object for callback
            )])
        
        keyboard.append([
            InlineKeyboardButton("◀ Back to Options", callback_data="back_to_options"),
            InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
        ])

    msg = await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    HelperUtils.store_message_id(context, msg.message_id)
    
    return VIEW_PAST_BOOKINGS

@HelperUtils.check_conversation_active
async def show_date_bookings(update: Update, context: CallbackContext) -> int:
    """Show all bookings for a specific date."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("show_date_"):
        date_str = query.data.replace("show_date_", "")
        selected_date = datetime.strptime(date_str, "%A, %d %b %Y").date()

        HelperUtils.set_user_data(context, "selected_date", selected_date)  # Store the selected date
        print(f"Selected date: {selected_date}")
    else:
        selected_date = HelperUtils.get_user_data(context, "selected_date")
    
    user_id = query.from_user.id
    
    # Get all past bookings again
    completed_bookings = Booking.get_completed_bookings(user_id, db)
    no_show_bookings = Booking.get_no_show_bookings(user_id, db)
    
    # Combine and filter for selected date
    date_bookings = []
    for booking_id, start_time, details, _, _ in completed_bookings:
        print(start_time.date())
        if start_time.date() == selected_date:
            date_bookings.append((start_time, booking_id, details, "✅ Completed"))
    
    for booking_id, start_time, details in no_show_bookings:
        if start_time.date() == selected_date:
            date_bookings.append((start_time, booking_id, details, "❌ No Show"))
    
    # Sort by time
    date_bookings.sort()

    if not date_bookings:
        await query.answer("No bookings found for this date!", show_alert=True)
        return VIEW_PAST_BOOKINGS

    message = f"📅 <b>Bookings for {selected_date.strftime('%A, %d %b %Y')}:</b>\n\n"
    keyboard = []
    
    for start_time, booking_id, details, status in date_bookings:
        keyboard.append([InlineKeyboardButton(
            f"{status} - {start_time.strftime('%I:%M %p')}",
            callback_data=f"show_detail_{booking_id}"
        )])
    
    keyboard.append([
        InlineKeyboardButton("◀ Back to Dates", callback_data="back_to_past_bookings"),
        InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
    ])

    await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return VIEW_PAST_BOOKINGS

@HelperUtils.check_conversation_active
async def show_past_booking_detail(update: Update, context: CallbackContext) -> int:
    """Show details of a specific past booking."""
    query = update.callback_query

    booking_id = query.data.replace("show_detail_", "")
    print(f"Booking ID: {booking_id}")
    
    # Find the booking in either completed or no-show bookings
    user_id = query.from_user.id
    completed_bookings = Booking.get_completed_bookings(user_id, db)
    no_show_bookings = Booking.get_no_show_bookings(user_id, db)
    
    # Find the specific booking
    booking_details = None
    status = None
    
    # Check completed bookings first
    for booking in completed_bookings:
        if booking[0] == booking_id:
            booking_details = booking
            status = "✅ Completed"
            break
    
    # If not found in completed, check no-show bookings
    if booking_details is None:
        for booking in no_show_bookings:
            if booking[0] == booking_id:
                booking_details = booking
                status = "❌ No Show"
                break

    if booking_details:
        if status == "✅ Completed":
            _, start_time, details, rating, review = booking_details
            formatted_rating = f"{rating}/5" if rating != "No rating yet" else "No rating yet"
            message_text = (
                f"<b>Booking Details</b>\n\n"
                f"<b>Status:</b> {status}\n"
                f"<b>Date:</b> {start_time.strftime('%A, %d %b %Y at %I:%M %p')}\n"
                f"<b>⭐ Rating:</b> {formatted_rating}\n"
                f"<b>✏️ Review:</b> {review}\n"
                f"{details}\n\n"
            )
        else:
            _, start_time, details = booking_details
            message_text = (
                f"<b>Booking Details</b>\n\n"
                f"<b>Status:</b> {status}\n"
                f"<b>Date:</b> {start_time.strftime('%A, %d %b %Y at %I:%M %p')}\n"
                f"{details}\n\n"
            )

        # Create inline keyboard with rate/review buttons
        keyboard = []
        if status == "✅ Completed" and (rating == "No rating yet" or review == "No review yet"):
            message_text += "How was your experience?"
            keyboard.append([
                InlineKeyboardButton("⭐ Rate Service", callback_data=f"rate_{booking_id}"),
                InlineKeyboardButton("✏️ Leave Review", callback_data=f"review_{booking_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Back to Bookings", callback_data="back_to_show_date_bookings")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            # Fallback if message can't be edited
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        await query.edit_message_text("Booking details not found!")
    
    return VIEW_PAST_BOOKINGS

# ==================== RATE SERVICE FLOW ====================
@HelperUtils.check_conversation_active
async def rate_service(update: Update, context: CallbackContext) -> int:
    """Prompt the user to rate the service."""
    query = update.callback_query
    booking_id = query.data.replace("rate_", "")
    context.user_data['booking_id'] = booking_id  # Store booking_id in user_data

    keyboard = [
        [InlineKeyboardButton("⭐", callback_data="rate_1")],
        [InlineKeyboardButton("⭐⭐", callback_data="rate_2")],
        [InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3")],
        [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4")],
        [InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Please rate the service:\n\n",
        reply_markup=reply_markup
    )
    return RATE_SERVICE

async def save_rating(update: Update, context: CallbackContext) -> int:
    """Save the user's rating for the service."""
    query = update.callback_query
    await query.answer()

    # Get the rating from the callback data
    rating = int(query.data.replace("rate_", ""))
    
    # Retrieve the booking_id from user_data
    booking_id = context.user_data.get('booking_id')
    
    if not booking_id:
        await query.edit_message_text("Error: Booking ID not found.")
        return ConversationHandler.END
    
    # Get reviewer name
    reviewer_name = update.effective_user.full_name if update.effective_user else "Unknown User"

    # Save the rating using Booking class method
    success, message = Booking.save_rating(booking_id, rating, reviewer_name, db)

    # Show thank you with back button
    keyboard = [[
        InlineKeyboardButton("🔙 Back", callback_data=f"show_detail_{booking_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

    # context.user_data.pop('booking_id', None)  # Clear the booking_id from user_data
    HelperUtils.store_message_id(context, msg.message_id)
    
    return VIEW_PAST_BOOKINGS

# ==================== LEAVE REVIEW FLOW ====================
@HelperUtils.check_conversation_active
async def leave_review(update: Update, context: CallbackContext) -> int:
    """Prompt the user to enter a text review."""
    query = update.callback_query
    booking_id = query.data.replace("review_", "")
    context.user_data['booking_id'] = booking_id

    await query.edit_message_text("Please type your review below:")
    return LEAVE_REVIEW

async def save_review(update: Update, context: CallbackContext) -> int:
    """Save the user's review text."""
    review_text = update.message.text
    booking_id = context.user_data.get('booking_id')

    # Get reviewer name
    reviewer_name = update.effective_user.full_name if update.effective_user else "Unknown User"
    
    # Save the review using Booking class method
    success, message = Booking.save_review(booking_id, review_text, reviewer_name, db)

    # Show thank you with back button
    keyboard = [[
        InlineKeyboardButton("🔙 Back", callback_data=f"show_detail_{booking_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        text=message,
        reply_markup=reply_markup
    )
    
    context.user_data.pop('booking_id', None)  # Clear the booking_id from user_data
    HelperUtils.store_message_id(context, msg.message_id)

    return VIEW_PAST_BOOKINGS

# ==================== VIEW CALENDAR FLOW ====================
@HelperUtils.check_conversation_active
async def view_calendar_bookings(update: Update, context: CallbackContext) -> int:
    query = update.callback_query

    await query.answer()

    # Get the user ID from the callback query
    user_id = update.callback_query.from_user.id

    # Get booking info from the Booking class
    booked_slots = Booking.get_upcoming_bookings(user_id, db)

    # Get completed bookings
    completed_bookings = Booking.get_completed_bookings(user_id, db)

    # Get no-show bookings
    no_show_bookings = Booking.get_no_show_bookings(user_id, db)

    # Organize slots by date
    slots_by_date = {}
    for slot_id, start_time, _ in booked_slots:
        date_key = start_time.date()
        if date_key not in slots_by_date:
            slots_by_date[date_key] = {'booked': [], 'completed': [], 'available': [], 'no_show': []}
        slots_by_date[date_key]['booked'].append((slot_id, start_time))
    
    # Add completed bookings to the slots_by_date dictionary
    for slot_id, start_time, _, _, _ in completed_bookings:
        date_key = start_time.date()
        if date_key not in slots_by_date:
            slots_by_date[date_key] = {'booked': [], 'completed': [], 'available': [], 'no_show': []}
        slots_by_date[date_key]['completed'].append((slot_id, start_time))
    
    # Add no-show bookings to the slots_by_date dictionary
    for slot_id, start_time, _ in no_show_bookings:
        date_key = start_time.date()
        if date_key not in slots_by_date:
            slots_by_date[date_key] = {'booked': [], 'completed': [], 'available': [], 'no_show': []}
        slots_by_date[date_key]['no_show'].append((slot_id, start_time))
    
    # Get current month and year (or from callback data)
    today = datetime.now().date()
    if query.data and query.data.startswith("calendar_"):
        _, action, year, month = query.data.split("_")
        year, month = int(year), int(month)
        if action == "prev":
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        elif action == "next":
            month += 1
            if month > 12:
                month = 1
                year += 1
    else:
        year, month = today.year, today.month

    # Generate calendar for the selected month/year
    calendar_keyboard = Keyboards.generate_calendar(year, month, slots_by_date)

    keyboard = calendar_keyboard

    keyboard.append([
        InlineKeyboardButton("◀ Back", callback_data="back_to_options"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use the Messages class to generate the header message
    message = "📅 Select a date to view bookings:\n (🔵 = Bookings, ✅ = Completed, ❌ = No show)"

    msg = await query.edit_message_text(message, reply_markup=reply_markup)
    HelperUtils.store_message_id(context, msg.message_id)

    return VIEW_CALENDAR

@HelperUtils.check_conversation_active
async def view_my_booked_slots(update: Update, context: CallbackContext) -> int:
    """View current user's booked slots."""
    query = update.callback_query

    user_id = query.from_user.id
    booked_slots = Booking.get_upcoming_bookings(user_id, db)
    completed_bookings = Booking.get_completed_bookings(user_id, db)
    no_show_bookings = Booking.get_no_show_bookings(user_id, db)

    # Handle date selection (format: "day_YYYY_MM_DD")
    if query.data.startswith("date_"):
        _, year, month, day = query.data.split("_")
        selected_date = datetime(int(year), int(month), int(day)).date()
        
        # Filter bookings for selected date
        date_bookings = []
        for booking_id, start_time, details in booked_slots:
            if start_time.date() == selected_date:
                date_bookings.append((booking_id, start_time, details, 'booked', None, None))
        
        # Filter completed bookings for selected date
        for booking_id, start_time, details, rating, review in completed_bookings:
            if start_time.date() == selected_date:
                # Find the matching booked slot and change its status to 'completed'
                for idx, (b_id, b_time, b_details, status) in enumerate(date_bookings):
                    if b_id == booking_id:
                        date_bookings[idx] = (b_id, b_time, b_details, 'completed', rating, review)
                        break
                else:
                    # If the booking is not found, add it as completed
                    date_bookings.append((booking_id, start_time, details, 'completed', rating, review))
        
        # Filter no-show bookings for selected date
        for booking_id, start_time, details in no_show_bookings:
            if start_time.date() == selected_date:
                # Find the matching booked slot and change its status to 'no_show'
                for idx, (b_id, b_time, b_details, status, _, _) in enumerate(date_bookings):
                    if b_id == booking_id:
                        date_bookings[idx] = (b_id, b_time, b_details, 'no_show', None, None)
                        break
                else:
                    # If the booking is not found, add it as no-show
                    date_bookings.append((booking_id, start_time, details, 'no_show', None, None))

        if not date_bookings:
            await query.answer(
                f"No bookings found for {selected_date.strftime('%d %b %Y')}",
                show_alert=True
            )
            return VIEW_CALENDAR
        
        # Prepare bookings list for selected date
        bookings_text = f"📖 <b>Your Booking(s) for {selected_date.strftime('%A, %d %b %Y')}:</b>\n\n"
        keyboard = []

        for booking_id, start_time, details, status, rating, review in date_bookings:
                if status == 'completed':
                    bookings_text += f"✅ {start_time.strftime('%I:%M %p')} (Completed)\n"
                    if rating == "No rating yet":
                        bookings_text += "⭐ Rating: No rating yet\n"
                    else:
                        bookings_text += f"⭐ Rating: {rating}/5\n"
                    bookings_text += f"✏️ Review: {review}\n"
                    bookings_text += f"{details}\n\n"
                elif status == 'no_show':
                    bookings_text += f"❌ {start_time.strftime('%I:%M %p')} (No Show)\n"
                    bookings_text += f"{details}\n\n"
                elif status == 'booked':
                    bookings_text += f"⏰ {start_time.strftime('%I:%M %p')}\n"
                    bookings_text += f"{details}\n\n"
                
                if status == 'booked':
                    keyboard.append([
                        InlineKeyboardButton(
                            f"❌ Cancel ({start_time.strftime('%A, %d %b, %I:%M %p')})", 
                            callback_data=f"cancel_{booking_id}"
                        ),
                    ])
        
        # Add navigation buttons
        keyboard.append([
            InlineKeyboardButton("◀ Back to Calendar", callback_data="back_to_calendar"),
            InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
        ])

        msg = await query.edit_message_text(
            text=bookings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        HelperUtils.store_message_id(context, msg.message_id)
        
        return VIEW_CALENDAR
    
    return VIEW_CALENDAR

# ==================== CANCEL BOOKING FLOW ====================
@HelperUtils.check_conversation_active
async def confirm_cancel_prompt(update: Update, context: CallbackContext) -> int:
    """Prompt the user to confirm the cancellation of a booking."""
    query = update.callback_query
    await query.answer()

    # Get the booking_id from the callback data (after 'cancel_')
    booking_id = query.data.replace("cancel_", "")
    HelperUtils.set_user_data(context, "booking_id", booking_id)  # Store the booking_id in user_data

    # Ask the user to confirm the cancellation
    keyboard = [
        [InlineKeyboardButton("✅ Yes, cancel", callback_data="confirm_cancel")],
        [InlineKeyboardButton("❌ No, go back", callback_data="cancel_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Are you sure you want to cancel this booking?",
        reply_markup=reply_markup,
    )

    return CONFIRM_CANCEL

@HelperUtils.check_conversation_active
async def confirm_cancel(update: Update, context: CallbackContext) -> int:
    """Handle cancellation of a booking."""
    query = update.callback_query
    await query.answer()

    # Retrieve the booking_id from user_data
    booking_id = HelperUtils.get_user_data(context, "booking_id")
    user_id = query.from_user.id
    chat_id = query.message.chat_id  # Ensure correct chat ID

    success, message = Booking.cancel_booking(booking_id, user_id, db)

    if success:
        msg = await query.edit_message_text(message)
    else:
        msg = await query.edit_message_text(f"Error: {message}")
    
    HelperUtils.reset_conversation_state(context)
    HelperUtils.store_message_id(context, msg.message_id)
    return ConversationHandler.END

# ==================== BACK HANDLERS ====================
@HelperUtils.check_conversation_active
async def back_to_options(update: Update, context: CallbackContext) -> int:
    """Return to the calendar view from bookings list."""
    return await start_bookings(update, context)

async def back_to_calendar(update: Update, context: CallbackContext) -> int:
    """Return to the calendar view from bookings list."""
    query = update.callback_query
    await query.answer()
    return await view_calendar_bookings(update, context)

async def cancel_back(update: Update, context: CallbackContext) -> int:
    """Handle the user choosing not to cancel the booking."""
    query = update.callback_query
    await query.answer()

    # Call the view_my_booked_slots function to display the bookings again
    return await view_upcoming_bookings(update, context)

async def back_to_past_bookings(update: Update, context: CallbackContext) -> int:
    """Return to the main past bookings view."""
    return await view_past_bookings(update, context)

async def back_to_show_date_bookings(update: Update, context: CallbackContext) -> int:
    """Return to the date bookings view."""
    return await show_date_bookings(update, context)

# ==================== CONVERSATION HANDLER DEFINITION ====================
view_bookings_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_bookings, pattern="^view_booked_slots$")],
    states={
        VIEW_BOOKINGS_OPTIONS: [
            CallbackQueryHandler(view_upcoming_bookings, pattern="^view_upcoming$"),
            CallbackQueryHandler(view_past_bookings, pattern="^view_past$"),
            CallbackQueryHandler(view_calendar_bookings, pattern="^view_calendar$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        VIEW_UPCOMING_BOOKINGS: [
            CallbackQueryHandler(show_upcoming_booking_detail, pattern="^show_detail_"),
            CallbackQueryHandler(confirm_cancel_prompt, pattern="^cancel_"),
            CallbackQueryHandler(back_to_options, pattern="^back_to_options$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        VIEW_PAST_BOOKINGS: [
            CallbackQueryHandler(show_date_bookings, pattern="^show_date_"),
            CallbackQueryHandler(show_past_booking_detail, pattern="^show_detail_"),
            CallbackQueryHandler(back_to_options, pattern="^back_to_options$"),
            CallbackQueryHandler(back_to_past_bookings, pattern="^back_to_past_bookings$"),
            CallbackQueryHandler(back_to_show_date_bookings, pattern="^back_to_show_date_bookings$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
            CallbackQueryHandler(rate_service, pattern="^rate_"),
            CallbackQueryHandler(leave_review, pattern="^review_"),
        ],
        RATE_SERVICE: [
            CallbackQueryHandler(save_rating, pattern="^rate_\\d$"),
        ],
        LEAVE_REVIEW: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_review),
        ],
        VIEW_CALENDAR: [
            CallbackQueryHandler(view_my_booked_slots, pattern="^date_\\d+_\\d+_\\d+$"),
            CallbackQueryHandler(view_calendar_bookings, pattern="^calendar_(prev|next)_\\d+_\\d+$"),
            CallbackQueryHandler(confirm_cancel_prompt, pattern="^cancel_"),
            CallbackQueryHandler(back_to_options, pattern="^back_to_options$"),
            CallbackQueryHandler(back_to_calendar, pattern="^back_to_calendar$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        CONFIRM_CANCEL: [
            CallbackQueryHandler(confirm_cancel, pattern="^confirm_cancel$"),
            CallbackQueryHandler(cancel_back, pattern="^cancel_back$"),
        ],
    },
    fallbacks=[
        CommandHandler("client_menu", client_menu),
        CommandHandler("cancel", client_cancel),
    ],
    allow_reentry=True
)