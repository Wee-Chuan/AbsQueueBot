import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.globals import *
from utils.messages import Messages
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from shared.utils import HelperUtils
from io import BytesIO

# /start
# Starting up the bot
async def start(update: Update, context: CallbackContext) -> None:
    """Handler for /start command"""
    # Send welcome image
    await _send_welcome_image(update)

    welcome_message = (
        "Welcome to <b>AbsQueue</b>! The easiest way to book your barber slot!\n\n"
        "Type /menu to see available options.\n"
        "Type /help if you need assistance.\n\n"
    )

    await update.message.reply_text(welcome_message, parse_mode="HTML")
    return ConversationHandler.END

async def client_menu(update: Update, context: CallbackContext) -> None:
    """Handler for /menu command - shows the main options"""
    # Reset copnversation state and clear previous messages
    await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

    # Reset the conversation state
    HelperUtils.reset_conversation_state(context)

    # Set the conversation_active flag to True
    HelperUtils.set_user_data(context, "conversation_active", True)

    menu_text = "Please choose an option:"
    menu_buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Schedule Appointment", callback_data="book_slots")],
        [InlineKeyboardButton("📖 My Bookings", callback_data="view_booked_slots")],
        # [InlineKeyboardButton("💈 Open Booking App", web_app={"url": "https://d31b-2406-3003-2002-ba-6c24-94a6-77ae-572d.ngrok-free.app/booking.html"})],
        [InlineKeyboardButton("📷 Our Instagram", url="https://www.instagram.com/absqueue/")],
    ])
    
    if update.message:
        msg = await update.message.reply_text(menu_text, reply_markup=menu_buttons)
    elif update.callback_query:
        msg = await update.callback_query.message.reply_text(menu_text, reply_markup=menu_buttons)
    
    HelperUtils.store_message_id(context, msg.message_id)

    return ConversationHandler.END

async def _send_welcome_image(update: Update) -> None:
    """Helper function to send welcome image"""
    try:
        bucket = storage.bucket()
        blob = bucket.blob("image.jpg")
        
        if blob.exists():
            image_data = blob.download_as_bytes()
            await update.message.reply_photo(photo=BytesIO(image_data))
    except Exception as e:
        print(f"Error loading welcome image: {e}")

# Function to handle cancellation of the conversation
@HelperUtils.check_conversation_active
async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    chat_id = update.effective_chat.id

    await HelperUtils.clear_previous_messages(context, chat_id)
    
    message = Messages.cancel_operation_message()
    msg = await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())

    HelperUtils.reset_conversation_state(context)
    return ConversationHandler.END
    
