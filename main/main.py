import sys
import os
import asyncio

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Telegram imports
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, ConversationHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Import client-side modules
from client_side.utils.core_commands import *
# from client_side.utils.clientListener import NotificationListener 
from client_side.handlers.booking_handlers import book_slots_handler
from client_side.handlers.view_bookings_handlers import view_bookings_handler
from shared.utils import HelperUtils

# Import barber-side modules


# Define states
SELECTING_ROLE, BARBER_MODE, CLIENT_MODE = range(3)

### Loading Environmental Variables ###
load_dotenv()

class BarberBot:
    def __init__(self, token):
        self.token = token
        self.user_roles = {}  # Dictionary to store user roles
        # self.notification_listener = None  # Placeholder for notification listener

    async def start(self, update: Update, context: CallbackContext):
        """Initial start command - ask user to select a role."""
        user_id = update.effective_user.id

        # Clear previous messages
        await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

        # Create role selection keyboard
        keyboard = [
            [KeyboardButton("👨‍🔧 Barber")],
            [KeyboardButton("👤 Client")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        await update.message.reply_text(
            "Welcome to AbsQueue!💈 Please select your role:",
            reply_markup=reply_markup
        )

        return SELECTING_ROLE
    
    async def handle_role_selection(self, update: Update, context: CallbackContext):
        """Handle role selection by the user."""
        user_id = update.effective_user.id
        selected_role = update.message.text

        if "Barber" in selected_role:
            self.user_roles[user_id] = "barber"
            await self.enter_barber_mode(update, context)
            return BARBER_MODE
        
        elif "Client" in selected_role:
            self.user_roles[user_id] = "client"
            await self.enter_client_mode(update, context)
            return CLIENT_MODE
        
        else:
            await update.message.reply_text("Invalid selection. Please select a valid role.")
            return SELECTING_ROLE

    # ======= Barber Mode Logic ======= #    
    async def enter_barber_mode(self, update: Update, context: CallbackContext):
        """Enter barber mode"""
        await update.message.reply_text(
            "🔄 Switching to Barber Mode...\n\n"
            "You now have access to all barber features, please login to continue."
            "Use /switch_role to change to client mode.",
            reply_markup=ReplyKeyboardRemove()
        )

        try:
            # Call barber's logic here
            pass  # Placeholder for barber mode logic
        except Exception as e:
            await update.message.reply_text(f"An error occurred in Barber Mode: {str(e)}")
            return SELECTING_ROLE
    
    # ======= Client Mode Logic ======= #
    async def enter_client_mode(self, update: Update, context: CallbackContext):
        """Enter client mode"""
        loading_msg = await update.message.reply_text(
            "🔄 Switching to Client Mode...\n\n"
            "You now have access to all client features. \n",
            reply_markup=ReplyKeyboardRemove()
        )

        # wait for 2 seconds 
        await asyncio.sleep(1)

        # Delete the loading message
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=loading_msg.message_id)
        except Exception as e:
            print(f"Error deleting loading message: {e}")

        try:
            await client_menu(update, context)  # Call menu to show the main menu
        except Exception as e:
            await update.message.reply_text(f"An error occurred in Client Mode: {str(e)}")
            return SELECTING_ROLE
    
    async def handle_barber_messages(self, update: Update, context: CallbackContext):
        """Handle messages when in barber mode"""
        user_id = update.effective_user.id
        
        # Check if it's a role switch command
        if update.message.text == "/switch_role":
            return await self.switch_role(update, context)
        
        try:
            pass
        except Exception as e:
            print(f"Error in barber message handler: {e}")
            await update.message.reply_text("⚠️ Unsure? Click on /barber_menu to see the available options!")
        
    async def handle_client_messages(self, update: Update, context: CallbackContext):
        """Handle messages when in client mode"""
        user_id = update.effective_user.id
        
        # Check if it's a role switch command
        if update.message.text == "/switch_role":
            return await self.switch_role(update, context)
        
        # Use the existing client-side message handler
        try:
            msg = await update.effective_message.reply_text("⚠️ Unsure? Click on /client_menu to see the available options! Or select /start to restart the bot.")
            HelperUtils.store_message_id(context, msg.message_id)
        except Exception as e:
            print(f"Error in client message handler: {e}")
            await update.message.reply_text("⚠️ Unsure? Click on /client_menu to see the available options! Or select /start to restart the bot.")
        
        return CLIENT_MODE
    
    async def switch_role(self, update: Update, context: CallbackContext):
        """Allow user to switch roles between barber and client."""
        user_id = update.effective_user.id

        if user_id not in self.user_roles:
            msg = await update.message.reply_text(
                "❗ You need to select a role first. Use /start to begin.",
            )
            HelperUtils.store_message_id(context, msg.message_id)
            return SELECTING_ROLE
        
        keyboard = [
            [KeyboardButton("👨‍🔧 Switch to Barber")],
            [KeyboardButton("👤 Switch to Client")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "🔄 Switch Role\n\n"
            "Please select your new role:",
            reply_markup=reply_markup
        )
        
        return SELECTING_ROLE
    
    async def unified_cancel(self, update: Update, context: CallbackContext):
        """Cancel the current operation and reset the conversation."""
        user_id = update.effective_user.id
        user_role = self.user_roles.get(user_id, None)

        if user_role == "client":
            # Use client-side cancel function
            try:
                await client_cancel(update, context)
            except Exception as e:
                print(f"Error calling client cancel: {e}")
                await update.message.reply_text("❌ Operation cancelled.")
            
            return CLIENT_MODE
        
        elif user_role == "barber":
            # For barber mode use the barber's cancel logic
            pass
        
        else:
            # Default fallback
            self.user_roles.pop(user_id, None)  # Remove user role if exists
            await update.message.reply_text(
                "❌ Operation cancelled. Use /start to begin again.",
                reply_markup=ReplyKeyboardRemove()
            )
            return SELECTING_ROLE
    
    async def handle_unknown_messages(self, update: Update, context: CallbackContext):
        """Handle unknown messages."""
        msg = await update.effective_message.reply_text("⚠️ Unsure? Click on /start to select your role!")
        HelperUtils.store_message_id(context, msg.message_id)
    
    def create_application(self):
        """Create and configure bot application."""
        app = Application.builder().token(self.token).build()

        # Create conversation handler for role selection
        role_selection_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                SELECTING_ROLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_role_selection)
                ],
                BARBER_MODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_barber_messages)
                ],
                CLIENT_MODE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_client_messages)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.unified_cancel), 
                CommandHandler("switch_role", self.switch_role)
            ],
            allow_reentry=True
        )

        # Add role selection handler first
        app.add_handler(role_selection_handler)

        # Always handle /switch_role, even outside conversation
        app.add_handler(CommandHandler("switch_role", self.switch_role))

        # Always handle /cancel, even outside conversation
        app.add_handler(CommandHandler("cancel", self.unified_cancel))

        # Add unified command handlers

        # Add client side handlers
        app.add_handler(CommandHandler("client_menu", client_menu))
        app.add_handler(book_slots_handler)
        app.add_handler(view_bookings_handler)

        # Add barber side handlers
        pass  # Add barber mode handlers here if needed

        # Handle unknown messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_messages))
    
        return app
    
def main():
    """Main function to run the bot."""
    token = os.getenv("TOKEN")
    barber_bot = BarberBot(token)
    
    app = barber_bot.create_application()
    
    try:
        # Start the bot
        print("🤖 Bot is running...")
        app.run_polling()
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
    finally:
        print("✅ Bot shut down cleanly")
    
if __name__ == "__main__":
    main()
