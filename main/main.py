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
# Local imports (group them by functionality for better readability)
from barber_side.utils.globals import *
from barber_side.utils.storage_actions import display_start_image

# Handlers for various functionalities (from barber_side.handlers)
from barber_side.handlers.menu_handlers import menu
from barber_side.handlers.auth_handlers import *
from barber_side.handlers.calendar import calendar_handler
from barber_side.handlers.description_handlers import description_conv_handler
from barber_side.handlers.service_handlers import main_services_conversation, services_menu
from barber_side.handlers.appointment_handlers import appointments_conv_handler
from barber_side.handlers.earnings_handlers import earnings_handler
from barber_side.handlers.profile_handlers import profile_conversation_handler
from barber_side.handlers.portfolio_handlers import portfolio_conv_handler


# Define states
SELECTING_ROLE = range(1)

### Loading Environmental Variables ###
load_dotenv()

class BarberBot:
    def __init__(self, token):
        self.token = token
        self.user_roles = {}  # Dictionary to store user roles
        # self.notification_listener = None  # Placeholder for notification listener

    async def start(self, update: Update, context: CallbackContext): #### /start 
        """Initial start command - ask user to select a role."""
        user_id = update.effective_user.id

        # Clear previous messages
        await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

        # Create role selection keyboard
        keyboard = [
            [KeyboardButton("💈 I'm a Barber")],
            [KeyboardButton("👤 I'm a Client")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        welcome_message = (
            "👋 <b>Welcome to AbsQueue!</b>\n\n"
            "The easiest way to <i>book</i> or <i>offer</i> barber services.\n\n"
            "<b>How it works:</b>\n"
            "✅ <b>For Clients</b> – Find your favorite barber & book instantly.\n"
            "✅ <b>For Barbers</b> – Manage bookings and grow your business.\n\n"
            "💡 <i>Whether you're a barber or a client, we've got you covered.</i>\n\n"
            "<b>Please choose your role to get started:</b>"
        )

        await update.message.reply_text(
            welcome_message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

        return SELECTING_ROLE
    
    async def handle_role_selection(self, update: Update, context: CallbackContext):
        """Handle role selection by the user."""
        user_id = update.effective_user.id
        selected_role = update.message.text
        print("Selected Role: ", selected_role)
        if "Barber" in selected_role:
            self.user_roles[user_id] = "barber"
            await self.enter_barber_mode(update, context)
            return ConversationHandler.END
        
        elif "Client" in selected_role:
            self.user_roles[user_id] = "client"
            await self.enter_client_mode(update, context)
            return ConversationHandler.END
        
        else:
            await update.message.reply_text("Invalid selection. Please select a valid role.")
            return SELECTING_ROLE

    # ======= Barber Mode Logic ======= #    
    async def enter_barber_mode(self, update: Update, context: CallbackContext):
        """Enter barber mode"""
        
        keyboard = [[InlineKeyboardButton("Login", callback_data="login")], [InlineKeyboardButton("Sign Up", callback_data="signup")]]
        msg = await update.message.reply_text(
            "🔄 Switching to Barber Mode...\n\n"
            "You now have access to all barber features, please login to continue.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Store the message ID for later deletion
        HelperUtils.store_message_id(context, msg.message_id)

        # try:
            
        # except Exception as e:
        #     await update.message.reply_text(f"An error occurred in Barber Mode: {str(e)}")
        #     return SELECTING_ROLE
    
    # ======= Client Mode Logic ======= #
    async def enter_client_mode(self, update: Update, context: CallbackContext):
        """Enter client mode"""
        loading_msg = await update.message.reply_text(
            "🔄 Switching to Client Mode...\n\n"
            "You now have access to all client features. \n",
            reply_markup=ReplyKeyboardRemove()
        )

        # wait for 1 seconds 
        await asyncio.sleep(0.6)

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
    
    async def switch_role(self, update: Update, context: CallbackContext):
        """Allow user to switch roles between barber and client."""
        user_id = update.effective_user.id

        if user_id not in self.user_roles:
            msg = await update.message.reply_text(
                "⚠️ You need to select a role first. Use /start to begin.",
            )
            HelperUtils.store_message_id(context, msg.message_id)
            return ConversationHandler.END
        
        # Remove the user's current role
        self.user_roles.pop(user_id, None)
        
        msg = await update.message.reply_text(
            "🔄 Switching Role\n\n"
            "To switch roles, please use /start and select your new role.",
        )

        HelperUtils.store_message_id(context, msg.message_id)
        ConversationHandler.END  # End current conversation
    
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
        
        # elif user_role == "barber":
        #     # For barber mode use the barber's cancel logic
        #     pass
        
        else:
            # Default fallback
            self.user_roles.pop(user_id, None)  # Remove user role if exists
            chat_id = update.effective_chat.id
            await HelperUtils.clear_previous_messages(context, chat_id)
            await update.message.reply_text(
                "❌ Operation cancelled. Use /start to begin again.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END  # End current conversation
    
    async def handle_unknown_messages(self, update: Update, context: CallbackContext):
        """Handle unknown messages."""
        msg = await update.effective_message.reply_text("⚠️ Unsure? Click on /start to select your role!")
        HelperUtils.store_message_id(context, msg.message_id)
    
    def create_application(self):
        """Create and configure bot application."""
        app = Application.builder().token(self.token).build()

        app.add_handler(book_slots_handler)

        # Create conversation handler for role selection    
        role_selection_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start, filters=filters.Regex(r"^/start$"))],
            states={
                SELECTING_ROLE: [
                    MessageHandler(filters.Regex("(Client|Barber)$"),  self.handle_role_selection)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.unified_cancel), 
                CommandHandler("switch_role", self.switch_role)
            ],
            per_user=True,
            allow_reentry=True
        )

        # Add role selection handler first
        app.add_handler(role_selection_handler)

        # Always handle /switch_role, even outside conversation
        app.add_handler(CommandHandler("switch_role", self.switch_role))

        # Add client side handlers
        app.add_handler(CommandHandler("client_menu", client_menu))
        app.add_handler(book_slots_handler)
        app.add_handler(view_bookings_handler)

        # Add barber side handlers
        ### Add conversation handlers ###
        #/login_dev
        app.add_handler(CommandHandler("login_dev", login_dev))
        
        #/login
        app.add_handler(login_conversation_handler)
        
        # signup
        app.add_handler(signup_handler)
        
        #/calendar
        app.add_handler(calendar_handler)
        
        #profile
        app.add_handler(profile_conversation_handler)

        #services
        app.add_handler(main_services_conversation)
        
        #descriptions
        app.add_handler(description_conv_handler)
        
        # appointments
        app.add_handler(appointments_conv_handler)
        # app.add_handler(day_view_handler)
        
        # earnings
        app.add_handler(earnings_handler)
            
        # portfolio
        app.add_handler(portfolio_conv_handler)
        
        # COMMAND HANDLERS
        #/start
        #app.add_handler(CommandHandler("start", start))
        
        #/menu
        app.add_handler(CommandHandler("menu", menu))

        # Handle chatbot
        # Handle unknown messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_messages))
    
        # sign out
        app.add_handler(CallbackQueryHandler(sign_out, pattern='signout')),  # Trigger for button press

        # Always handle /cancel, even outside conversation
        app.add_handler(CommandHandler("cancel", self.unified_cancel))
        
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
