import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client_side.utils.globals import *
from datetime import datetime
from shared.utils import HelperUtils

class Booking:
    """booking_id is == its document id"""
    """client_id is the client who made the booking"""
    """barber_id is the barber who will be serving the client"""
    
    def __init__(self, booking_id, customer_id, username, barber_email, barber_name, barber_id, 
                 phone_number, start_time, service_id, service_name, service_price, completed=False, no_show=False):
        self.booking_id = booking_id
        self.customer_id = customer_id
        self.username = username
        self.barber_email = barber_email
        self.barber_name = barber_name
        self.barber_id = barber_id  
        self.phone_number = phone_number
        self.start_time = start_time
        self.service_id = service_id
        self.service_name = service_name
        self.service_price = service_price
        self.completed = completed
        self.no_show = no_show
    
    # =========== INSTANCE METHODS =========== #
    # Push to Firestore
    def push_to_db(self, db: firestore.Client):
        """Push the booking details to Firestore."""
        try:
            service_price = float(self.service_price) if self.service_price is not None else 0.0

            booking_ref = db.collection('booked slots').document(self.booking_id)
            booking_ref.set({
                "booked_by": {
                    "customer_id": self.customer_id,
                    "username": self.username,
                    "phone_number": self.phone_number
                },
                "barber_email": self.barber_email,
                "barber_name": self.barber_name,
                "barber_id": self.barber_id,
                "start time": self.start_time,
                "service_id": self.service_id,
                "service_name": self.service_name,
                "service_price": service_price,
                "completed": self.completed,
                "no_show": self.no_show,
            })
            print(f"Booking {self.booking_id} added successfully to Firestore.")
            return True
        except Exception as e:
            print(f"Error adding booking to Firestore: {e}")
            return False
    
    # =========== STATIC METHODS =========== #
    @staticmethod
    def initialize_booking(context):
        """Initialize booking session"""
        context.user_data.clear()
        HelperUtils.set_user_data(context, "conversation_active", True)

    @staticmethod
    def convert_to_sgt(utc_time):
        """Convert UTC time to Singapore Time."""
        return utc_time.replace(tzinfo=pytz.utc).astimezone(timezone)
    
    @staticmethod
    def fetch_service_details(service_id, db: firestore.Client):
        """Fetch the service details (name and price) from Firestore."""
        service_doc = db.collection("services").document(service_id).get()

        if not service_doc.exists:
            return None, None
        service_data = service_doc.to_dict()
        return service_data["name"], service_data["price"]

    @staticmethod
    def fetch_slot_details(slot_id, db: firestore.Client):
        """Fetch the slot details (start and end time) from Firestore."""
        slot_doc = db.collection("open slots").document(slot_id).get()
        if not slot_doc.exists:
            return None
        slot_data = slot_doc.to_dict()
        return slot_data["start time"]

    @staticmethod
    def get_barber_name(barber_email: str, db: firestore.Client):
        """Fetch the barber's name using their email from Firestore."""
        try:
            collection_ref = db.collection('barbers')
            query = collection_ref.where("email", "==", barber_email)
            result = query.stream()
            result_list = list(result)
            data = result_list[0].to_dict()
            barber_name = data.get('name')
            return barber_name
        except Exception as e:
            print(f"Error retrieving barber name: {e}")
            return None

    @staticmethod
    def get_available_barbers(db: firestore.Client):
        """Fetch all available barbers who have open slots."""
        slots_ref = db.collection('open slots').stream()
        barbers = {}
        for slot in slots_ref:
            slot_data = slot.to_dict()
            barber_email = slot_data.get("barber_email")
            if barber_email not in barbers:
                barber_name = Booking.get_barber_name(barber_email, db)
                barbers[barber_email] = barber_name
        return barbers

    @staticmethod
    def get_barber_services(barber_name: str, db: firestore.Client):
        """Fetch all services offered by selected barber."""
        barbers_ref = db.collection('barbers').where("name", "==", barber_name).stream()
        barber_data = next(barbers_ref, None)
        if not barber_data:
            return []
        
        barber_data = barber_data.to_dict()
        service_ids = barber_data.get('services', [])

        services = []
        for service_id in service_ids:
            service_doc = db.collection('services').document(service_id).get()
            if service_doc.exists:
                services.append((service_doc.id, service_doc.to_dict()))

        return services

    @staticmethod
    def get_available_slots(barber_id: str, db: firestore.Client):
        """Fetch all available slots for the selected barber."""
        slots_ref = db.collection('open slots').where("barber_id", "==", barber_id).stream()
        slots = []
        current_time = datetime.now(timezone)  # Get the current time in Singapore Time

        for slot in slots_ref:
            slot_data = slot.to_dict()
            start_time = Booking.convert_to_sgt(slot_data["start time"])
            # Only include slots that are not earlier than the current time
            if start_time >= current_time:
                slots.append((slot.id, start_time))
        
        # Sort the slots by start time
        slots = sorted(slots, key=lambda x: x[1])
        return slots
    
    @staticmethod
    def filter_by_region(barbers: dict, region: str):
        """Filter barbers by the selected region."""
        return {doc_id: barber_info for doc_id, barber_info in barbers.items() if barber_info['region'] == region}

    @staticmethod
    def search_barber_by_name(barber_name: str, db: firestore.Client):
        """Search for a barber by name in Firestore."""
        try:
            barbers_ref = db.collection('barbers').where('name', '==', barber_name).stream()
            barber_data = next(barbers_ref, None)
            if barber_data:
                data = barber_data.to_dict()
                doc_id = barber_data.id  # Use the document ID as the key
                barber_email = data.get('email', "No email available")
                barber_name = data.get('name', "Unknown Barber")
                description_ref = data.get('description_id')
                instagram = data.get('instagram')
                facebook = data.get('facebook')
                website = data.get('website')
                portfolio = data.get('portfolio_link')
                region = data.get('region', "No region available")
                address = data.get('address', "No address available")
                postal = data.get('postal code', "No postal code available")

                # Fetch the description using the id from 'descriptions' collection
                description_text = "No active description available."
                if description_ref:
                    description_doc = description_ref.get()
                    if description_doc.exists:
                        description_text = description_doc.to_dict().get('description', description_text)

                # Return the barber's details as a dictionary
                return {
                    'doc_id': doc_id,
                    'email': barber_email,
                    'name': barber_name,
                    'description': description_text,
                    'instagram': instagram,
                    'facebook': facebook,
                    'website': website,
                    'portfolio_link': portfolio,
                    'region': region,
                    'address': address,
                    'postal': postal
                }
            else:
                return None
        except Exception as e:
            print(f"Error searching for barber: {e}")
            return None
    
    # Function to create a new booking
    @staticmethod
    def create_booking(slot_id, service_ids, user_id, user_name, phone_number, barber_email, barber_name, barber_id, db: firestore.Client):
        """Create a new booking and push it to Firestore"""
        try:
            # Fetch the selected service names and prices from Firestore"
            total_service_price = 0.0
            service_names = []
            service_prices = []

            for sid in service_ids:
                service_name, service_price = Booking.fetch_service_details(sid, db)
                if not service_name:
                    return False, f"This service '{sid}' no longer exists."
                service_names.append(service_name)
                service_prices.append(service_price)
                total_service_price += float(service_price) if service_price is not None else 0.0
            
            service_name_str = ', '.join(service_names)

            # Fetch the selected slot start and end time from Firestore
            start_time = Booking.fetch_slot_details(slot_id, db)
            if not start_time:
                return False, "This slot no longer exists."

            # Create new booking
            booking_id = slot_id # Use the slot_id as the booking_id
            new_booking = Booking(
                booking_id=booking_id,
                customer_id=user_id,
                username=user_name,
                barber_email=barber_email,
                barber_name=barber_name,
                barber_id = barber_id,
                phone_number=phone_number,
                start_time=start_time,
                service_id=service_ids,
                service_name=service_names,
                service_price=total_service_price
            )

            # Push the booking to Firestore
            if new_booking.push_to_db(db):
                # Remove slot from open slots
                # (Ensuring when client books, only available slots will be shown)
                db.collection("open slots").document(slot_id).delete()

                # Convert Firestore stored UTC time to Singapore Time before storing in booked slots
                start_time_sgt = Booking.convert_to_sgt(start_time)

                message = (
                    f"✅ Slot booked successfully!\n\n" 
                    f"💈 <b>Barber:</b> {barber_name}\n" 
                    f"📋 <b>Service(s):</b> {service_name_str}\n" 
                    f"💲 <b>Total Price:</b> ${total_service_price:.2f}\n\n" 
                    f"📅 <b>Date:</b> {start_time_sgt.strftime('%a %d/%m/%Y')}\n" 
                    f"🕛 <b>Time:</b> {start_time_sgt.strftime('%I:%M %p')}\n\n" 
                    f"Thank you, {user_name}! You can view your bookings back at /client_menu"
                )

                return True, message, start_time, service_name_str
                            
            else:
                return False, "Failed to book the slot. Please try again later.", None, None

        except Exception as e:
            print(f"Error creating booking: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def get_booking_info(customer_id: str, db: firestore.Client):
        """Fetch the booking details for the given customer."""
        try:
            # Fetch book slots from Firestore
            booked_slots_ref = db.collection("booked slots").where("booked_by.customer_id", "==", customer_id).stream()

            # Prepare a list to store book slots
            booked_slots = []

            for booking in booked_slots_ref:
                booking_data = booking.to_dict()
                user_info = booking_data["booked_by"]
                start_time = booking_data["start time"]
                barber_email = booking_data["barber_email"]
                barber_name = booking_data["barber_name"]
                service_names = booking_data.get("service_name", [])
                service_name = ', '.join(service_names) if isinstance(service_names, list) else service_names
                service_price = booking_data["service_price"]
                user_name = user_info["username"]
                phone_number = user_info["phone_number"]

                # Get additional details
                barber_ref = db.collection("barbers").where("name", "==", barber_name).stream()

                barber_info = next(barber_ref, None)

                if barber_info:
                    barber_info = barber_info.to_dict()
                    barber_address = barber_info.get("address", "No address available")
                    barber_postal = barber_info.get("postal code", "No postal code available")
                    barber_region = barber_info.get("region", "No region available")

                # Convert times from UTC to Singapore Time
                start_time_sgt = Booking.convert_to_sgt(start_time)

                # Store the formatted slot details in the list
                booked_slots.append(
                    (
                        booking.id, 
                        start_time_sgt, 
                        f"────────────────────\n"
                        f"💈 <b>Barber:</b> {barber_name}\n"
                        f"📍 <b>Location:</b> {barber_address}, {barber_postal}\n"
                        f"🌍 <b>Region:</b> {barber_region}\n\n"
                        f"📋 <b>Services:</b> {service_name}\n"
                        f"💲 <b>Total Price:</b> ${service_price}\n"  
                        f"🕛 <b>Total duration:</b> {start_time_sgt.strftime('%I:%M %p')}" 
                    )
                )

            return booked_slots

        except Exception as e:
            print(f"Error retrieving booked slots: {e}")
            return None
    
    @staticmethod
    def cancel_booking(booking_id: str, user_id: str, db: firestore.Client):
        """Cancel a booking and re-add the slot back to 'open slots'."""
        try:
            # Fetch the booked slot from the "booked slots" collection
            booked_slot_ref = db.collection("booked slots").document(booking_id).get()

            if not booked_slot_ref.exists:
                return False, "This booking no longer exists."
            
            booked_slot_data = booked_slot_ref.to_dict()
            start_time = booked_slot_data['start time']
            barber_email = booked_slot_data["barber_email"]
            
            # Ensure that the user is the one who made the booking (extra checks)
            if booked_slot_data['booked_by']['customer_id'] != user_id:
                return False, "You cannot cancel someone else's booking."
            
            # Remove the slot from "booked slots"
            db.collection("booked slots").document(booking_id).delete()

            # Re-add the slot back to "open slots"
            db.collection("open slots").document(booking_id).set({
                "start time": start_time,
                "barber_email": barber_email,
            })

            print(f"Booking {booking_id} canceled successfully.")
            return True, "Your booking has been successfully canceled. Press /client_menu to go back to menu."

        except Exception as e:
            print(f"Error canceling booking: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def get_completed_bookings(customer_id: str, db: firestore.Client):
        """Fetch the completed booking for the given customer."""
        try:
            # Fetch book slots from Firestore
            booked_slots_ref = db.collection("booked slots").where("booked_by.customer_id", "==", customer_id).where("completed", "==", True).stream()

            # Prepare a list to store book slots
            completed_bookings = []

            for booking in booked_slots_ref:
                booking_data = booking.to_dict()
                start_time = booking_data["start time"]

                # Get barber info by UUID
                barber_id = booking_data.get("barber_id")
                barber_address = "No address available"
                barber_postal = "No postal code available"
                barber_region = "No region available"
                barber_name = "Unknown Barber"

                if barber_id:
                    barber_doc = db.collection("barbers").document(barber_id).get()
                    if barber_doc.exists:
                        barber_info = barber_doc.to_dict()
                        barber_name = barber_info.get("name", barber_name)
                        barber_address = barber_info.get("address", barber_address)
                        barber_postal = barber_info.get("postal code", barber_postal)
                        barber_region = barber_info.get("region", barber_region)

                service_names = booking_data.get("service_name", [])
                service_name = ', '.join(service_names) if isinstance(service_names, list) else service_names
                service_price = booking_data["service_price"]
                rating = booking_data.get("rating", "No rating yet")
                review = booking_data.get("review", "No review yet")

                # Convert times from UTC to Singapore Time
                start_time_sgt = Booking.convert_to_sgt(start_time)

                # Store the formatted slot details in the list
                completed_bookings.append(
                    (
                        booking.id, 
                        start_time_sgt, 
                        f"─────────────\n"
                        f"💈{barber_name}\n"
                        f"📍{barber_address}, {barber_postal}\n"
                        f"🌍{barber_region}\n\n"
                        f"📋{service_name}\n"
                        f"💲${service_price}\n"  
                        f"⏰{start_time_sgt.strftime('%I:%M %p')}",
                        rating,
                        review
                    )
                )

            return completed_bookings

        except Exception as e:
            print(f"Error retrieving booked slots: {e}")
            return None
    
    @staticmethod
    def get_no_show_bookings(customer_id: str, db: firestore.Client):
        """Fetch the no-show booking for the given customer."""
        try:
            # Fetch book slots from Firestore
            booked_slots_ref = db.collection("booked slots").where("booked_by.customer_id", "==", customer_id).where("no_show", "==", True).stream()

            # Prepare a list to store book slots
            no_show_bookings = []

            for booking in booked_slots_ref:
                booking_data = booking.to_dict()
                start_time = booking_data["start time"]

                # Get barber info by UUID
                barber_id = booking_data.get("barber_id")
                barber_address = "No address available"
                barber_postal = "No postal code available"
                barber_region = "No region available"
                barber_name = "Unknown Barber"

                if barber_id:
                    barber_doc = db.collection("barbers").document(barber_id).get()
                    if barber_doc.exists:
                        barber_info = barber_doc.to_dict()
                        barber_name = barber_info.get("name", barber_name)
                        barber_address = barber_info.get("address", barber_address)
                        barber_postal = barber_info.get("postal code", barber_postal)
                        barber_region = barber_info.get("region", barber_region)

                service_names = booking_data.get("service_name", [])
                service_name = ', '.join(service_names) if isinstance(service_names, list) else service_names

                # Convert times from UTC to Singapore Time
                start_time_sgt = Booking.convert_to_sgt(start_time)

                # Store the formatted slot details in the list
                no_show_bookings.append(
                    (
                        booking.id, 
                        start_time_sgt, 
                        f"─────────────\n"
                        f"💈{barber_name}\n"
                        f"📍{barber_address}, {barber_postal}\n"
                        f"🌍{barber_region}\n\n"
                        f"📋{service_name}\n"  
                    )
                )
            return no_show_bookings
        except Exception as e:
            print(f"Error retrieving booked slots: {e}")
            return None

    @staticmethod
    def get_upcoming_bookings(customer_id: str, db: firestore.Client):
        """Fetch the upcoming booking for the given customer."""
        try:
            now = datetime.now(timezone)

            booked_slots_ref = db.collection("booked slots")\
                .where("booked_by.customer_id", "==", customer_id)\
                .where("completed", "==", False)\
                .where("no_show", "==", False)\
                .stream()

            upcoming_bookings = []

            for booking in booked_slots_ref:
                booking_data = booking.to_dict()
                user_info = booking_data["booked_by"]
                start_time = booking_data["start time"]

                if start_time < now:
                    continue

                # Get barber info by UUID 
                barber_id = booking_data.get("barber_id")
                barber_address = "No address available"
                barber_postal = "No postal code available"
                barber_region = "No region available"
                barber_name = "Unknown Barber"

                if barber_id:
                    barber_doc = db.collection("barbers").document(barber_id).get()
                    if barber_doc.exists:
                        barber_info = barber_doc.to_dict()
                        barber_name = barber_info.get("name", barber_name)
                        barber_address = barber_info.get("address", barber_address)
                        barber_postal = barber_info.get("postal code", barber_postal)
                        barber_region = barber_info.get("region", barber_region)

                service_names = booking_data.get("service_name", [])
                service_name = ', '.join(service_names) if isinstance(service_names, list) else service_names
                service_price = booking_data["service_price"]

                # Convert times from UTC to Singapore Time
                start_time_sgt = Booking.convert_to_sgt(start_time)

                # Store the formatted slot details in the list
                upcoming_bookings.append(
                    (
                        booking.id, 
                        start_time_sgt, 
                        f"─────────────\n"
                        f"💈{barber_name}\n"
                        f"📍{barber_address}, {barber_postal}\n"
                        f"🌍{barber_region}\n\n"
                        f"📋{service_name}\n"
                        f"💲${service_price}\n"  
                        f"🕛{start_time_sgt.strftime('%I:%M %p')}" 
                    )
                )

            return upcoming_bookings
        except Exception as e:
            print(f"Error retrieving booked slots: {e}")
            return []
    
    @staticmethod
    def save_rating(booking_id: str, rating: int, reviewer_name: str, db: firestore.Client):
        """Save the rating for a completed booking."""
        try:
            # Update the booking document with the rating
            db.collection("booked slots").document(booking_id).update({
                "rating": rating
            })
            print(f"Rating {rating} saved successfully for booking {booking_id}.")

            # Fetch barber ID for this booking
            booking_doc = db.collection("booked slots").document(booking_id).get()
            if not booking_doc.exists:
                return False, "Booking not found."

            booking_data = booking_doc.to_dict()
            barber_id = booking_data.get("barber_id")

            if not barber_id:
                return False, "Barber ID not found for this booking."
            
            # Save rating in ratings and reviews collection
            db.collection("barbers").document(barber_id).collection("ratings and reviews").document(booking_id).set({
                "booking_id": booking_id,
                "rating": rating,
                "reviewer_name": reviewer_name,
                "timestamp": datetime.now(timezone)
            }, merge=True)

            return True, "Thank you for your rating ⭐!"
        except Exception as e:
            print(f"Error saving rating: {e}")
            return False, f"Error: {str(e)}"
        
    @staticmethod
    def save_review(booking_id: str, review: str, reviewer_name: str, db: firestore.Client):
        """Save the review for a completed booking."""
        try:
            # Update the booking document with the review
            db.collection("booked slots").document(booking_id).update({
                "review": review
            })
            print(f"Review saved successfully for booking {booking_id}.")

            # Fetch barber ID for this booking
            booking_doc = db.collection("booked slots").document(booking_id).get()
            if not booking_doc.exists:
                return False, "Booking not found."

            booking_data = booking_doc.to_dict()
            barber_id = booking_data.get("barber_id")

            if not barber_id:
                return False, "Barber ID not found for this booking."

            # Save review in ratings and reviews collection
            db.collection("barbers").document(barber_id).collection("ratings and reviews").document(booking_id).set({
                "booking_id": booking_id,
                "review": review,
                "reviewer_name": reviewer_name,
                "timestamp": datetime.now(timezone)
            }, merge=True)

            return True, "Thank you for your review! Your feedback is valuable to us."
        except Exception as e:
            print(f"Error saving review: {e}")
            return False, f"Error: {str(e)}"
    
