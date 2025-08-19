from telegram import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from datetime import datetime, timedelta
from utils.globals import *

class Keyboards:
    """
    Centralized keyboard generator class to streamline Telegram bot interface creation.
    
    Purpose:
    - Eliminates duplicate keyboard code across different handlers
    - Provides consistent button layouts throughout the bot
    - Makes maintenance easier (changes only need to be made in one place)
    
    Usage:
    - Import this class in any handler file
    - Call the appropriate static method to get pre-formatted keyboards
    
    Benefits:
    1. Single Source of Truth - All keyboard layouts are defined here
    2. DRY Principle - No repeated keyboard code in handlers
    3. Easy Modifications - Change a keyboard once and it updates everywhere
    4. Consistent UX - Standardized button labels and emoji usage

    """

    # =============== BOOKING, VIEW BARBER, SEARCHING =============== #
    @staticmethod
    def search_options():
        """Buttons for search options."""
        maps_url = "https://absqueuebot.web.app"
        print(f"MapUrl: {maps_url}")

        return [
            [InlineKeyboardButton("⭐ Top Rated", callback_data="search_by_rating"),
            InlineKeyboardButton("❤️ Favorites", callback_data="search_by_favorites")],
            [InlineKeyboardButton("🌍 Regions", callback_data="search_by_region"),
            InlineKeyboardButton("📍 Barbers near me", callback_data="search_by_location")],
            [InlineKeyboardButton("🔍 Search by name", callback_data="search_by_name"),
            InlineKeyboardButton("🗺 View Barbers on a Map", url=maps_url)]
        ]
    
    @staticmethod
    def search_by_location():
        """Keyboard for sharing location."""
        return ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Share Location", request_location=True)]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    
    @staticmethod
    def search_by_region():
        """Buttons for selecting a region."""
        return [
            [InlineKeyboardButton("🌍 North", callback_data="region_north")],
            [InlineKeyboardButton("🌍 South", callback_data="region_south")],
            [InlineKeyboardButton("🌍 East", callback_data="region_east")],
            [InlineKeyboardButton("🌍 West", callback_data="region_west")],
            [InlineKeyboardButton("🌍 North East", callback_data="region_northeast")],
            [InlineKeyboardButton("🌍 Central", callback_data="region_central")],
            [InlineKeyboardButton("◀", callback_data="back_to_search_option"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
        ]
    
    @staticmethod
    def select_barber_keyboard(barbers_page, start_index, end_index, total_items, page, search_type):
        """Generate the keyboard for selecting barbers."""
        keyboard = []

        if search_type == "region":
            # Add a button to filter by location if in region search
            keyboard.append([InlineKeyboardButton("📍 Filter by Location", callback_data="filter_by_location")])

        # Barber buttons with distance at the side
        for doc_id, barber_info in barbers_page:
            btn_text = f"💈 {barber_info['name']}"

            # Add distance if available
            if search_type == "location" or 'distance_km' in barber_info:
                btn_text += f" ({barber_info['distance_km']}km)"
            
            # Add rating if available
            if search_type == "rating" or 'avg_rating' in barber_info:
                rating = barber_info.get('avg_rating', None)
                if rating is not None:
                    try:
                        rating = float(rating)
                        btn_text += f" (⭐ {rating:.1f})"
                    except ValueError:
                        btn_text += " (⭐ N/A)"
                else:
                    btn_text += " (⭐ N/A)"

            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"barber_{doc_id}")])

        # Add pagination buttons
        navigation_buttons = []
        if start_index > 0:
            navigation_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
        if end_index < total_items:
            navigation_buttons.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
        keyboard.append(navigation_buttons)

        # Add the appropriate "Back" button based on the search type
        if search_type != "region":
            keyboard.append([InlineKeyboardButton("◀", callback_data="back_to_search_option"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])
        else:
            keyboard.append([InlineKeyboardButton("◀", callback_data="back_to_region"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])

        return keyboard

    @staticmethod
    def barber_details(doc_id, is_following=False, search_type=None):
        """Buttons for barber details section."""
        follow_button_text = "⭐ Favorited" if is_following else "➕ Favorite this barber to get notified"
        follow_button_callback = f"unfollow_{doc_id}" if is_following else f"follow_{doc_id}"

        return [
            [InlineKeyboardButton("📋 View Services", callback_data=f"select_services_{doc_id}")],
            [InlineKeyboardButton("ℹ️ Learn more", callback_data=f"learn_more_{doc_id}")],
            [InlineKeyboardButton("💬 Ratings & Reviews", callback_data=f"view_ratings_reviews_{doc_id}")],
            [InlineKeyboardButton(follow_button_text, callback_data=follow_button_callback)],
            [InlineKeyboardButton("◀", callback_data="back_to_barbers"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
        ]
    
    @staticmethod
    def service_keyboard(barber_doc_id: str, search_type):
        """Buttons for select services section."""
        if search_type == "name":
            return [
                [InlineKeyboardButton("◀", callback_data=f"back_to_search_info"), 
                 InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
            ]
        elif search_type == "location":
            return [
                [InlineKeyboardButton("◀", callback_data="back_to_info"), 
                 InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],    
            ]
        else:
            return [
                [InlineKeyboardButton("◀", callback_data=f"back_to_info"), 
                 InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")],
            ]
    
    @staticmethod
    def learn_more_keyboard(barber_info, barber_doc_id: str, search_type):
        """Buttons for learning more section."""
        keyboard = []

        def is_valid_url(url):
            # Check for http/https and common domain endings
            valid_domains = (".com", ".net", ".org", ".sg", ".co", ".io", ".edu", ".gov")
            return (
                isinstance(url, str)
                and any(url.endswith(domain) for domain in valid_domains)
            )

        def format_url(url):
            if not url.startswith(("http://", "https://")):
                return f"https://{url}"
            return url

        if barber_info:
            if barber_info.get('instagram'): 
                keyboard.append([InlineKeyboardButton("📷 Instagram", url=f"https://www.instagram.com/{barber_info['instagram']}/")])
            if barber_info.get('facebook'):
                keyboard.append([InlineKeyboardButton("📘 Facebook", url=f"https://www.facebook.com/{barber_info['facebook']}/")])
            if barber_info.get('website') and is_valid_url(barber_info['website']):
                keyboard.append([InlineKeyboardButton("🌐 Website", url=format_url(barber_info['website']))])
            if barber_info.get('portfolio_link') and is_valid_url(barber_info['portfolio_link']):
                keyboard.append([InlineKeyboardButton("📂 Portfolio", url=format_url(barber_info['portfolio_link']))])
                
            
        if search_type == "name":
            keyboard.append([InlineKeyboardButton("◀", callback_data=f"back_to_search_info"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])
        elif search_type == "location":
            keyboard.append([InlineKeyboardButton("◀", callback_data="back_to_info"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])
        else:
            keyboard.append([InlineKeyboardButton("◀", callback_data=f"back_to_info"), InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")])
        
        return keyboard
    
    @staticmethod
    def generate_calendar(year, month, slots_by_date):
        """Generate a calendar keyboard with available dates highlighted."""
        keyboard = []
        
        # Month names with fixed width (using non-breaking spaces)
        month_names = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 
            5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
            9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }

        # Header row with month and navigation
        month_header = f"{month_names[month]} {year}"
        header = [
            InlineKeyboardButton("«", callback_data=f"calendar_prev_{year}_{month:02d}"),  # Use :02d to pad the month
            InlineKeyboardButton(month_header, callback_data="ignore"),
            InlineKeyboardButton("»", callback_data=f"calendar_next_{year}_{month:02d}")  # Use :02d here too
        ]
        keyboard.append(header)

        # Add weekday headers
        weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        keyboard.append([
            InlineKeyboardButton(day, callback_data="ignore") for day in weekdays
        ])
        
        # Get first day of month and prepare calendar
        first_day = datetime(year, month, 1)
        starting_weekday = (first_day.weekday()) % 7  # Monday is 0
        days_in_month = (datetime(year, month + 1, 1) - timedelta(days=1)).day
        
        # Generate calendar rows
        day = 1
        for week in range(6):  # Max 6 weeks in a month
            if day > days_in_month:
                break
                
            week_row = []
            for weekday in range(7):
                if (week == 0 and weekday < starting_weekday) or day > days_in_month:
                    week_row.append(InlineKeyboardButton("   ", callback_data="ignore"))
                else:
                    current_date = datetime(year, month, day).date()
                    button_text = f"{day:2d}"  # Fixed width day number
                    
                    if current_date in slots_by_date:
                        # If there are booked slots but no completed slots, indicate booked
                        if slots_by_date[current_date]['booked']:
                            button_text = f"{day:2d}🔵"  # Booked slots

                        # If there are completed slots, indicate that
                        elif slots_by_date[current_date]['completed']:
                            button_text = f"{day:2d}✅"  # Completed slots
                        
                        # If there are no show slots, indicate no show
                        elif slots_by_date[current_date]['no_show']:
                            button_text = f"{day:2d}❌"  # No show slots

                        # If there are available slots, indicate available
                        elif slots_by_date[current_date]['available']:
                            button_text = f"{day:2d}🟢"
                    
                    # Ensure consistent width by padding if needed
                    if len(button_text) < 4:
                        button_text = button_text.ljust(4)
                    
                    week_row.append(
                        InlineKeyboardButton(
                            button_text,
                            callback_data=f"date_{year}_{month:02d}_{day:02d}"
                        )
                    )
                    day += 1
            keyboard.append(week_row)
        
        return keyboard
    
    @staticmethod
    def contact_keyboard():
        """Keyboard for sharing contact."""
        return ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Share Contact", request_contact=True)]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    
    @staticmethod
    def confirm_booking_keyboard():
        """Buttons for confirming booking."""
        return [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_booking")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_booking")],
        ]
    
    @staticmethod
    def home_button():
        """Button to return to the home menu."""
        return [InlineKeyboardButton("🏠 Home", callback_data="back_to_menu")]
        