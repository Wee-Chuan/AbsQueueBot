# Standard imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

# Local imports (group them by functionality for better readability)
from barber_side.utils.globals import *

async def clear_menu(update: Update, context: CallbackContext) -> None:
    menu_messages = context.user_data.get('menu_message', [])

    if not menu_messages:
        return  # Nothing to delete

    # Get the correct chat ID from either message or callback
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        print("NO VALID CHAT_ID IN CLEAR_MENU")
        return  # no valid chat_id

    try:
        await context.bot.delete_messages(chat_id=chat_id, message_ids=menu_messages)
        print(f"✅ Deleted menu messages: {menu_messages}")
    except Exception as e:
        print(f"❌ Error deleting messages: {e}")

    # Clear the list so you don't try deleting the same ones again
    context.user_data['menu_message'] = []
    
async def menu(update: Update, context: CallbackContext) -> None:
    print("global menu handler")
    if not await check_login(update, context): await update.message.reply_text("Please log in first.\nClick on /login to login!"); return
        
    await clear_menu(update, context) # clear previous menus
    keyboard = [
        [InlineKeyboardButton("💈 Profile Details", callback_data="profile_details"), 
         InlineKeyboardButton("🔗 Portfolio", callback_data="link_portfolio")],
        [InlineKeyboardButton("🗓️ Calendar", callback_data="calendar"),
         InlineKeyboardButton("📅 Appt History", callback_data="appointments")],
        [InlineKeyboardButton("💇🏻 Your Services", callback_data="services_menu"), 
         InlineKeyboardButton("💬 Your Descriptions", callback_data="descriptions")],
        [InlineKeyboardButton("💲 Earnings", callback_data="earnings"),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        message = await update.message.reply_text("What would you like to do?", reply_markup=reply_markup)
    else:
        message = await update.callback_query.message.reply_text("What would you like to do?", reply_markup=reply_markup)

    context.user_data.setdefault('menu_message', []).append(message.message_id)
    
