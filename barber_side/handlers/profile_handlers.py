# Standard imports
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

# Local imports
from barber_side.handlers.menu_handlers import clear_menu, menu
from barber_side.handlers.description_handlers import get_account_document, send_or_edit_message
from barber_side.utils.storage_actions import display_barber_image


# Define the states
EDIT_MENU, EDIT_NAME, EDITTING, BACK = range(4)

# Step 1: Profile details function (stage 1)
async def profile_details(update: Update, context: CallbackContext) -> int:
    context.user_data.setdefault('edit_messages', [])
    try:
        result_list = await get_account_document(update, context)

        # Error checking
        if not result_list:  # If no results, send a message
            await update.message.reply_text("Profile does not exist in the 'barbers' collection.")
            return ConversationHandler.END  # End the conversation

        # Else
        data = result_list[0].to_dict()
        email = data.get('email')
        barber_name = data.get('name')
        region = data.get('region')
        postal_code = data.get('postal code')
        address = data.get('address')
        portfolio = data.get('portfolio_link')
        
        caption = f"Barber Name: {barber_name}\nEmail: {email}\nRegion: {region}\nPostal Code: {postal_code}\nAddress: {address}\nPortfolio Link: {portfolio}"
        
        await display_barber_image(update, context,"luqmanarifin49@gmail.png", caption)
        await editting_menu(update, context)
        return EDITTING  

    except Exception as e:  # Catches any exception
        await update.message.reply_text("Log In Required")
        return ConversationHandler.END  # End the conversation

async def editting_menu(update:Update, context:CallbackContext) -> int:
    back_button = InlineKeyboardButton("Back", callback_data="back")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Edit Name", callback_data="edit_name"), 
         InlineKeyboardButton("Edit Email", callback_data="edit_email")],
        [InlineKeyboardButton("Edit Address and Post Code", callback_data="edit_address"),
         InlineKeyboardButton("Edit Photo", callback_data="edit_photo")], [back_button]])

    await update.callback_query.message.reply_text("What would you like to edit?", reply_markup=reply_markup)

# Step 2: Handle the "Back" button press
async def back_button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    await menu(update, context)

    return ConversationHandler.END  # End the conversation or go back to another state

async def edit_name(update:Update, context:CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_editting")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await update.callback_query.message.edit_text("Enter your new name:", reply_markup=reply_markup)
    
    edit_messages = context.user_data.get('edit_messages', [])
    edit_messages.append(message.message_id)
    return EDIT_NAME

async def receive_name(update:Update, context:CallbackContext) -> int :
    
    
    return EDITTING

# fallbacks
async def back_to_main(update:Update, context:CallbackContext):
    await menu(update, context)
    return ConversationHandler.END

async def cancel_editting(update:Update, context:CallbackContext):
    edit_messages = context.user_data.get('edit_messages', [])
    await context.bot.delete_messages(chat_id = update.callback_query.message.chat_id, message_ids=edit_messages)
    context.user_data["edit_messages"] = []
    await editting_menu(update, context)
    return EDITTING


# Step 3: Create the ConversationHandler
profile_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(profile_details, pattern=r"^profile_details$")],  # Triggered by the "Profile Details" button
    states={
        EDITTING: [CallbackQueryHandler(edit_name, pattern=r"^edit_name$")],
        EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
    },
    fallbacks=[
        CallbackQueryHandler(back_button_handler, pattern="back"),
        CallbackQueryHandler(cancel_editting, pattern="cancel_editting")
        ],
    per_chat=True,
    allow_reentry=True
)

