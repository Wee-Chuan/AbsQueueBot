# Telegram imports
from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Third-party imports
import requests
import re

# Local imports
from barber_side.handlers.menu_handlers import clear_menu, menu
from barber_side.utils.globals import *
from barber_side.classes.classes import *
from firebase_admin import auth

# quick login for devs (luqqycutz account)
async def login_dev(update: Update, context: CallbackContext) -> None:
    email = "luqmanarifin49@gmail.com"
    password = "Starwars91!"
    
    login_result = login_user(email, password)

    if login_result["success"]:
        user_id = login_result["user_id"]
        user_sessions[update.message.from_user.id] = user_id

        # Query Firestore for barber data
        collection_ref = db.collection('barbers')
        query = collection_ref.where("email", "==", email)
        result = query.stream()
        result_list = list(result)
        
        user = auth.get_user_by_email(email)
        uid = user.uid
        
        # Save barber object to context.user_data
        barber_doc = result_list[0].to_dict()
        current_barber = Barber(
            address=barber_doc.get('address'),
            email=barber_doc.get('email'),
            name=barber_doc.get('name'),
            desc_id=barber_doc.get('description_id'),
            postal=barber_doc.get('postal code'),
            region=barber_doc.get('region'),
            portfolio = barber_doc.get('portfolio_link'),
            doc_id=result_list[0].id,
            uuid=uid
        )
        context.user_data['current_user'] = current_barber
        context.user_data['logged_in'] = True
        print("\n✅ Barber object saved to context.user_data\n")

        welcome_message = f"✅ Welcome back, *{current_barber.name}* 👋"
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN_V2)
        await menu(update, context)
    else:
        await update.message.reply_text(f"❌ Login failed! {login_result['error']}")

# helper for Firebase Authentication
def login_user(email, password):
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(FIREBASE_AUTH_URL, json=payload)
    data = response.json()

    if "idToken" in data:
        return {"success": True, "user_id": data["localId"], "token": data["idToken"]}
    else:
        return {"success": False, "error": data.get("error", {}).get("message", "Login failed")}

# States for ConversationHandler
EMAIL, PASSWORD = range(2)

# entry point into conversation (asks for email)
async def start_login(update: Update, context: CallbackContext) -> int:
    print("starting login conversation")  # Debug statement
    
    # Remove the previous message with the inline buttons
    query = update.callback_query
    if query:
        await query.message.delete()
    
    # checks if user is already logged in
    logged_in = context.user_data.get('logged_in')
    curr_user = context.user_data.get('current_user')

    if logged_in:
        print("User is already logged in")  # Debug statement
        welcome_message = f"✅ You are currently logged in as *{curr_user.name}* 💈"
        if update.message:
            await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN_V2)
        elif update.callback_query:
            await update.callback_query.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END  # Exit if already logged in
    
    # not logged in
    else:
        print("User is not logged in. Requesting email...")  # Debug statement
        
        # Prompt the user to enter their email
        if update.message: # /login command
            email_prompt = await update.message.reply_text("Please enter your email.")
            context.user_data.setdefault('messages_to_delete', []).append(email_prompt.message_id)

        elif update.callback_query: # Login button
            email_prompt = await update.callback_query.message.reply_text("Please enter your email.")
            context.user_data.setdefault('messages_to_delete', []).append(email_prompt.message_id)

        print("returning EMAIL...")
        return EMAIL  # This returns the EMAIL state to wait for user input

# Get the password after email
async def get_password(update: Update, context: CallbackContext) -> int:
    print(f"Received email: {update.message.text}")  # Debug line to ensure we captured the email
    context.user_data["login_email"] = update.message.text  # Temporarily store email

    # Ask for the password
    password_prompt = await update.message.reply_text("Please enter your password.")
    
    # add message_id to list to delete
    messages_to_delete = context.user_data.get('messages_to_delete', [])
    messages_to_delete.append(password_prompt.message_id)
    messages_to_delete.append(update.message.message_id)

    return PASSWORD

# Final step: Attempt to log in
async def get_login_details(update: Update, context: CallbackContext) -> int:
    # Retrieve saved user data
    email = context.user_data.get("login_email")
    password = update.message.text  # Get password from the latest message
    print(password)
    messages_to_delete = context.user_data.get('messages_to_delete', [])
    messages_to_delete.append(update.message.message_id)
    if not email or not password:
        await update.message.reply_text("❌ Missing email or password. Please try again.")
        return ConversationHandler.END
    
    login_result = login_user(email, password)

    if login_result["success"]:
        
        user_id = login_result["user_id"]
        user_sessions[update.message.from_user.id] = user_id
        
        # Query Firestore for barber data
        collection_ref = db.collection('barbers')
        
        query = collection_ref.where("email", "==", email)
        
        
        result = query.stream()
        print(result)
        result_list = []
        for doc in result:
            print(doc)
            result_list.append(doc)
            if len(result_list) > 1:  # Safety check
                break
        
        # Check if barber exists (maybe suspended or something?)
        if not result_list:
            print("LOGGED IN BUT NO DATA!!!!! ")
            await update.message.reply_text("There was a problem logging in to your account.\nPlease contact customer service for more details!")
            return ConversationHandler.END
        
        
        user = auth.get_user_by_email(email)
        uid = user.uid
        # Save barber object to context.user_data
        barber_doc = result_list[0].to_dict()
        current_barber = Barber(
            address=barber_doc.get('address'),
            email=barber_doc.get('email'),
            name=barber_doc.get('name'),
            desc_id=barber_doc.get('description_id'),
            postal=barber_doc.get('postal code'),
            region=barber_doc.get('region'),
            portfolio=barber_doc.get('portfolio_link'),
            doc_id=result_list[0].id,
            uuid=uid
        )
        context.user_data['current_user'] = current_barber
        context.user_data['logged_in'] = True
        print("\n✅ Barber object saved to context.user_data\n")
        
        # Send the welcome message
        welcome_message = f"✅ Login successful\\! 🎉\nWelcome back, *{current_barber.name}* 👋"
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN_V2)
        await menu(update, context)

    else:
        error_message = f"Invalid Login Credentials 🚫 Try again with /login"
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN_V2)
    
    # Delete the past 4 messages (email and password prompts and responses)
    try:
        # Use context.bot instead of update.bot
        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=messages_to_delete)
    except Exception as e:
        print(f"Error deleting message: {e}")
        
    # Clear sensitive data
    context.user_data['messages_to_delete'] = []
    context.user_data.pop("login_email", None)
    context.user_data.pop("login_password", None)

    return ConversationHandler.END

# sign out:
async def sign_out(update: Update, context: CallbackContext) -> None:
    print("Signing out user...")
    await clear_menu(update, context) # clear previous menus

    user_id = update.effective_user.id
    
    # Clear user session data
    context.user_data.clear()  # Remove everything stored in user_data
    
    # Optionally remove from global session dict
    user_sessions.pop(user_id, None)

    # Notify the user
    if update.message:
        await update.message.reply_text("🚪 You have been signed out. Tap /start to start again")
    elif update.callback_query:
        await update.callback_query.message.reply_text("🚪 You have been signed out. Tap /start to start again")

async def back_to_main(update:Update, context:CallbackContext):
    await menu(update, context)
    return ConversationHandler.END

# Define the login conversation handler
# The entry point for the /login command is already here:
login_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("login", start_login),  # This works when /login is typed
                  CallbackQueryHandler(start_login, pattern='login')],  # Trigger for button press
    states={
        EMAIL: [MessageHandler(filters.TEXT  & ~filters.COMMAND, get_password)],
        PASSWORD: [MessageHandler(filters.TEXT  & ~filters.COMMAND, get_login_details)],
    },
    fallbacks=[
        CommandHandler("menu", back_to_main)
    ],
    per_user=True,
    allow_reentry=True
)


# ---- Sign Up Conversation Handler ---- #
# States
EMAIL_SU, PASSWORD_SU, NAME_SU, ADDRESS_SU, POSTCODE_SU, REGION_SU = range(6)

### Step 1: Ask for email ###
async def get_email_su(update: Update, context: CallbackContext) -> int:
    await update.callback_query.message.reply_text("Please enter your email address:")
    return EMAIL_SU

### Step 2: Save email and ask for password ###
async def get_password_su(update: Update, context: CallbackContext) -> int:
    email = update.message.text.strip()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await update.message.reply_text("❌ Invalid email format. Please enter a valid email:")
        return EMAIL_SU

    context.user_data["email"] = email
    await update.message.reply_text("Please enter your password:")
    return PASSWORD_SU

### Step 3: Save password and ask for name ###
async def get_name_su(update: Update, context: CallbackContext) -> int:
    context.user_data["password"] = update.message.text.strip()  # WARNING: Never store plaintext passwords in production
    await update.message.reply_text("Please enter your full name:")
    return NAME_SU

### Step 4: Save address and ask for postcode ###
async def get_postcode_su(update: Update, context: CallbackContext) -> int:
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Please enter your postal code:")
    return POSTCODE_SU

### Step 5: Save name and ask for address ###
async def get_address_su(update: Update, context: CallbackContext) -> int:
    postal = update.message.text.strip()

    # Check if it's 6 digits
    if not re.match(r"^\d{6}$", postal):
        await update.message.reply_text("❌ Postal code must be 6 digits. Try again:")
        return POSTCODE_SU

    # Check if first 2 digits represent a valid SG sector (01–82)
    sector = int(postal[:2])
    if not (1 <= sector <= 82):
        await update.message.reply_text("❌ Invalid Singapore postal code. Please try again:")
        return POSTCODE_SU

    context.user_data["postal"] = postal
    
    await update.message.reply_text("Please enter your address:")
    return ADDRESS_SU

async def get_region_su(update: Update, context: CallbackContext) -> int:
    raw_address = update.message.text.strip()

    # Remove trailing 6-digit postal code if present (with or without comma/space)
    cleaned_address = re.sub(r"[\s,]*\d{6}$", "", raw_address).strip()

    context.user_data["address"] = cleaned_address

    # Create inline keyboard with 6 regions (2 buttons per row)
    keyboard = [
        [
            InlineKeyboardButton("East", callback_data="east"),
            InlineKeyboardButton("West", callback_data="west")
        ],
        [
            InlineKeyboardButton("South", callback_data="south"),
            InlineKeyboardButton("North", callback_data="north")
        ],
        [
            InlineKeyboardButton("Central", callback_data="central"),
            InlineKeyboardButton("North-East", callback_data="northeast")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Please select your region:",
        reply_markup=reply_markup
    )
    return REGION_SU


### Final Step: Save region, create Barber, and push to DB ###
async def create_barber_and_save(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    # Save selected region
    context.user_data["region"] = query.data

    # Create Barber object without doc_id (it will be set by add_to_db_with_auth)
    barber = Barber(
        name=context.user_data["name"],
        email=context.user_data["email"],
        address=context.user_data["address"],
        postal=context.user_data["postal"],
        region=context.user_data["region"],
        doc_id=None
    )

    db = firestore.client()
    password = context.user_data.get("password")

    # if not password:
    #     await update.message.reply_text("❌ Password not found. Please restart the signup.")
    #     return ConversationHandler.END

    success = barber.add_to_db_with_auth(db, password)

    if success:
        await update.callback_query.message.reply_text("✅ You have been successfully registered!")
    else:
        await update.callback_query.message.reply_text("❌ Something went wrong during registration.")

    return ConversationHandler.END

### Cancel handler ###
async def cancel_sign_up(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Sign-up process cancelled.")
    return ConversationHandler.END

signup_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(get_email_su, pattern='signup')],
    states={
        EMAIL_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password_su)],
        PASSWORD_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name_su)],
        NAME_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_postcode_su)],
        POSTCODE_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address_su)],
        ADDRESS_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_region_su)],
        REGION_SU: [CallbackQueryHandler(create_barber_and_save, pattern=r"^(east|west|south|north|central|northeast)$")],
    },
    fallbacks=[CommandHandler("cancel", cancel_sign_up)],
    per_user=True,
    allow_reentry=True
)
