# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

# Local imports
from barber_side.handlers.menu_handlers import menu
from barber_side.utils.globals import *
from barber_side.classes.classes import *
from datetime import datetime

# State Definitions
DESCRIPTION_MENU, DESCRIPTION_NAVIGATION, ADD_DESCRIPTION, DELETE_CONFIRMATION = range(4)

# cleanup convo
async def cleanup_user_messages(update: Update, context: CallbackContext):
    try:
        # Get the last message that needs to be deleted
        last_message = context.user_data.get('last_message')

        if last_message:
            chat_id = (
                update.callback_query.message.chat_id
                if update.callback_query else update.message.chat_id
            )

            # Delete the last message
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message.message_id)
            context.user_data.pop('last_message', None)  # Clear out the last message after deletion

    except Exception as e:
        print(f"Error deleting message: {e}")
    
# --- Helpers for cleaning up messages ---
async def _delete_messages(update: Update, context: CallbackContext, key: str):
    try:
        msgs = context.user_data.pop(key, [])
        if msgs:
            chat_id = (
                update.callback_query.message.chat_id
                if update.callback_query
                else update.message.chat_id
            )
            await context.bot.delete_messages(chat_id=chat_id, message_ids=msgs)
    except Exception as e:
        print(f"Error deleting {key}: {e}")

async def clear_conversation(update: Update, context: CallbackContext):
    await _delete_messages(update, context, 'messages_to_delete')
    await _delete_messages(update, context, 'chat_flow')

### ENTRY point
async def descriptions_menu(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("➕ Add Description", callback_data="add_description")],
        [InlineKeyboardButton("📄 View Descriptions", callback_data="view_descriptions")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
    ]

    if update.callback_query:  # coming from "Back to Menu" or any button
        message = await update.callback_query.message.edit_text(
            "What would you like to do?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["last_message"] = message
        
    else:
        message = await update.message.reply_text(
            "What would you like to do?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["last_message"] = message
        
    context.user_data.setdefault('menu_message', []).append(message.message_id)
    
    return DESCRIPTION_MENU

# handles choice (add or view or cancel)
async def handle_description_menu_choice(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "add_description":
        return await add_description(update, context)
    elif query.data == "view_descriptions":
        return await view_my_descriptions(update, context)
    elif query.data == "cancel":
        context.user_data.pop('waiting_for_description', None)
        # await cleanup_user_messages(update, context)  # Only delete the last message
        return ConversationHandler.END
    elif query.data == "back_to_menu":
        return await descriptions_menu(update, context)

async def back_to_desc_menu(update:Update, context:CallbackContext) -> int:
    await descriptions_menu(update, context)

async def view_my_descriptions(update: Update, context: CallbackContext) -> int:
    descriptions = await Description.get_all_descriptions(update, context)

    if not descriptions:
        try:
            back_button = InlineKeyboardButton("⬅ Back to Menu", callback_data="back_to_menu")
            reply_markup = InlineKeyboardMarkup([[back_button]])
            await context.user_data["last_message"].edit_text("No descriptions found.", reply_markup = reply_markup)
        except Exception as e:
            print(f"Error editing to show 'No descriptions found': {e}")

    context.user_data.update({
        "descriptions": list(d.description for d in descriptions),# store Description objects directly
        "desc_ids": list([d.doc_id for d in descriptions]),     # extract doc_ids
        "desc_index": 0
    })

    await send_description(update, context)
    return DESCRIPTION_NAVIGATION

# pagination & activation
async def navigate_descriptions(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "prev_desc":
        context.user_data["desc_index"] = max(0, context.user_data["desc_index"] - 1)
    elif query.data == "next_desc":
        context.user_data["desc_index"] = min(len(context.user_data.get("descriptions", [])) - 1, context.user_data["desc_index"] + 1)
    elif query.data == "activate":
        await Description.activate_description(update, context)
        await descriptions_menu(update, context)
        return DESCRIPTION_MENU
    elif query.data == "delete":
        await ask_delete_confirmation(update, context)
        return DELETE_CONFIRMATION 
    elif query.data == "edit":
        pass
    elif query.data == "cancel":
        # await cleanup_user_messages(update, context)
        return ConversationHandler.END
    elif query.data == "back_to_menu":
        return await descriptions_menu(update, context)

    await send_description(update, context)
    return DESCRIPTION_NAVIGATION

async def send_or_edit_message(update: Update, context: CallbackContext,
                               description_text: str, reply_markup: InlineKeyboardMarkup) -> None:
    query = update.callback_query
    await query.answer()
    try:
        # try to update the existing bot message
        last_message = await query.message.edit_text(
            description_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        context.user_data.setdefault('chat_flow', []).append(last_message.message_id)
    except BadRequest:
        # if it can't be edited (e.g. was deleted), send a fresh one
        last_message = await query.message.reply_text(
            description_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        context.user_data.setdefault('chat_flow', []).append(last_message.message_id)

async def send_description(update: Update, context: CallbackContext) -> None:
    descriptions = context.user_data.get("descriptions", [])
    index = context.user_data.get("desc_index", 0)

    if not descriptions:
        await update.message.reply_text("No descriptions available.")
        return

    description_text = f"Description {index + 1}/{len(descriptions)}:\n\n{descriptions[index]}"
    context.user_data["curr_desc_id_displayed_on_bot"] = context.user_data.get("desc_ids", [])[index]

    keyboard = []
    if index > 0:
        keyboard.append(InlineKeyboardButton("⬅ Previous", callback_data="prev_desc"))
    if index < len(descriptions) - 1:
        keyboard.append(InlineKeyboardButton("Next ➡", callback_data="next_desc"))

    result_list = await get_account_document(update, context) # barbers details
    data = result_list[0].to_dict()
    curr_desc = data.get('description_id') # currently active desc_id

    new_description_id = context.user_data.get("curr_desc_id_displayed_on_bot")
    new_description_ref = db.collection('descriptions').document(new_description_id)
    

    status_button = InlineKeyboardButton(
        "Already Active ✅" if curr_desc == new_description_ref else "Make Active ✅",
        callback_data="noop" if curr_desc == new_description_ref else "activate"
    )

    keyboard2 = [status_button]
    keyboard3 = [InlineKeyboardButton("❌ Delete", callback_data="delete"), InlineKeyboardButton("📝 Edit", callback_data="delete")]
    back_button = InlineKeyboardButton("⬅ Back to Menu", callback_data="back_to_menu")

    reply_markup = InlineKeyboardMarkup([keyboard, keyboard2, keyboard3, [back_button]])

    await send_or_edit_message(update, context, description_text, reply_markup)

### adding descs
async def add_description(update: Update, context: CallbackContext) -> int:
    context.user_data['waiting_for_description'] = True

    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        [InlineKeyboardButton("⬅ Back to Menu", callback_data="back_to_menu")]
    ]

    description_text = "Please send me the description you'd like to add:"
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await send_or_edit_message(update, context, description_text, reply_markup)
    return ADD_DESCRIPTION

# save to db
async def handle_description(update: Update, context: CallbackContext) -> int:
    description = update.message.text
    result_list = await get_account_document(update, context)
    data = result_list[0].to_dict()

    db.collection("descriptions").add({
        "email": data.get('email'),
        "barber": data.get('name'),
        "description": description,
        "when_added" : datetime.utcnow()
    })
    
    # delete the “please send me…” prompt
    await _delete_messages(update, context, 'chat_flow')
    await update.message.reply_text(f"Description saved: {description}")
    context.user_data['waiting_for_description'] = False
    # Go back to the menu and edit the original menu message
    await descriptions_menu(update, context)
    return DESCRIPTION_MENU

async def back_to_main(update:Update, context:CallbackContext):
    await menu(update, context)
    return ConversationHandler.END

# delete confirmation
async def ask_delete_confirmation(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="confirm_delete"),
            InlineKeyboardButton("No", callback_data="cancel_delete")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(
        "Are you sure you want to delete this description?",
        reply_markup=reply_markup
    )

async def delete_handler(update:Update, context:CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_delete":
        await Description.delete_description(update, context)
        await _delete_messages(update, context, 'chat_flow')
        await descriptions_menu(update, context)
        return DESCRIPTION_MENU
    else:
        await _delete_messages(update, context, 'chat_flow')
        await descriptions_menu(update, context)
        return DESCRIPTION_MENU
        

description_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(descriptions_menu, pattern = r"^descriptions$")],
    states={
        DESCRIPTION_MENU: [
            CallbackQueryHandler(handle_description_menu_choice, pattern="^(add_description|view_descriptions|cancel)$"),
            
        ],
        DESCRIPTION_NAVIGATION: [
            CallbackQueryHandler(navigate_descriptions, pattern="^(prev_desc|next_desc|activate|cancel|back_to_menu|delete)$"),
            
        ],
        ADD_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
            CallbackQueryHandler(handle_description_menu_choice, pattern="^(cancel|back_to_menu)$"),
        ],
        DELETE_CONFIRMATION: [
            CallbackQueryHandler(delete_handler, pattern=r"^(confirm_delete|cancel_delete)$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(back_to_main, pattern=r"^back_to_main$"),
        CommandHandler("menu", back_to_main),
        CallbackQueryHandler(back_to_desc_menu, pattern=r"^back_to_menu")
        ],
    per_user=True,
    allow_reentry=True
)
