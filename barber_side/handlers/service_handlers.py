# Telegram imports
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
)
# Firebase imports
from firebase_admin import auth

# Local imports
from barber_side.utils.globals import *
from barber_side.classes.classes import Barber, Service
from barber_side.handlers.menu_handlers import menu as m

# --- Helper functions ---
async def cleanup_messages(update: Update, context: CallbackContext):
    """Delete all stored messages and clear the list."""
    print("clearing messages")
    chat_id = update.effective_chat.id
    msg_ids = context.user_data.get('messages_to_delete', [])
    if msg_ids:
        await context.bot.delete_messages(chat_id=chat_id, message_ids=msg_ids)
        context.user_data['messages_to_delete'] = []

async def cleanup_service_menu(update: Update, context: CallbackContext):
    print("clearing service menu")
    chat_id = update.effective_chat.id
    msg_id = context.user_data.get('service_menu_id')

    if msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            print(f"Deleted service menu message {msg_id}")
        except Exception as e:
            print(f"Failed to delete service menu message {msg_id}: {e}")

        # Properly remove the key
        context.user_data.pop('service_menu_id', None)
# --- Handler functions ---

#### VIEWING 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, ConversationHandler

SERVICES_PER_PAGE = 1
SERVICES_VIEWING, NAME, PRICE, DESCRIPTION, EDIT_SELECT_FIELD, EDIT_NAME, EDIT_PRICE, EDIT_DESCRIPTION = range(8)

async def services_menu(update: Update, context: CallbackContext) -> int:    
    service_menu_id = context.user_data.get('service_menu_id')  # fixed key name
    if service_menu_id:
        print(f"Found stored message ID: {service_menu_id}")
        await cleanup_service_menu(update, context)
    else:
        print("Service menu message not found in user_data.")

    keyboard = [
        [InlineKeyboardButton("📋 View Services", callback_data="view_services"),
         InlineKeyboardButton("➕ Create Service", callback_data="create_service")],
        [InlineKeyboardButton("🔙 Back to menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
    try:
        message = await update.callback_query.message.edit_text(
            "💈 *Services Menu*", 
            reply_markup=reply_markup,
            parse_mode='Markdown' 
        )
    except Exception as e:
        print(e)
        message = await update.callback_query.message.reply_text(
            "💈 *Services Menu*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    if message:
        context.user_data['service_menu_id'] = message.message_id  # make sure you're saving the ID!
    return SERVICES_VIEWING

## ----------------- view services -----------------
async def view_services(update: Update, context: CallbackContext, flag = True) -> int:
    
    messages = context.user_data.pop('messages_to_delete', None)
    if messages:
        try:
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=messages)
        except Exception as e:
            await context.bot.delete_messages(chat_id=update.callback_query.message.chat_id, message_ids=messages)
    barber_email = context.user_data.get('current_user').email
    collection_ref = db.collection('services')
    query = collection_ref.where("email", "==", barber_email)

    docs = query.stream()
    services = [doc.to_dict() for doc in docs]

    if not services:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("💈 You have no services set up yet.")
        return ConversationHandler.END

    context.user_data['services_list'] = services
    context.user_data['services_page'] = 0

    await send_services_page(update, context, flag)

    return SERVICES_VIEWING

async def send_services_page(update: Update, context: CallbackContext, flag = True):
    services = context.user_data['services_list']
    page = context.user_data['services_page']

    start = page * SERVICES_PER_PAGE
    end = start + SERVICES_PER_PAGE
    sliced_services = services[start:end]

    if not sliced_services:
        text = "💈 No services to display on this page."
        reply_markup = None
    else:
        # Build the text block
        text_lines = []
        keyboard = []

        for service in sliced_services:
            name = service.get("name", "Unnamed Service")
            price = service.get("price", "No price")
            description = service.get("description", "No description")
            service_id = service.get("service_id", "")

            # store in context_user for use
            context.user_data["curr_service_name"] = name
            context.user_data["curr_service_price"] = price
            context.user_data["curr_service_description"] = description  
            
            text_lines.append(
                f"💈 <b>{name}</b>\n💲Price: {price}\n📝 {description}\n"
            )

            # Per-service button row
            keyboard.append([
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{service_id}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{service_id}")
            ])            

        # Add navigation buttons if needed
        nav_buttons = []
        if start > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="services_prev"))
        if end < len(services):
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="services_next"))

        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data = "back_to_services_menu"),
                             InlineKeyboardButton("🏠 Home", callback_data= "back_to_main")])
        text = "\n".join(text_lines).strip()
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        if flag == True:
            try:
                message = await update.callback_query.message.edit_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as e:
                message = await update.callback_query.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    else:
        try:
            message = await update.message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            message = await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    context.user_data.setdefault('messages_to_delete',[]).append(message.message_id)

async def handle_service_pagination(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "services_next":
        context.user_data['services_page'] += 1
    elif query.data == "services_prev":
        context.user_data['services_page'] -= 1

    await send_services_page(update, context)

    return SERVICES_VIEWING

### ----------------- edit service -----------------
# entry
async def handle_edit_service(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    data = query.data  # e.g., "edit_barber123-s5"
    if data.startswith("edit_"):
        service_id = data[len("edit_"):]  # Extract service_id
        context.user_data["editing_service_id"] = service_id  # Store for later use
    print(f"user is editting {service_id}")
    
    name = context.user_data.get("curr_service_name")
    price = context.user_data.get("curr_service_price")
    description = context.user_data.get("curr_service_description")
    
    service_info = f"Name: {name}\nPrice: ${price}\nDescription: {description}"
    text = f"{service_info}\nWhich would you like to edit?"
    keyboard = []
    keyboard.append([InlineKeyboardButton("Name", callback_data=f"name_{service_id}"), 
                     InlineKeyboardButton("Price", callback_data=f"price_{service_id}"), 
                     InlineKeyboardButton("Description", callback_data=f"description_{service_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data = "back_to_edit_menu")])
    keyboard = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(text, reply_markup = keyboard)
    
    return EDIT_SELECT_FIELD    

# 1) User clicked “Name”, “Price” or “Description”
async def handle_edit_field_selection(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # data is e.g. "name_barber123-s5"
    field, service_id = query.data.split("_", 1)
    context.user_data["editing_service_id"] = service_id
    context.user_data["editing_field"] = field
    
    curr_name = context.user_data.get("curr_service_name")
    price = context.user_data.get("curr_service_price")
    description = context.user_data.get("curr_service_description")
    
    prompts = {
        "name": f"Current Service Name:{curr_name}\nPlease send me the *new name* for the service:",
        "price":f"Current Service Price:{price}\nPlease send me the *new price* (a number):",
        "description": f"Current Service Description:{description}\nPlease send me the *new description*:",
    }
    
    keyboard = []
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data = "back_to_edit_menu"),
                             InlineKeyboardButton("🏠 Home", callback_data= "back_to_main")])
    keyboard = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        prompts[field],
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    # Jump into the right next state
    if field == "name":
        return EDIT_NAME
    elif field == "price":
        return EDIT_PRICE
    else:
        return EDIT_DESCRIPTION


# 2a) Receive new name
async def receive_new_name(update: Update, context: CallbackContext) -> int:
    new_name = update.message.text.strip()
    context.user_data["new_service_name"] = new_name
    return await apply_service_update(update, context)


# 2b) Receive new price
async def receive_new_price(update: Update, context: CallbackContext) -> int:
    text = update.message.text.strip()
    try:
        new_price = float(text)
    except ValueError:
        await update.message.reply_text("⚠️ That doesn’t look like a number. Please send a valid price.")
        return EDIT_PRICE

    context.user_data["new_service_price"] = new_price
    return await apply_service_update(update, context)

# 2c) Receive new description
async def receive_new_description(update: Update, context: CallbackContext) -> int:
    new_desc = update.message.text.strip()
    context.user_data["new_service_description"] = new_desc
    return await apply_service_update(update, context)

# 3) Write back to Firestore and confirm
async def apply_service_update(update: Update, context: CallbackContext) -> int:
    svc_id = context.user_data["editing_service_id"]
    field = context.user_data["editing_field"]

    # Get the Firestore document to rebuild the object
    doc_ref = db.collection("services").document(svc_id)
    doc = doc_ref.get()

    if not doc.exists:
        await update.message.reply_text("❌ Service not found in database.")
        return ConversationHandler.END

    service_data = doc.to_dict()
    service = Service(
        service_id=svc_id,
        barber_name=service_data["barber_id"],
        name=service_data["name"],
        price=service_data["price"],
        description=service_data["description"],
        barber_email=service_data["email"]
    )

    # Prepare kwargs for your edit_service method
    kwargs = {}
    if field == "name":
        kwargs["name"] = context.user_data["new_service_name"]
    elif field == "price":
        kwargs["price"] = context.user_data["new_service_price"]
    else:
        kwargs["description"] = context.user_data["new_service_description"]

    # Update and push to Firestore using your method
    service.edit_service(db, **kwargs)

    message = await update.message.reply_text(
        f"✅ Service *{svc_id}* updated successfully ({field}).",
        parse_mode="Markdown"
    )

    # Cleanup
    for k in ("editing_service_id", "editing_field",
              "new_service_name", "new_service_price", "new_service_description"):
        context.user_data.pop(k, None)

    await view_services(update, context)
    return SERVICES_VIEWING



## ----------------- delete service -----------------
async def confirm_delete_service(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "delete_abc123"
    service_id = data.replace("delete_", "")

    context.user_data['pending_delete_service_id'] = service_id

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Delete", callback_data="confirm_delete"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "⚠️ Are you sure you want to delete this service?",
        reply_markup=reply_markup
    )

    return SERVICES_VIEWING

async def handle_confirm_delete(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    service_id = context.user_data.get('pending_delete_service_id')
    if not service_id:
        await query.edit_message_text("❌ No service selected for deletion.")
        return SERVICES_VIEWING

    barber_email = context.user_data.get('current_user').email
    service_doc = db.collection('services').document(service_id)
    service_data = service_doc.get()

    if service_data.exists and service_data.to_dict().get('email') == barber_email:
        service_doc.delete()
        await query.edit_message_text("🗑️ Service has been deleted!\n\nReturning to services list...")
    else:
        await query.edit_message_text("⚠️ Service not found or you don't have permission to delete it.")

    messages_to_delete = context.user_data.pop('messages_to_delete', None)
    if messages_to_delete:
        await context.bot.delete_messages(chat_id=update.callback_query.message.chat_id, message_ids=messages_to_delete)

    # Clear the stored service ID
    context.user_data.pop('pending_delete_service_id', None)

    return await view_services(update, context, False)  # Show updated list

async def handle_cancel_delete(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data.pop('pending_delete_service_id', None)

    await query.edit_message_text("❌ Deletion cancelled.")
    messages_to_delete = context.user_data.pop('messages_to_delete', None)
    if messages_to_delete:
        await context.bot.delete_messages(chat_id=update.callback_query.message.chat_id, message_ids=messages_to_delete)
        
    return await view_services(update, context, False)  # Show updated list

## ----------------- create service -----------------
async def start_create_service(update: Update, context: CallbackContext) -> int:
    query = update.callback_query; await query.answer()
    keyboard = []
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data = "back_to_services_menu"),
                             InlineKeyboardButton("🏠 Home", callback_data= "back_to_main")])
    keyboard = InlineKeyboardMarkup(keyboard)
    if context.user_data.get('logged_in'):
        prompt = await update.callback_query.message.reply_text("Please enter the name of the service.", reply_markup = keyboard)
        context.user_data.setdefault('messages_to_delete', []).append(prompt.message_id)
        return NAME
    else:
        notice = await update.callback_query.message.reply_text("Please log in first!")
        return ConversationHandler.END

async def get_service_name(update: Update, context: CallbackContext) -> int:
    keyboard = []
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data = "back_to_services_menu"),
                             InlineKeyboardButton("🏠 Home", callback_data= "back_to_main")])
    keyboard = InlineKeyboardMarkup(keyboard)

    context.user_data["service_name"] = update.message.text
    prompt = await update.message.reply_text("Please enter the price of the service.", reply_markup=keyboard)
    context.user_data.setdefault("messages_to_delete", []).append(prompt.message_id)
    return PRICE

async def get_service_price(update: Update, context: CallbackContext) -> int:
    keyboard = []
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data = "back_to_services_menu"),
                             InlineKeyboardButton("🏠 Home", callback_data= "back_to_main")])
    keyboard = InlineKeyboardMarkup(keyboard)

    context.user_data["service_price"] = update.message.text
    prompt = await update.message.reply_text("Please enter a description of the service.", reply_markup=keyboard)
    context.user_data.setdefault("messages_to_delete", []).append(prompt.message_id)
    return DESCRIPTION

async def get_service_description(update: Update, context: CallbackContext) -> int:
    context.user_data["service_description"] = update.message.text
    name = context.user_data["service_name"]
    price_input = context.user_data["service_price"]

    try:
        price = float(price_input)
    except ValueError:
        err = await update.message.reply_text("❌ Price must be a number!")
        context.user_data.setdefault("messages_to_delete", []).append(err.message_id)
        return await start_create_service(update, context)

    desc = context.user_data["service_description"]
    barber = context.user_data.get('current_user')
    service_id = Service.generate_service_id(barber.name, db)
    service = Service(service_id, barber.name, name, price, desc, barber.email)
    service.push_to_db(db)

    await update.message.reply_text(f"✅ Service '{name}' created successfully!")
    await services_menu(update, context)

## ----------------- other fallbacks -----------------
async def cancel(update: Update, context: CallbackContext) -> int:
    print("cancelling")
    await cleanup_messages(update, context)
    return ConversationHandler.END

async def silent_cancel(update: Update, context: CallbackContext) -> int:
    await cleanup_messages(update, context)
    return ConversationHandler.END

async def resend_command(update: Update, context: CallbackContext) -> int:
    await cleanup_messages(update, context)
    if update.message:
        context.application.create_task(context.application.process_update(update))
    return ConversationHandler.END

async def back_to_main(update:Update, context:CallbackContext):
    print("back tomain HAHAHAHHAHAHAHHAHAAHHA")
    await cleanup_service_menu(update, context)
    await cleanup_messages(update, context)
    await m(update, context)
    return ConversationHandler.END

async def back_to_services(update:Update, context:CallbackContext):
    await cleanup_messages(update, context)
    await services_menu(update, context)
    return SERVICES_VIEWING

async def back_to_view(update:Update, context:CallbackContext):
    print("back to view")
    await view_services(update, context)
    return SERVICES_VIEWING
    
async def back_to_edit_service(update: Update, context: CallbackContext):
    pass 

# --- Conversation handler setup ---
main_services_conversation = ConversationHandler(
    entry_points=[
        CommandHandler('services', services_menu),
        CallbackQueryHandler(services_menu, pattern="^services_menu$"),
    ],
    states={
        SERVICES_VIEWING: [
            CallbackQueryHandler(view_services, pattern="^view_services$"),
            CallbackQueryHandler(handle_service_pagination, pattern="^(services_next|services_prev)$"),
            CallbackQueryHandler(start_create_service, pattern="create_service"),
            CallbackQueryHandler(handle_edit_service, pattern=r'^edit_'),
            CallbackQueryHandler(confirm_delete_service, pattern=r'^delete_'),
            CallbackQueryHandler(handle_confirm_delete, pattern=r'^confirm_delete$'),
            CallbackQueryHandler(handle_cancel_delete, pattern=r'^cancel_delete$'),
        ],

        # Create service flow
        NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_name)
        ],
        PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_price)
        ],
        DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_description)
        ],

        # Edit service flow
        EDIT_SELECT_FIELD: [
            CallbackQueryHandler(handle_edit_field_selection, pattern=r"^(name|price|description)_")
        ],
        EDIT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_name)
        ],
        EDIT_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_price)
        ],
        EDIT_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_description)
        ]
    },
    fallbacks=[
        CommandHandler("menu",back_to_main),
        CallbackQueryHandler(back_to_main, pattern=r"^back_to_main$"),
        CallbackQueryHandler(back_to_services, pattern=r"^back_to_services_menu$"),
        CallbackQueryHandler(back_to_view, pattern=r"^back_to_edit_menu$"),
        CallbackQueryHandler(cancel, pattern=r"^cancel$"),  # Add cancel from create flow
    ],
    per_user=True,
    allow_reentry=True
)
