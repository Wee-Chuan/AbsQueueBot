# ==================== IMPORTS ====================
import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# telegram imports
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton

# utils imports
from client_side.utils.globals import *
from client_side.utils.core_commands import *
from client_side.utils.keyboards import Keyboards
from client_side.utils.messages import Messages
from shared.utils import HelperUtils

# Classes imports
from client_side.classes.booking import Booking
from client_side.classes.customer import Customer

from datetime import datetime

# ==================== CONSTANTS ====================
# State constants
SEARCH_OPTION, SEARCH_BARBER, REQUEST_LOCATION, SELECT_BARBER, BARBER_DETAILS = range(5)
LEARN_MORE, VIEW_RATINGS_REVIEWS, SELECT_SERVICE, SELECT_SLOT, REQUEST_CONTACT = range(5, 10)
CONFIRM_CONTACT, CONFIRM_BOOKING = range(10, 12)

# Pagination constants
BARBER_PER_PAGE = 5

# ==================== OPTION FLOW ====================
@HelperUtils.check_conversation_active
async def search_option(update: Update, context: CallbackContext) -> int:
    """Display search options (region/location)"""
    Booking.initialize_booking(context)

    # Generate the keyboard using the Keyboards class
    keyboard = Keyboards.search_options()       # Keyboard for search options
    keyboard.append(Keyboards.home_button())    # Add home button
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use the Messages class to generate the header message
    message_text = Messages.header_message("search_option")

    if update.callback_query:
        msg = await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        msg = await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
        )
    
    HelperUtils.store_message_id(context, msg.message_id)  # Store message ID
    return SEARCH_OPTION

# ==================== SEARCH HANDLERS ====================
async def handle_search_option(update: Update, context: CallbackContext) -> int:
    """Handle search option selection."""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    # Clear previous search data
    HelperUtils.clear_user_data(context, [
        "search_type", 
        "selected_region",
        "barbers_location", 
        "barber_name",
        "barber_info",
        "barber_doc_id",
        "all_barbers",
    ])

    # Get barbers location data once for all search types
    barbers_location = HelperUtils.get_user_data(context, "barbers_location")
    if not barbers_location:
        barbers_location = Customer.get_barbers_location(db, GEOCODING_API_KEY)
        HelperUtils.set_user_data(context, "barbers_location", barbers_location)
    
    # Get all barbers data once for all search types
    barbers = HelperUtils.get_user_data(context, "all_barbers")
    if not barbers:
        barbers = Customer.get_all_barbers(db)
        HelperUtils.set_user_data(context, "all_barbers", barbers)

    search_type = query.data.replace("search_by_", "")
    HelperUtils.set_user_data(context, "search_type", search_type)

    if search_type == "location":
        return await search_by_location(update, context)
    elif search_type == "region":
        return await select_region(update, context)
    elif search_type == "favorites":
        return await favorite_barbers(update, context)
    elif search_type == "name":
        return await start_search_barber(update, context)

# ==================== OPTIONS ====================
@HelperUtils.check_conversation_active
async def favorite_barbers(update: Update, context: CallbackContext) -> int:
    """Handle favorite barbers display"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    favorited_barbers = Customer.get_followed_barbers(db, user.id)
    
    if not favorited_barbers:
        await query.edit_message_text(
            text="You do not have any favorited barbers.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="back_to_search_option")]
            ])
        )
        return SEARCH_OPTION
    
    return await select_barber(update, context, page=0, barbers=favorited_barbers)

@HelperUtils.check_conversation_active
async def start_search_barber(update: Update, context: CallbackContext) -> int:
    """Start search for barber"""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query

    # Clear previous messages first
    await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

    # Add a "Back to Menu" button
    keyboard = [[InlineKeyboardButton("◀", callback_data="back_to_search_option")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Try to edit the existing message
        msg = await query.edit_message_text(
            "Please enter the barber's name:", 
            reply_markup=reply_markup
        )
    except Exception:
        # Fallback to new message if edit fails
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please enter the barber's name:",
            reply_markup=reply_markup
        )

    HelperUtils.store_message_id(context, msg.message_id)
    return SEARCH_BARBER
    
@HelperUtils.check_conversation_active
async def search_by_location(update: Update, context: CallbackContext) -> int:
    """Search for barber by location"""
    query = update.callback_query
    await query.answer()

    msg = await update.effective_message.reply_text(
        Messages.header_message("search_by_location"),
        reply_markup=Keyboards.search_by_location()
    )
    HelperUtils.store_message_id(context, msg.message_id)  # Store message ID

    # Provide a fallback 
    msg = await update.effective_message.reply_text(
        "If location sharing is not supported on your platform, press /cancel and go back to menu."
    )

    HelperUtils.store_message_id(context, msg.message_id)
    return REQUEST_LOCATION

@HelperUtils.check_conversation_active
async def select_region(update: Update, context: CallbackContext) -> int:
    """Display region options."""       
    query = update.callback_query
    await query.answer()

    # Clear any previous selected region
    HelperUtils.clear_user_data(context, "selected_region")

    # Generate the keyboard using the Keyboards class
    keyboard = Keyboards.search_by_region()     # Keyboard for region options
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = Messages.header_message("select_region")

    if query:
        msg = await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        msg = await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    
    HelperUtils.store_message_id(context, msg.message_id)  # Store message ID
    return SELECT_BARBER

# ==================== BARBER SELECTION FLOW ====================
@HelperUtils.check_conversation_active
async def select_barber(update: Update, context: CallbackContext, page: int=0, barbers=None) -> int:
    """Function to show barbers of selected region."""
    # Clear previously stored barber-related data
    HelperUtils.clear_user_data(context, [
        "barber_info",
        "barber_doc_id",
        "current_page",
        "available_slots",
    ])
    
    try:
        query = update.callback_query
        search_type = HelperUtils.get_user_data(context, "search_type")
        region = HelperUtils.get_user_data(context, "selected_region")
            
        if search_type == "region" and not barbers:
            if query and query.data.startswith("region_"): 
                region = query.data.replace("region_", "")             
                HelperUtils.set_user_data(context, "selected_region", region)
            
            # Get all barbers from the database
            barbers = HelperUtils.get_user_data(context, "all_barbers")

            # Filter barbers by region
            barbers = Booking.filter_by_region(barbers, region)

            # Sort barbers alphabetically by name
            barbers = dict(sorted(barbers.items(), key=lambda item: item[1]["name"].lower()))
        
        if not barbers:
            # Use the Messages class to generate the error message
            error_message = Messages.error_message(
                "no_barbers_found" if search_type != "location" else "no_location_barbers"
            )
            if query:
                await query.answer(text=error_message, show_alert=True)
                return SELECT_BARBER
        
        # Pagination
        start_index = page * BARBER_PER_PAGE
        end_index = start_index + BARBER_PER_PAGE
        barbers_page = list(barbers.items())[start_index:end_index]

        # Generate the keyboard using the Keyboards class
        keyboard = Keyboards.select_barber_keyboard(
            barbers_page, start_index, end_index, len(barbers), page, search_type
        )  # Keyboard for barber selection
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Clear previous messages first
        await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

        # Determine the message text based on search type using the Messages class
        message_text = Messages.header_message(
            "select_barber", 
            details={
                "region": region, 
                "is_location_search": search_type == "location",
                "is_favorites": search_type == "favorites"
            }
        ) 

        if query:
            msg = await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            msg = await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode="HTML")
        
        HelperUtils.store_message_id(context, msg.message_id)  # Store message ID

        # Store the current page in user_data
        HelperUtils.set_user_data(context, "current_page", page)

        return BARBER_DETAILS

    except Exception as e:
        # Use the Messages class to generate a generic error message
        error_message = Messages.error_message("generic_error", additional_info=str(e))
        if query:
            await query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)

        HelperUtils.reset_conversation_state(context)
        return ConversationHandler.END

# ==================== BARBER DETAILS ====================
@HelperUtils.check_conversation_active
async def view_barber_details(update: Update, context: CallbackContext) -> int:
    """Display barber details along with view services option, learn more and follow options"""
    query = update.callback_query
    await query.answer()  # Acknowledge callback query

    if query.data.startswith(("barber_")):
        await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

    # Handle follow/unfollow actions first
    if query.data.startswith(("follow_", "unfollow_")):
        doc_id = query.data.split("_")[1]  # Extract doc_id from either follow_ or unfollow_
        username = update.effective_user.username or str(update.effective_user.id)
        user_id = update.effective_user.id or str(update.effective_user.id)
        
        if query.data.startswith("follow_"):
            Customer.follow_barber(db, doc_id, username, user_id)
        else:
            Customer.unfollow_barber(db, doc_id, user_id)
        
        # Update the doc_id in context for consistency
        HelperUtils.set_user_data(context, "barber_doc_id", doc_id)
    else:
        # Existing doc_id handling for non-follow actions
        doc_id = HelperUtils.get_user_data(context, "barber_doc_id")
        if not doc_id and query.data.startswith("barber_"):
            doc_id = query.data.replace("barber_", "")
            HelperUtils.set_user_data(context, "barber_doc_id", doc_id)

    barbers = HelperUtils.get_user_data(context, "all_barbers")
    barber_info = barbers.get(doc_id)

    if not barber_info:
        error_message = Messages.error_message("barber_not_found")
        await query.answer(error_message)
        return BARBER_DETAILS
    
    user_id = update.effective_user.id or str(update.effective_user.id)
    is_following = Customer.is_user_following(db, doc_id, user_id)
    search_type = HelperUtils.get_user_data(context, "search_type")
    barbers_location = HelperUtils.get_user_data(context, "barbers_location")

    # Enrich barber info with location data if available
    if barbers_location and doc_id in barbers_location:
        enriched_info = barbers_location[doc_id]
        barber_info["latitude"] = enriched_info.get("latitude")
        barber_info["longitude"] = enriched_info.get("longitude")
        if "distance_km" in barber_info:
                barber_info["distance_km"] = enriched_info.get("distance_km")

    HelperUtils.set_user_data(context, "barber_info", barber_info) 
    response_text = Messages.barber_details(barber_info)
    keyboard = Keyboards.barber_details(doc_id, is_following, search_type)
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Handle message display
    if query.data.startswith(("follow_", "unfollow_", "back_to_info")):
        try:
            await query.edit_message_text(
                text=response_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error editing message: {e}")
            # Fallback to sending new message if edit fails
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    elif barber_info.get("latitude") and barber_info.get("longitude"):
        try:
            # Send location map
            location_msg = await context.bot.send_location(
                chat_id=update.effective_chat.id,
                latitude=barber_info["latitude"],
                longitude=barber_info["longitude"]
            )
            HelperUtils.store_message_id(context, location_msg.message_id)

            # Send details message
            details_msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            HelperUtils.store_message_id(context, details_msg.message_id)
        except Exception as e:
            print(f"Error sending location: {e}")
            # Fallback to text with address
            fallback_text = f"{response_text}\n\n📍 Location: {barber_info.get('address', 'Not available')}"
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=fallback_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            HelperUtils.store_message_id(context, msg.message_id)
    else:
        # No coordinates available
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        HelperUtils.store_message_id(context, msg.message_id)

    return SELECT_SERVICE

@HelperUtils.check_conversation_active
async def search_barber(update: Update, context: CallbackContext) -> int:
    """Display details for search by name option"""
    query = update.callback_query
    if query:
        await query.answer()

    # Handle follow/unfollow actions
    if query and query.data.startswith(("search_follow_", "search_unfollow_")):
        doc_id = query.data.split("_")[2]  # Extract doc_id 
        username = update.effective_user.username or str(update.effective_user.id)
        user_id = update.effective_user.id or str(update.effective_user.id)
        
        if query.data.startswith("search_follow_"):
            Customer.follow_barber(db, doc_id, username, user_id)
        else:
            Customer.unfollow_barber(db, doc_id, user_id)
        
        # Update the doc_id in context for consistency
        HelperUtils.set_user_data(context, "barber_doc_id", doc_id)
        barber_info = HelperUtils.get_user_data(context, "barber_info")
        if not barber_info:
            barber_info = Booking.search_barber_by_name(HelperUtils.get_user_data(context, "barber_name"), db)
            HelperUtils.set_user_data(context, "barber_info", barber_info)
        
        # Check the new follow status
        is_following = Customer.is_user_following(db, doc_id, user_id)

        response_text = Messages.barber_details(barber_info)
        keyboard = [
            [InlineKeyboardButton("📋 View Services", callback_data=f"select_services_{doc_id}")],
            [InlineKeyboardButton("ℹ️ Learn more", callback_data=f"learn_more_{doc_id}")],
            [InlineKeyboardButton("💬 Ratings & Reviews", callback_data=f"view_ratings_reviews_{doc_id}")],
            [InlineKeyboardButton("⭐ Favorited" if is_following else "➕ Favorite this barber to get notified", 
                                callback_data=f"search_unfollow_{doc_id}" if is_following else f"search_follow_{doc_id}")],
            [InlineKeyboardButton("◀", callback_data="back_to_search"), 
            InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
        ]
        
        await query.edit_message_text(
            text=response_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        return SELECT_SERVICE 
    
    # Get barber name from message or callback query
    if update.message:
        barber_name = update.message.text                                   # Extract the barber's name from the message
        print(f"Barber name from message: {barber_name}")
        HelperUtils.set_user_data(context, "barber_name", barber_name)
        HelperUtils.store_message_id(context, update.message.message_id)    # Store the user's search message ID
    elif update.callback_query:
        await update.callback_query.answer()                                
        barber_name = HelperUtils.get_user_data(context, "barber_name")     # Retrieve the barber's name from user data
        if not barber_name:
            msg = await update.callback_query.edit_message_text("🙁 No barber name provided. Please try again.")
            HelperUtils.store_message_id(context, msg.message_id)
            return SEARCH_BARBER
        
        # Store the callback query message ID
        HelperUtils.store_message_id(context, update.callback_query.message.message_id)
    else:
        HelperUtils.reset_conversation_state(context)
        return ConversationHandler.END

    try:
        barber_info = Booking.search_barber_by_name(barber_name, db)
        print("Barber Info", barber_info)

        if not barber_info:
            error_message = Messages.error_message("barber_not_found")
            if update.message:
                msg = await update.message.reply_text(
                        error_message,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔍 Try Again", callback_data="search_barber")]
                        ])
                    )
            HelperUtils.store_message_id(context, msg.message_id)
            return SEARCH_BARBER

        doc_id = barber_info['doc_id']
        user_id = update.effective_user.id or str(update.effective_user.id)
        is_following = Customer.is_user_following(db, doc_id, user_id)

        # Enrich with location data if available
        barbers_location = HelperUtils.get_user_data(context, "barbers_location")
        if barbers_location and doc_id in barbers_location:
            enriched_info = barbers_location[doc_id]
            # Add latitude and longitude to barber_info
            barber_info["latitude"] = enriched_info.get("latitude")
            barber_info["longitude"] = enriched_info.get("longitude")

        HelperUtils.set_user_data(context, "barber_info", barber_info) # Store the barber's info in user data
        HelperUtils.set_user_data(context, "barber_doc_id", doc_id)

        # Prepare barber details
        response_text = Messages.barber_details(barber_info)
        keyboard = [
            [InlineKeyboardButton("📋 View Services", callback_data=f"select_services_{doc_id}")],
            [InlineKeyboardButton("ℹ️ Learn more", callback_data=f"learn_more_{doc_id}")],
            [InlineKeyboardButton("💬 Ratings & Reviews", callback_data=f"view_ratings_reviews_{doc_id}")],
            [InlineKeyboardButton("⭐ Favorited" if is_following else "➕ Favorite this barber to get notified", 
                                callback_data=f"search_unfollow_{doc_id}" if is_following else f"search_follow_{doc_id}")],
            [InlineKeyboardButton("◀ Back to search", callback_data="back_to_search"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Handle location display if available
        if barber_info.get("latitude") and barber_info.get("longitude"):
            try:
                if update.message:
                    location_msg = await update.message.reply_location(
                        latitude=barber_info["latitude"],
                        longitude=barber_info["longitude"]
                    )
                    HelperUtils.store_message_id(context, location_msg.message_id)
                    details_msg = await update.message.reply_text(
                        text=response_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    HelperUtils.store_message_id(context, details_msg.message_id)
                # For callback queries (from button presses)
                elif query:
                    details_msg = await query.edit_message_text(
                        text=response_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    HelperUtils.store_message_id(context, details_msg.message_id)
            except Exception as e:
                print(f"Error sending location: {e}")
                # Fallback to text display if location fails
                fallback_text = f"{response_text}\n\n📍 Location: {barber_info.get('address', 'Address not available')}"
                if update.message:
                    msg = await update.message.reply_text(
                        text=fallback_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                elif query:
                    msg = await query.edit_message_text(
                        text=fallback_text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                HelperUtils.store_message_id(context, msg.message_id)
        else:
            # No location available
            if update.message:
                msg = await update.message.reply_text(
                    text=response_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            elif query:
                msg = await query.edit_message_text(
                    text=response_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            HelperUtils.store_message_id(context, msg.message_id)

        return SELECT_SERVICE
        
    except Exception as e:
        error_message = Messages.error_message("generic_error", additional_info=str(e))
        if update.message:
            await update.message.reply_text(error_message)
        elif query:
            await query.edit_message_text(error_message)
        HelperUtils.reset_conversation_state(context)
        return ConversationHandler.END

# ==================== BOOKING FLOW ====================
@HelperUtils.check_conversation_active
async def select_service(update: Update, context: CallbackContext) -> int:
    """Show available services from the selected barber"""
    query = update.callback_query
    search_type = HelperUtils.get_user_data(context, "search_type")
    
    barber_info = HelperUtils.get_user_data(context, "barber_info")
    if not barber_info or not isinstance(barber_info, dict):
        error_message = Messages.error_message("barber_not_found")
        await query.answer(error_message)
        return SELECT_SERVICE

    barber_name = barber_info["name"]
    HelperUtils.set_user_data(context, "barber_name", barber_name)  # Store the selected barber's name
    barber_doc_id = context.user_data.get("barber_doc_id")

    try:
        services = Booking.get_barber_services(barber_name, db)     # Fetch barber's services from Firestore

        if not services:
            error_message = Messages.error_message("no_services")
            await query.answer(error_message, show_alert=True)
            
            return SELECT_SERVICE
    
        # Create inline buttons for each service
        # callback_data is used to store the service id
        keyboard = [
            [InlineKeyboardButton(f"{service['name']} - ${service['price']}", callback_data=f"service_{service_id}")]
            for service_id, service in services
        ]

        keyboard.extend(Keyboards.service_keyboard(barber_doc_id, search_type))  # Add back button to barber details
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Use the Messages class to generate the header message
        message = Messages.header_message("select_service", {"barber_name": barber_name})

        msg = await query.edit_message_text(
            message, 
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        HelperUtils.store_message_id(context, msg.message_id)

        return SELECT_SLOT

    except Exception as e:
        error_message = Messages.error_message("generic_error", additional_info=str(e))
        await query.edit_message_text(error_message)
        HelperUtils.reset_conversation_state(context)
        return ConversationHandler.END

@HelperUtils.check_conversation_active
async def learn_more(update: Update, context: CallbackContext) -> int:
    """Learn more about barber."""
    query = update.callback_query

    barber_info = HelperUtils.get_user_data(context, "barber_info")
    if not barber_info:
        error_message = Messages.error_message("barber_not_found")
        await query.answer(error_message)
        return SELECT_SERVICE
    
    if barber_info["instagram"] == None and barber_info["facebook"] == None and barber_info["website"] == None and barber_info["portfolio_link"] == None:
        await query.answer("🙁 No portfolio available for this barber.", show_alert=True)
        return SELECT_SERVICE
    
    # Get search type
    search_type = HelperUtils.get_user_data(context, "search_type")

    # Use the Messages class to generate the "Learn more" message
    message = Messages.learn_more_message(barber_info)

    # Use the Keyboards class 
    keyboard = Keyboards.learn_more_keyboard(barber_info, context.user_data["barber_doc_id"], search_type)
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await query.edit_message_text(
        text=message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    HelperUtils.store_message_id(context, msg.message_id)

    return LEARN_MORE

# ==================== RATINGS AND REVIEWS ====================
@HelperUtils.check_conversation_active
async def view_ratings_reviews(update: Update, context: CallbackContext) -> int:
    """View ratings and reviews for the barber."""
    query = update.callback_query

    barber_info = HelperUtils.get_user_data(context, "barber_info")
    if not barber_info:
        error_message = Messages.error_message("barber_not_found")
        await query.edit_message_text(error_message)
        return SELECT_SERVICE

    barber_name = barber_info["name"]

    # Find the correct barber document ID
    barber_doc_id = context.user_data.get("barber_doc_id")
    if not barber_doc_id:
        error_message = Messages.error_message("barber_not_found")
        await query.edit_message_text(error_message)
        return SELECT_SERVICE
    
    # Fetch reviews
    reviews_ref = db.collection("barbers").document(barber_doc_id).collection("ratings and reviews")
    reviews = list(reviews_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream())

    if not reviews:
        await query.answer("🙁 No ratings or reviews found.", show_alert=True)
        return SELECT_SERVICE

    # Store reviews in user_data
    context.user_data["reviews_list"] = [r.to_dict() for r in reviews]
    context.user_data["current_review_index"] = 0

    return await paginate_ratings_reviews(update, context)

@HelperUtils.check_conversation_active
async def paginate_ratings_reviews(update: Update, context: CallbackContext) -> int:
    """ Show one review and rating at a time """
    query = update.callback_query

    reviews_list = context.user_data.get("reviews_list", [])
    current_index = context.user_data.get("current_review_index", 0)
    total = len(reviews_list)

    if not reviews_list:
        await query.answer("🙁 No ratings or reviews found.", show_alert=True)
        return SELECT_SERVICE

    # Compute average and total ratings
    valid_ratings = [
        int(r.get("rating")) for r in reviews_list
        if isinstance(r.get("rating"), int) or (isinstance(r.get("rating"), str) and r.get("rating").isdigit())
    ]
    total_ratings = len(valid_ratings)
    average_rating = round(sum(valid_ratings) / total_ratings, 1) if total_ratings > 0 else 0
    summary_line = f"<b>⭐ {average_rating} ({total_ratings})</b>\n\n"

    # Get the current review
    review_data = reviews_list[current_index]
    rating = review_data.get("rating", "No rating")
    review_text = review_data.get("review", "No review text")
    reviewer_name = review_data.get("reviewer_name", "Anonymous")
    timestamp = review_data.get("timestamp")
    
    # Format timestamp
    if timestamp:
        date_str = timestamp.strftime("%a, %d %b %Y at %I:%M %p")
    else:
        date_str = "No date available"
    
    # Generate star rating
    try:
        rating = int(rating)  # Ensure rating is an integer
        stars = "⭐" * rating + "☆" * (5 - rating)
    except (TypeError, ValueError):
        stars = "No rating"

    barber_info = HelperUtils.get_user_data(context, "barber_info")
    barber_name = barber_info["name"]

    text = (
        f"<b>{stars}</b>\n"
        f"<b>{reviewer_name}</b>\n"
        f"<i>{date_str}</i>\n\n"
        f"{review_text}"
    )

    # Add review counter (optional)
    text = summary_line + f"<b>Review {current_index+1} of {total}</b>\n\n" + text

    # Pagination buttons
    buttons = []
    if current_index > 0:
        buttons.append(InlineKeyboardButton("◀️ Back", callback_data="review_prev"))
    if current_index < total - 1:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data="review_next"))
    
    # Back to Info/Home buttons
    search_type = HelperUtils.get_user_data(context, "search_type")
    if search_type == "name":
        nav_buttons = [InlineKeyboardButton("◀", callback_data="back_to_search_info")]
    elif search_type == "location":
        nav_buttons = [InlineKeyboardButton("◀", callback_data="back_to_info")]
    else:
        nav_buttons = [InlineKeyboardButton("◀", callback_data="back_to_info")]
    nav_buttons.append(InlineKeyboardButton("🏠 Home", callback_data="back_to_menu"))

    keyboard = [buttons] if buttons else []
    keyboard.append(nav_buttons)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
    HelperUtils.store_message_id(context, query.message.message_id)

    return VIEW_RATINGS_REVIEWS

async def review_next(update: Update, context: CallbackContext) -> int:
    context.user_data["current_review_index"] += 1
    return await paginate_ratings_reviews(update, context)

async def review_prev(update: Update, context: CallbackContext) -> int:
    context.user_data["current_review_index"] -= 1
    return await paginate_ratings_reviews(update, context)

# ==================== SLOT SELECTION ====================
@HelperUtils.check_conversation_active
async def select_slot(update: Update, context: CallbackContext, page: int=0) -> int:
    """Function to select slot after choosing a service."""
    query = update.callback_query

    if query.data and query.data.startswith("service_"):
        service_id = query.data.replace("service_", "")
        HelperUtils.set_user_data(context, "service_id", service_id)
    else:
        service_id = HelperUtils.get_user_data(context, "service_id")       

    barber_info = HelperUtils.get_user_data(context, "barber_info")
    if not barber_info or not isinstance(barber_info, dict):
        error_message = Messages.error_message("barber_not_found")
        await query.edit_message_text(error_message)
        return ConversationHandler.END
    
    barber_email = barber_info["email"]                                 # Retrieve the selected barber's email
    HelperUtils.set_user_data(context, "barber_email", barber_email)    # Store the selected barber's email

    try:
        # Fetch available slots for the selected barber
        all_slots = HelperUtils.get_user_data(context, "available_slots")
        if not all_slots:
            all_slots = Booking.get_available_slots(barber_email, db)
            HelperUtils.set_user_data(context, "available_slots", all_slots)
        print(f"All slots: {all_slots}")

        if not all_slots:
            error_message = Messages.error_message("no_slots")
            await query.answer(error_message, show_alert=True)

            return SELECT_SLOT

        # Organize slots by date
        slots_by_date = {}
        for slot_id, start_time in all_slots:
            date_key = start_time.date()
            if date_key not in slots_by_date:
                slots_by_date[date_key] = []
                slots_by_date[date_key] = {
                    'available': [],
                    'completed': [],
                    'booked': [],
                    'no_show': [],
                }
            slots_by_date[date_key]['available'].append((slot_id, start_time))

        # Get current month and year (or from callback data)
        today = datetime.now().date()
        if query.data and query.data.startswith("calendar_"):
            _, action, year, month = query.data.split("_")
            year, month = int(year), int(month)
            if action == "prev":
                month -= 1
                if month < 1:
                    month = 12
                    year -= 1
            elif action == "next":
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            year, month = today.year, today.month
        
        # Generate calendar for the selected month/year
        calendar_keyboard = Keyboards.generate_calendar(year, month, slots_by_date)

        # Add navigation and action buttons
        keyboard = calendar_keyboard
        keyboard.append([InlineKeyboardButton("◀", callback_data="back_to_services"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Use the Messages class to generate the header message
        message = Messages.header_message("select_slot")

        msg = await query.edit_message_text(message, reply_markup=reply_markup)

        HelperUtils.store_message_id(context, msg.message_id)

        return REQUEST_CONTACT

    except Exception as e:
        error_message = Messages.error_message("generic_error", additional_info=str(e))
        await query.edit_message_text(error_message)
        HelperUtils.reset_conversation_state(context)
        return ConversationHandler.END

async def handle_date_selection(update: Update, context: CallbackContext) -> int:
    """Handle when a user selects a date from the calendar."""
    query = update.callback_query
    
    try:
        _, year, month, day = query.data.split("_")
        selected_date = datetime(int(year), int(month), int(day)).date()
        print(f"Selected date: {selected_date}")
        
        # Get available slots for this barber
        barber_email = HelperUtils.get_user_data(context, "barber_email")
        all_slots = HelperUtils.get_user_data(context, "available_slots")
        
        # Filter slots for selected date
        date_slots = [(slot_id, start_time) for slot_id, start_time in all_slots 
                    if start_time.date() == selected_date]
        
        if not date_slots:
            await query.answer(f"🙁 No slots found for {selected_date.strftime('%d %b %Y')}", show_alert=True)
            return REQUEST_CONTACT
        
        # Show time slots for selected date
        keyboard = []
        for slot_id, start_time in sorted(date_slots, key=lambda x: x[1]):
            keyboard.append([
                InlineKeyboardButton(
                    start_time.strftime("%I:%M %p"),
                    callback_data=f"slot_{slot_id}"
                )
            ])
        
        # Add back button to return to calendar
        keyboard.append([
            InlineKeyboardButton("◀", callback_data="back_to_calendar"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"Available slots for {selected_date.strftime('%A, %B %d, %Y')}:"
        await query.edit_message_text(message, reply_markup=reply_markup)
        
        return REQUEST_CONTACT

    except Exception as e:
        # Handle unexpected errors
        error_message = Messages.error_message("generic_error", additional_info=str(e))
        await query.edit_message_text(error_message)
        return ConversationHandler.END

@HelperUtils.check_conversation_active
async def request_contact(update: Update, context: CallbackContext) -> int:
    """ Request user's contact info after selecting a slot """
    query = update.callback_query
    slot_id = query.data.replace("slot_", "")
    HelperUtils.set_user_data(context, "slot_id", slot_id) # Store the selected slot id

    reply_markup = Keyboards.contact_keyboard() # Keyboard for requesting contact info

    # Store the callback query
    HelperUtils.set_user_data(context, "callback_query", query)

    await query.answer()
    msg = await query.message.reply_text(
        Messages.header_message("share_contact"), 
        reply_markup=reply_markup
    )

    HelperUtils.store_message_id(context, msg.message_id)

    return CONFIRM_CONTACT

@HelperUtils.check_conversation_active
async def confirm_contact(update: Update, context: CallbackContext) -> int:
    """ Confirm the user's contact number and proceed to booking confirmation """
    # Clear previous messages
    await HelperUtils.clear_previous_messages(context, update.effective_chat.id)

    contact = update.message.contact

    if not contact:
        await update.message.reply_text("Please use the button to share your contact.")
        return REQUEST_CONTACT

    # Store contact info and message ID
    HelperUtils.set_user_data(context, "phone_number", contact.phone_number)
    HelperUtils.store_message_id(context, update.message.message_id)

    # Immediately delete the contact message
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        print(f"Couldn't delete contact message: {e}")

    # Remove the previous inline keyboard (if any)
    if "callback_query" in context.user_data:
        try:
            await context.user_data["callback_query"].edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            print(f"Failed to remove inline keyboard: {e}")

    contact_msg = await update.message.reply_text(
        Messages.header_message("contact_received"),
        reply_markup=ReplyKeyboardRemove()  # This removes the button
    )
    HelperUtils.store_message_id(context, contact_msg.message_id)

    # Confirm booking
    keyboard = Keyboards.confirm_booking_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send confirmation message
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=Messages.header_message("confirm_booking"),
        reply_markup=InlineKeyboardMarkup(Keyboards.confirm_booking_keyboard())
    )

    HelperUtils.store_message_id(context, msg.message_id)

    return CONFIRM_BOOKING

@HelperUtils.check_conversation_active
async def confirm_booking(update: Update, context: CallbackContext) -> int:
    """ Confirm the booking and push to the database """
    query = update.callback_query
    await query.answer()                                                    # Acknowledge the button press
    chat_id = query.message.chat.id

    user_response = query.data

    if user_response == "confirm_booking":
        slot_id = HelperUtils.get_user_data(context, "slot_id")             # Retrieve the selected slot id
        service_id = HelperUtils.get_user_data(context, "service_id")       # Retrieve the selected service id
        user_id = query.from_user.id
        user_name = query.from_user.first_name
        phone_number = HelperUtils.get_user_data(context, "phone_number")   # Retrieve the user's phone number
        barber_email = HelperUtils.get_user_data(context, "barber_email")   # Retrieve the selected barber's email
        barber_name = HelperUtils.get_user_data(context, "barber_name")     # Retrieve the selected barber's name

        success, message, start_time, end_time, service_name = Booking.create_booking(
            slot_id, service_id, user_id, user_name, phone_number, barber_email, barber_name, db)

        # Delete stored messages
        if "message_ids" in context.user_data:
            for msg_id in set(context.user_data["message_ids"]):  # Use set to avoid duplicates
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    if "Message to delete not found" not in str(e):
                        print(f"Could not delete message {msg_id}: {e}")

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML"
        )
        HelperUtils.reset_conversation_state(context)

        # Notify the barber if telegram_id is stored
        if success:
            try:
                # Get barber's document
                barber_query = db.collection("barbers").where("email", "==", barber_email).limit(1)
                docs = barber_query.stream()
                barber_doc = next(docs, None)

                if barber_doc:
                    barber_data = barber_doc.to_dict()
                    barber_telegram_id = barber_data.get("telegram_id")

                    if barber_telegram_id:
                        # Get slot details for notification
                        start_time_sgt = Booking.convert_to_sgt(start_time)
                        end_time_sgt = Booking.convert_to_sgt(end_time)

                        # Sanitize variables before sending message
                        if isinstance(user_name, set):
                            user_name = ', '.join(str(x) for x in user_name)
                        if isinstance(phone_number, set):
                            phone_number = ', '.join(str(x) for x in phone_number)
                        if isinstance(service_name, set):
                            service_name = ', '.join(str(x) for x in service_name)
                        if isinstance(barber_name, set):
                            barber_name = ', '.join(str(x) for x in barber_name)

                        await context.bot.send_message(
                            chat_id=barber_telegram_id,
                            text=(
                                f"📢 <b>New Booking Received</b>\n\n"
                                f"👤 <b>Customer:</b> {user_name}\n"
                                f"📞 <b>Phone:</b> {phone_number}\n"
                                f"📋 <b>Service:</b> {service_name}\n"
                                f"🕛 <b>Time:</b> {start_time_sgt.strftime('%I:%M %p')} - {end_time_sgt.strftime('%I:%M %p')}\n"
                                f"📅 <b>Date:</b> {start_time_sgt.strftime('%a %d/%m/%Y')}"
                            ),
                            parse_mode="HTML"
                        )
                    else:
                        print(f"Barber {barber_name} does not have a Telegram ID stored.")
                else:
                    print("Barber document not found.")
            except Exception as e:
                print(f"Failed to notify barber: {e}")

    elif user_response == "cancel_booking":
        # Delete stored messages
        if "message_ids" in context.user_data:
            for msg_id in set(context.user_data["message_ids"]):  # Use set to avoid duplicates
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    if "Message to delete not found" not in str(e):
                        print(f"Could not delete message {msg_id}: {e}")

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Booking cancelled.",
            parse_mode="HTML"
        )
        HelperUtils.store_message_id(context, msg.message_id)
        ConversationHandler.END

    else:
        await query.edit_message_text("⚠️ Invalid action. Please try again.")
        return CONFIRM_BOOKING

# ==================== Pagination Handlers ====================
async def handle_pagination(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()                            # Acknowledge callback query

    page = int(query.data.replace("page_", ""))     # Extract the page number from the callback data
    return await select_barber(update, context, page)

# ==================== Location Handler ====================
async def handle_location(update: Update, context: CallbackContext) -> int:
    """Handle the user's location and find nearby barbers."""
    user_location = update.message.location
    if not user_location:
        await update.message.reply_text(
            "⚠️ Location sharing is not supported on your platform.\n",
            reply_markup=ReplyKeyboardRemove()
        )
        return SEARCH_OPTION
    
    # Delete the user's shared location message
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception as e:
        print(f"Error deleting location message: {e}")

    # Save the user's location in context.user_data
    context.user_data["user_location"] = {
        "latitude": user_location.latitude,
        "longitude": user_location.longitude,
    }

    # Remove the keyboard immediately after receiving location
    msg = await update.message.reply_text(
        "📍 Location received! Searching for nearby barbers...",
        reply_markup=ReplyKeyboardRemove()
    )
    HelperUtils.store_message_id(context, msg.message_id)  # Store message ID

    if HelperUtils.get_user_data(context, "search_type") == "region":
        region = HelperUtils.get_user_data(context, "selected_region")
        all_barbers = HelperUtils.get_user_data(context, "all_barbers")
        barbers_with_locations = HelperUtils.get_user_data(context, "barbers_location")
        
        # Filter barbers by region and calculate distances
        barbers_region = {}
        for doc_id, details in all_barbers.items():
            if doc_id in barbers_with_locations and Booking.filter_by_region({doc_id: details}, region):
                barber_location = barbers_with_locations[doc_id]
                distance = Customer.calculate_distance(
                    user_location.latitude, 
                    user_location.longitude,
                    barber_location['latitude'],
                    barber_location['longitude']
                )
                
                details['distance_km'] = round(distance, 1)
                barbers_region[doc_id] = details

        # Sort by distance
        barbers_region = dict(sorted(
            barbers_region.items(),
            key=lambda item: item[1]['distance_km']
        ))
    
        return await select_barber(update, context, barbers=barbers_region)

    else:
        # Fetch barbers near the user's location
        nearyby_barbers = Customer.get_nearby_barbers(db, context.user_data["user_location"], GEOCODING_API_KEY)

        if not nearyby_barbers:
            error_message = Messages.error_message("no_location_barbers")

            # Create a back button
            keyboard = [[InlineKeyboardButton("◀ Back", callback_data="back_to_search_option")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send the error message with the back button
            msg = await update.message.reply_text(
                error_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

            await HelperUtils.clear_previous_messages(context, update.effective_chat.id)  # Clear previous messages
            HelperUtils.store_message_id(context, msg.message_id)  # Store message ID

            return SEARCH_OPTION

        # Display nearby barbers
        return await select_barber(update, context, barbers=nearyby_barbers)

# ==================== BACK HANDLERS ====================
async def handle_back_to_search_option(update: Update, context: CallbackContext) -> int:
    """Handle the "Back" button callback and display search options again."""
    return await search_option(update, context)

async def handle_back_to_search(update: Update, context: CallbackContext) -> int:
    """Handle the back to search callback"""
    return await start_search_barber(update, context)

async def handle_back_to_region(update: Update, context: CallbackContext) -> int:
    """Handle the "Back to region" button callback and display region options again."""
    return await select_region(update, context)

async def handle_back_to_favorites(update: Update, context: CallbackContext) -> int:
    """Handle the "Back to favorites" button callback and display favorite barbers."""
    return await select_barber(update, context, HelperUtils.get_user_data(context, "current_page"))

async def handle_back_to_barbers(update: Update, context: CallbackContext) -> int:
    """Handle the "Back to barbers" button callback and display barbers options again."""
    await update.callback_query.answer()

    search_type = HelperUtils.get_user_data(context, "search_type")

    # Check if we have user location data (meaning we came from location-based search)
    if  search_type == "location" and "user_location" in context.user_data:
        # Re-fetch nearby barbers for location-based search
        barbers = Customer.get_nearby_barbers(db, context.user_data["user_location"], GEOCODING_API_KEY)
        return await select_barber(update, context, barbers=barbers)
    elif search_type == "favorites":
        # Fetch favorite barbers
        user_id = update.effective_user.id or str(update.effective_user.id)
        barbers = Customer.get_followed_barbers(db, user_id)
        return await select_barber(update, context, barbers=barbers)
    else:
        # Default 
        return await select_barber(update, context, HelperUtils.get_user_data(context, "current_page"))

async def handle_back_to_services(update: Update, context: CallbackContext) -> int:
    """Handle the "Back to services" button callback and display services options again."""
    return await select_service(update, context)

# ==================== CONVERSATION HANDLER DEFINITION ====================
book_slots_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_option, pattern="^book_slots$")],
    states={
        SEARCH_OPTION: [
            CallbackQueryHandler(handle_search_option, pattern="^search_by_(favorites|region|location|name)$"),
            CallbackQueryHandler(handle_back_to_search_option, pattern="^back_to_search_option$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        SEARCH_BARBER: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_barber),
            CallbackQueryHandler(start_search_barber, pattern="^search_barber$"),
            CallbackQueryHandler(handle_back_to_search_option, pattern="^back_to_search_option$"),
        ],
        REQUEST_LOCATION: [
            MessageHandler(filters.LOCATION, handle_location),
            CallbackQueryHandler(handle_back_to_search_option, pattern="^back_to_search_option$"), 
        ],
        SELECT_BARBER: [
            CallbackQueryHandler(select_barber, pattern="^region_"),
            CallbackQueryHandler(handle_back_to_search_option, pattern="^back_to_search_option$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        BARBER_DETAILS: [
            CallbackQueryHandler(search_by_location, pattern="^filter_by_location$"),
            CallbackQueryHandler(view_barber_details, pattern="^barber_"),
            CallbackQueryHandler(handle_pagination, pattern="^page_"),
            CallbackQueryHandler(handle_back_to_region, pattern="^back_to_region"),
            CallbackQueryHandler(handle_back_to_search_option, pattern="^back_to_search_option$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        SELECT_SERVICE: [
            CallbackQueryHandler(select_service, pattern="^select_services_"),
            CallbackQueryHandler(learn_more, pattern="^learn_more_"),
            CallbackQueryHandler(view_ratings_reviews, pattern="^view_ratings_reviews_"),
            CallbackQueryHandler(view_barber_details, pattern="^follow_"),
            CallbackQueryHandler(view_barber_details, pattern="^unfollow_"),
            CallbackQueryHandler(search_barber, pattern="^search_follow_"),
            CallbackQueryHandler(search_barber, pattern="^search_unfollow_"),
            CallbackQueryHandler(handle_back_to_barbers, pattern="^back_to_barbers"),
            CallbackQueryHandler(handle_back_to_search, pattern="^back_to_search$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        LEARN_MORE: [
            CallbackQueryHandler(search_barber, pattern="^back_to_search_info$"),
            CallbackQueryHandler(view_barber_details, pattern="back_to_info"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        VIEW_RATINGS_REVIEWS: [
            CallbackQueryHandler(view_barber_details, pattern="^back_to_info"),
            CallbackQueryHandler(search_barber, pattern="^back_to_search_info$"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
            CallbackQueryHandler(review_next, pattern="^review_next$"),
            CallbackQueryHandler(review_prev, pattern="^review_prev$"),
        ],
        SELECT_SLOT: [
            CallbackQueryHandler(select_slot, pattern="^service_"),
            CallbackQueryHandler(search_barber, pattern="^back_to_search_info$"),
            CallbackQueryHandler(view_barber_details, pattern="back_to_info"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        REQUEST_CONTACT: [
            CallbackQueryHandler(select_slot, pattern="^calendar_(prev|next)_\\d+_\\d+$"),
            CallbackQueryHandler(handle_date_selection, pattern="^date_\\d+_\\d+_\\d+$"),
            CallbackQueryHandler(select_slot, pattern="^back_to_calendar$"),

            CallbackQueryHandler(request_contact, pattern="^slot_[a-zA-Z0-9]+$"),
            
            CallbackQueryHandler(handle_back_to_services, pattern="^back_to_services"),
            CallbackQueryHandler(client_menu, pattern="^back_to_menu$"),
        ],
        CONFIRM_CONTACT: [MessageHandler(filters.CONTACT, confirm_contact)],
        CONFIRM_BOOKING: [
            CallbackQueryHandler(confirm_booking, pattern="^(confirm_booking|cancel_booking)$")
        ],
    },
    fallbacks=[
        CommandHandler("client_menu", client_menu),
        CommandHandler("cancel", client_cancel),
    ],
    allow_reentry=True
)