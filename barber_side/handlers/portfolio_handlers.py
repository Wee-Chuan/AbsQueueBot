from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from barber_side.handlers.menu_handlers import menu
from barber_side.utils.globals import *

# States
CHOOSE_LINK_TYPE, RECEIVE_LINK = range(2)

async def start_portfolio(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("📸 Instagram", callback_data="ig_link"),
            InlineKeyboardButton("🎵 TikTok", callback_data="tiktok_link")
        ],
        [
            InlineKeyboardButton("Back to Menu", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("Which link would you like to save?", reply_markup=reply_markup)
    return CHOOSE_LINK_TYPE

async def choose_link_type(update: Update, context: CallbackContext) -> int:
    """Save the chosen link type and ask user to send the link."""
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    link_type = query.data
    context.user_data["link_type"] = link_type

    await query.edit_message_text(
        text=f"Please enter your { 'Instagram' if link_type == 'ig_link' else 'TikTok' } link:",
        reply_markup = InlineKeyboardMarkup(keyboard)
    )
    return RECEIVE_LINK


async def receive_link(update: Update, context: CallbackContext) -> int:
    """Receive the actual link and save it in Firestore."""
    portfolio_link = update.message.text
    context.user_data["portfolio_link"] = portfolio_link

    # Retrieve barber info
    current_barber = context.user_data['current_user']
    uuid = current_barber.uuid
    link_type = context.user_data["link_type"]

    try:
        # Query Firestore for the barber with the given uuid
        barber_query = db.collection("barbers").where("uuid", "==", uuid).limit(1).stream()
        barber_doc = None
        for doc in barber_query:
            barber_doc = doc
            break

        if barber_doc is None:
            await update.message.reply_text("❗ Barber not found in the database.")
            return ConversationHandler.END

        # Update Firestore with the chosen link
        db.collection("barbers").document(barber_doc.id).update({
            link_type: portfolio_link
        })

        await update.message.reply_text("✅ Link saved successfully.")
        await menu(update, context)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed to save link: {e}")

    return ConversationHandler.END

async def back_to_home(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    await menu(update, context)
    return ConversationHandler.END

portfolio_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_portfolio, pattern = r"^link_socials$")],
    states={
        CHOOSE_LINK_TYPE: [CallbackQueryHandler(choose_link_type)],
        RECEIVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
    },
    fallbacks=[CallbackQueryHandler(back_to_home, pattern=r"^cancel$"),],
)