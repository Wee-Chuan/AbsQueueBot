from barber_side.handlers.menu_handlers import menu
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler

DISPLAY_LINK = range(1)

async def generate_link(update:Update, context:CallbackContext) -> None :
    query = update.callback_query
    await query.answer()
    
    uuid = context.user_data.get('current_user', None).uuid
    link = f"https://t.me/AbsQueueBot?start=barber_{uuid}"
    
    back_button = [InlineKeyboardButton("🔙", callback_data = "back")]
    
    message = await update.callback_query.message.edit_text(f"✨ Want your clients to book instantly?\n Share this link with them:\n{link}", 
                                                            reply_markup = InlineKeyboardMarkup([back_button]) )
    return DISPLAY_LINK
    

# --- Cancel handler ---
async def back(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    await menu(update, context)
    return ConversationHandler.END


# --- Conversation handlers registration ---
link_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(generate_link, pattern = r"^deep_link$")],
    states={
        DISPLAY_LINK: [
            CallbackQueryHandler(back, pattern = r"^back$")
        ],
    },
    fallbacks=[],
    per_user=True,
    per_chat=True,
    allow_reentry=True
)