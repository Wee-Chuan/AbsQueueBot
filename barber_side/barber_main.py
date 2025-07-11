# Standard imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler

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
### Environment Variables Loaded ###

timezone = pytz.timezone("Asia/Singapore")

### Bot Commands
# /start
# starting up the bot 
async def start(update: Update, context: CallbackContext) -> None:
    await display_start_image(update, context, "image.jpg")

    # Define the buttons
    keyboard = [
        [InlineKeyboardButton("Login", callback_data="login")],
    ]

    # Create the markup for inline buttons
    reply_markup = InlineKeyboardMarkup(keyboard)

    logged_in = context.user_data.get('logged_in') # get logged in value (bool)
    curr_user = context.user_data.get('current_user') # get user name

    if logged_in == True:
        print("User is already logged in")  # Debug statement
        welcome_message = f"✅ You are currently logged in as *{curr_user.name}* 💈"
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN_V2)
    # Send a message with the buttons
    else:
        await update.message.reply_text("Please choose an option:", reply_markup=reply_markup)


async def reply_any_message(update: Update, context: CallbackContext) -> None:
    print("IN GENERAL HANDLER")

    await update.message.reply_text("Unsure? Click on menu to see the available options!")
    
    print("RETURNING NONE FROM GENERAL HANDLER")
    return None

async def hello(update:Update, context: CallbackContext):
    print("global hello")

# ----- Menu ----- #

# Main function to start the bot
# def main():
#     # Initialize the application with the token
#     app = Application.builder().token(TOKEN).build()

#     ### Add conversation handlers ###
#     #/login_dev
#     app.add_handler(CommandHandler("login_dev", login_dev))
    
#     #/login
#     app.add_handler(login_conversation_handler)
    
#     #/calendar
#     app.add_handler(calendar_handler)
    
#     #profile
#     app.add_handler(profile_conversation_handler)

#     #services
#     app.add_handler(main_services_conversation)
    
#     #descriptions
#     app.add_handler(description_conv_handler)
    
#     # appointments
#     app.add_handler(appointments_conv_handler)
#     # app.add_handler(day_view_handler)
    
#     # earnings
#     app.add_handler(earnings_handler)
        
#     # portfolio
#     app.add_handler(portfolio_conv_handler)
    
#     # COMMAND HANDLERS
#     #/start
#     app.add_handler(CommandHandler("start", start))
    
#     #/menu
#     app.add_handler(CommandHandler("menu", menu))
#     # ADD LAST FOR THE CATCH ALL HANDLER
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_any_message))

    
#     # Start polling for updates
#     app.run_polling()

# if __name__ == "__main__":
#     main()
    

