# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
)

# Third-party imports
from datetime import datetime, timedelta

# Local imports
from barber_side.handlers.menu_handlers import menu
from barber_side.utils.globals import *

# Conversation state constant
TYPE_SELECTION = 0

# --- Helpers for cleaning up messages ---
async def _delete_messages(update: Update, context: CallbackContext, key: str):
    try:
        msgs = context.user_data.pop(key, [])
        if msgs:
            chat_id = (
                update.callback_query.message.chat_id
                if update.callback_query
                else update.message.chat_id
            )
            await context.bot.delete_messages(chat_id=chat_id, message_ids=msgs)
    except Exception as e:
        print(f"Error deleting {key}: {e}")

async def clear_conversation(update: Update, context: CallbackContext):
    await _delete_messages(update, context, 'messages_to_delete')
    await _delete_messages(update, context, 'chat_flow')

async def cleanup_chat_flow(update: Update, context: CallbackContext):
    await _delete_messages(update, context, 'chat_flow')

# --- Main earnings menu ---
async def earnings(update: Update, context: CallbackContext) -> int:
    """
    Entry point for /earnings command: show options for today's or total earnings.
    """
    # Ensure user is logged in
    if not context.user_data.get('logged_in'):
        await update.message.reply_text("Please log in first!")
        return ConversationHandler.END

    # Initialize or clear message-deletion tracking
    context.user_data.setdefault('messages_to_delete', [])
    messages_to_delete = context.user_data['messages_to_delete']

    # Build menu buttons
    keyboard = [
        [InlineKeyboardButton("📅 Today's Earnings", callback_data="today_earnings")],
        [InlineKeyboardButton("📊 Total Earnings", callback_data="total_earnings")],
        [InlineKeyboardButton("🗓️ This Week's Earnings", callback_data="week")],
        [InlineKeyboardButton("🗓️ This Month's Earnings", callback_data="month")],
        [InlineKeyboardButton("🔙 Back to menu", callback_data="back_to_main")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # Send menu prompt
    if update.message:
        menu_msg = await update.message.edit_text("Please choose an option:", reply_markup=markup)
    else:
        menu_msg = await update.callback_query.message.edit_text("Please choose an option:", reply_markup=markup)

    # Track menu message for cleanup
    messages_to_delete.append(menu_msg.message_id)
    return TYPE_SELECTION

# --- Today's earnings handler ---
async def today(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # Clear previous
    await cleanup_chat_flow(update, context)

    now = datetime.now(timezone)
    # Define day boundaries in local tz
    start_of_day = timezone.localize(datetime(now.year, now.month, now.day, 0, 0, 0))
    end_of_day = timezone.localize(datetime(now.year, now.month, now.day, 23, 59, 59))

    email = context.user_data.get('current_user').email

    earnings_stream = (
        db.collection('booked slots')
          .where('barber_email', '==', email)
          .where('completed', '==', True)
          .where('`start time`', '>=', start_of_day)
          .where('`start time`', '<=', end_of_day)
          .stream()
    )

    total_earnings = 0.0
    for doc in earnings_stream:
        data = doc.to_dict()
        price = data.get('service_price', 0)
        try:
            total_earnings += float(price)
        except (ValueError, TypeError):
            continue

    result_msg = await query.message.reply_text(f"Earnings for today: ${total_earnings:.2f}")
    context.user_data.setdefault('chat_flow', []).append(result_msg.message_id)
    return TYPE_SELECTION

# --- Total earnings handler ---
async def total(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    #clear previous result
    await cleanup_chat_flow(update, context)
    
    email = context.user_data.get('current_user').email
    earnings_stream = (
        db.collection('booked slots')
          .where('barber_email', '==', email)
          .where('completed', '==', True)
          .stream()
    )

    total_earnings = 0.0
    for doc in earnings_stream:
        data = doc.to_dict()
        price = data.get('service_price', 0)
        try:
            total_earnings += float(price)
        except (ValueError, TypeError):
            continue

    result_msg = await query.message.reply_text(f"Total earnings: ${total_earnings:.2f}")
    context.user_data.setdefault('chat_flow', []).append(result_msg.message_id)
    return TYPE_SELECTION

# --- Period earnings handler (week and month) ---
async def period_earnings(update: Update, context: CallbackContext) -> int:
    """
    Handles earnings for this week (since last Sunday) or this month (since first of month).
    Expects callback_data 'week' or 'month'.
    """
    query = update.callback_query
    await query.answer()

    # Clean up prior result messages
    await cleanup_chat_flow(update, context)

    now = datetime.now(timezone)
    period = query.data  # 'week' or 'month'

    if period == 'week':
        # Calculate last Sunday (or today if Sunday)
        weekday = now.weekday()  # Mon=0...Sun=6
        days_since_sunday = (weekday + 1) % 7
        start_day = now - timedelta(days=days_since_sunday)
        start_of_period = timezone.localize(datetime(
            start_day.year, start_day.month, start_day.day, 0, 0, 0
        ))
        label = start_of_period.strftime('%A, %d %B %Y')
        title = f"Earnings since Sunday ({label}):"
    else:
        # This month: from the first day of current month
        start_of_period = timezone.localize(datetime(
            now.year, now.month, 1, 0, 0, 0
        ))
        label = start_of_period.strftime('%B %Y')
        title = f"Earnings in {label}:"

    # Query completed bookings in the period
    earnings_stream = (
        db.collection('booked slots')
          .where('barber_email', '==', context.user_data['current_user'].email)
          .where('completed', '==', True)
          .where('`start time`', '>=', start_of_period)
          .where('`start time`', '<=', now)
          .stream()
    )

    total_earnings = 0.0
    for doc in earnings_stream:
        data = doc.to_dict()
        price = data.get('service_price', 0)
        try:
            total_earnings += float(price)
        except (ValueError, TypeError):
            continue

    # Send result
    result_msg = await query.message.reply_text(f"{title} ${total_earnings:.2f}")
    context.user_data.setdefault('chat_flow', []).append(result_msg.message_id)
    return TYPE_SELECTION



# --- Cancel handler ---
async def cancel(update: Update, context: CallbackContext) -> int:
    # Send cancel notification
    if update.message:
        await update.message.reply_text("Operation cancelled!")
    else:
        await update.callback_query.message.reply_text("Operation cancelled!")

    # Clean up previous messages
    await clear_conversation(update, context)
    return ConversationHandler.END

# --- Handle reissued /earnings command ---
async def handle_earnings_command(update: Update, context: CallbackContext) -> int:
    """
    Fallback for incoming /earnings during the conversation:
    end current flow, then redispatch /earnings globally.
    """
    # Delete any pending conversational messages
    await clear_conversation(update, context)

    # Schedule redispatch of the same update so global handler can pick it up
    if update.message:
        context.application.create_task(context.application.process_update(update))

    return ConversationHandler.END

async def back_to_main(update:Update, context:CallbackContext):
    await menu(update, context)
    return ConversationHandler.END


# --- Conversation Handler registration ---
earnings_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(earnings, pattern=r"earnings")],
    states={
        TYPE_SELECTION: [
            CommandHandler("earnings", handle_earnings_command),
            CallbackQueryHandler(cancel, pattern=r"^cancel$"),
            CallbackQueryHandler(today, pattern=r"^today_earnings$"),
            CallbackQueryHandler(total, pattern=r"^total_earnings$"),
            CallbackQueryHandler(period_earnings, pattern=r"^(?:week|month)$"),
        ]
    },
    fallbacks=[
        CallbackQueryHandler(back_to_main, pattern=r"^back_to_main$"),
        CommandHandler("menu", back_to_main)
        ],
    per_user=True,
    allow_reentry=True
)
