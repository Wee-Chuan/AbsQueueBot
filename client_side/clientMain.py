import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

from client_side.utils.globals import *
from client_side.utils.core_commands import *
from client_side.utils.clientListener import NotificationListener

# Import handlers
from client_side.handlers.booking_handlers import book_slots_handler
from client_side.handlers.view_bookings_handlers import view_bookings_handler

# Add help function
async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a help message to the user."""

    help_message = (
        "ℹ️ <b>Help - How to Use AbsQueue Bot</b>\n\n"
        "Here are the available commands and features:\n\n"
        "📅 <b>Schedule Appointment</b>: \n"
        "Start by selecting this option to book an appointment. You'll be able to:\n"
        "  • Search barbers by Region\n"
        "  • Find barbers near your Current Location\n"
        "  • Search for a Barber by Name\n"
        "  • View barbers on a Map\n\n"
        "📖 <b>My Bookings</b>: View your current bookings and manage them.\n\n"
        "You can use the following commands:\n"
        "/menu - Return to the main menu.\n"
        "/help - Show this help message.\n"
        "/cancel - Cancel the current operation.\n\n"
        "⚠️ <b>Having trouble?</b>\n"
        "If you encounter any issues, such as clicking an option but it not working, "
        "use the <b>/cancel</b> command to ensure all operations are canceled and start fresh."
    )

    if update.message:
        await update.message.reply_text(help_message, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.edit_message_text(help_message, parse_mode="HTML")
    
# Function to handle unknown messages
async def reply_any_message(update: Update, context: CallbackContext):
    """ Handles unknown text messages """
    msg = await update.effective_message.reply_text("⚠️ Unsure? Click on /menu to see the available options!")
    HelperUtils.store_message_id(context, msg.message_id)

# def main():
#     app = Application.builder().token(TOKEN).build()

#     # Initialize notification listener
#     notification_listener = NotificationListener(
#         bot_token=TOKEN,
#         db=db,
#         check_interval=20  # Check every 10 seconds
#     )

#     try:
#         # Add command handlers
#         app.add_handler(CommandHandler("start", start))
#         app.add_handler(CommandHandler("menu", menu))
#         app.add_handler(CommandHandler("help", help_command))

#         # Add the conversation handlers
#         app.add_handler(book_slots_handler)
#         app.add_handler(view_bookings_handler)

#         # Handle cancel operation
#         app.add_handler(CommandHandler("cancel", cancel))

#         # Handle unknown messages
#         app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_any_message))

#         # Start listener in a separate thread
#         import threading
#         listener_thread = threading.Thread(
#             target=notification_listener.start,
#             daemon=True
#         )
#         listener_thread.start()
        
#         print("🤖 Bot is running...")
#         app.run_polling()

#     except KeyboardInterrupt:
#         print("\n🛑 Stopping bot...")
#     finally:
#         notification_listener.stop()
#         print("✅ Bot shut down cleanly")

# if __name__ == "__main__":
#     main()