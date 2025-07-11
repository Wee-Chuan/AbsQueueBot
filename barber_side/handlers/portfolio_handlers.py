from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from barber_side.handlers.menu_handlers import menu
from barber_side.utils.globals import *

RECEIVE = range(1)

async def link_portfolio(update: Update, context: CallbackContext) -> None:
    message = await update.callback_query.message.edit_text("Enter a link to your portfolio:")
    return RECEIVE
    
async def receive_link(update: Update, context: CallbackContext) -> None:
    # Extract user input
    portfolio_link = update.message.text
    context.user_data["portfolio_link"] = portfolio_link

    # Retrieve email from context
    
    current_barber = context.user_data['current_user']
    user_email = current_barber.email
    print(user_email)

    try:
        # Query Firestore for the barber with the given email
        barber_query = db.collection("barbers").where("email", "==", user_email).limit(1).stream()

        barber_doc = None
        for doc in barber_query:
            barber_doc = doc
            break  

        if barber_doc is None:
            await update.message.reply_text("❗ Barber not found in the database.")
            return

        # Update the document with the portfolio link
        db.collection("barbers").document(barber_doc.id).update({
            "portfolio_link": portfolio_link
        })

        await update.message.reply_text("✅ Portfolio link saved successfully.")
        await menu(update, context)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed to save portfolio link: {e}")


portfolio_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(link_portfolio, pattern = r"^link_portfolio$")],
    states={
        RECEIVE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND,receive_link),
        ]
    },
    fallbacks=[
        # CallbackQueryHandler(back_to_main, pattern=r"^back_to_main$"),
        # CommandHandler("menu", back_to_main)
        ],
    per_user=True,
    allow_reentry=True
)