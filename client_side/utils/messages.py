

class Messages:
    """
    Centralized message generator class for consistent bot communication.
    
    Purpose:
    - Provides pre-formatted message templates for all bot responses
    - Ensures consistent formatting and emoji usage across the application
    
    Usage:
    - Call the appropriate static method with required parameters
    - Methods return formatted strings ready for sending via Telegram
    
    Benefits:
    1. Single Source of Truth - All user messages are defined here
    2. Maintainability - Message updates only need to be made in one place
    
    """

    # =============== BOOKING, VIEW BARBER, SEARCHING =============== #
    @staticmethod
    def header_message(context: str, details: dict = None) -> str:
        """Generate header messages for different contexts."""
        details = details or {}

        headers = {
            "search_option": "Select your preferred way to find barbers💈",
            "search_by_location": (
                "📍 Please share your location to find barbers near you.\n"
            ),
            "select_region": "Select your preferred region 👇",
            "select_service": "Select a service offered by <b>{barber_name}</b>:",
            "select_slot": "📅 Please choose a date (🟢 = Available)",
            "select_barber": (
                "❤️ Your favorite barbers 👇" if details.get("is_favorites")
                else "Barbers near you 👇" if details.get("is_location_search")
                else "⭐ Top rated barbers 👇" if details.get("is_top_rated")
                else f"Available barbers in <b>{details.get('region', 'Unknown')}</b>👇" 
            ),
            "share_contact": "📱 Please share your contact number so the barber can contact you.",
            "contact_received": "✅ Contact received! Proceeding to booking confirmation...",
            "confirm_booking": (
                "📅 You are about to book an appointment.\n"
                "Are you sure you want to proceed?"
            ),
        }

        # Get the base message for the context
        message = headers.get(context, "⚠️ Invalid context provided.")

        # Format the message with details if applicable
        if details:
            message = message.format(**details)

        return message
    
    @staticmethod
    def barber_details(barber_info):
        """ Generate the barber details message. """
        return (
            f"💈 <b>{barber_info['name']}</b>\n"
            f"📝 {barber_info['description']}\n"
            f"────────────────────\n"
            f"📍 {barber_info['address']}\n"
            f"📮 {barber_info['postal']}\n"
            f"🌍 {barber_info['region']}"
        )
    
    @staticmethod
    def learn_more_message(barber_info: dict) -> str:
        """Generate the 'Learn more' message for a barber."""
        message = f"🔗 Learn more about barber <b>{barber_info['name']}</b>\n\n"

        return message
    
    
    # ================ GENERAL ERROR MESSAGES ================ #
    @staticmethod
    def error_message(context: str, additional_info: str = None) -> str:
        """Generate error messages based on the context."""
        messages = {
            "no_barbers_found": "🙁 No barbers found in the selected region.\n\nPlease try selecting a different region.",
            "no_location_barbers": "🙁 <b>No barbers found near your current location.</b>",
            "no_services": "🙁 No services available for this barber at the moment.",
            "no_slots": "🙁 No available slots at the moment. Please check back later.",
            "barber_not_found": "🙁 Barber not found. Please try again.",
            "generic_error": "⚠️ Oops! Something went wrong. Please try again later.",
        }

        # Get the base message for the context
        message = messages.get(context, messages["generic_error"])

        # Append additional information if provided
        if additional_info:
            message += f"\n\n{additional_info}"

        return message
    
    # ================ CANCEL OPERATION MESSAGE ================ #
    @staticmethod
    def cancel_operation_message() -> str:
        """Message to inform the user that the operation has been canceled."""
        return "❌ Client operation canceled. Please select an option from /client_menu. Or select /start to restart the bot."