import sys
import os
from datetime import datetime
import pytz

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.globals import timezone  # Make sure your timezone is defined in globals
from shared.utils import HelperUtils
from firebase_admin import firestore

class Booking:
    """Represents a single booking in the system."""

    def __init__(self, booking_id, customer_id, username, barber_email, barber_name,
                 phone_number, start_time, end_time, service_id, service_name, service_price,
                 completed=False, no_show=False):
        self.booking_id = booking_id
        self.customer_id = customer_id
        self.username = username
        self.barber_email = barber_email
        self.barber_name = barber_name
        self.phone_number = phone_number
        self.start_time = start_time
        self.end_time = end_time
        self.service_id = service_id
        self.service_name = service_name
        self.service_price = service_price
        self.completed = completed
        self.no_show = no_show

    # =========== INSTANCE METHODS =========== #

    def push_to_db(self, db: firestore.Client):
        """Push the booking details to Firestore."""
        try:
            booking_ref = db.collection('booked slots').document(self.booking_id)
            booking_ref.set({
                "booked_by": {
                    "customer_id": self.customer_id,
                    "username": self.username,
                    "phone_number": self.phone_number
                },
                "barber_email": self.barber_email,
                "barber_name": self.barber_name,
                "start time": self.start_time,
                "end time": self.end_time,
                "service_id": self.service_id,
                "service_name": self.service_name,
                "service_price": self.service_price,
                "completed": self.completed,
            })
            print(f"Booking {self.booking_id} added successfully to Firestore.")
            return True
        except Exception as e:
            print(f"Error adding booking to Firestore: {e}")
            return False

    # =========== STATIC METHODS =========== #

    @staticmethod
    def convert_to_sgt(utc_time):
        """Convert UTC time to Singapore Time."""
        return utc_time.replace(tzinfo=pytz.utc).astimezone(timezone)

    @staticmethod
    def fetch_slot_details(slot_id, db: firestore.Client):
        """Fetch the slot start and end times from Firestore."""
        slot_doc = db.collection("open slots").document(slot_id).get()
        if not slot_doc.exists:
            return None, None
        slot_data = slot_doc.to_dict()
        return slot_data.get("start time"), slot_data.get("end time")

    @staticmethod
    def get_completed_bookings(barber_email: str, db: firestore.Client):
        """
        Fetch completed bookings for the barber using their email.

        Returns a list of tuples:
        (booking_id, start_time_sgt, formatted_summary)
        """
        try:
            query = db.collection("booked slots") \
                .where("barber_email", "==", barber_email) \
                .where("completed", "==", True) \
                .stream()

            completed_bookings = []

            for booking in query:
                booking_data = booking.to_dict()
                booked_by = booking_data.get("booked_by", {})

                start_time = booking_data.get("start time")
                end_time = booking_data.get("end time")
                barber_name = booking_data.get("barber_name", "Unknown Barber")
                service_name = booking_data.get("service_name", "Unknown Service")
                service_price = booking_data.get("service_price", "N/A")

                # Get barber's address & region for the booking summary
                barber_ref = db.collection("barbers").where("name", "==", barber_name).stream()
                barber_info_doc = next(barber_ref, None)

                if barber_info_doc:
                    barber_info = barber_info_doc.to_dict()
                    barber_address = barber_info.get("address", "No address available")
                    barber_postal = barber_info.get("postal code", "No postal code available")
                    barber_region = barber_info.get("region", "No region available")
                else:
                    barber_address = "No address available"
                    barber_postal = "No postal code available"
                    barber_region = "No region available"

                start_time_sgt = Booking.convert_to_sgt(start_time) if start_time else "Unknown Time"
                end_time_sgt = Booking.convert_to_sgt(end_time) if end_time else "Unknown Time"

                completed_bookings.append(
                    (
                        booking.id,
                        start_time_sgt,
                        f"────────────────────\n"
                        f"💈 <b>Barber:</b> {barber_name}\n"
                        f"📍 <b>Location:</b> {barber_address}, {barber_postal}\n"
                        f"🌍 <b>Region:</b> {barber_region}\n\n"
                        f"📋 <b>Service:</b> {service_name}\n"
                        f"💲 <b>Price:</b> ${service_price}\n"
                        f"⏰ <b>Total duration:</b> "
                        f"{start_time_sgt.strftime('%I:%M %p') if start_time_sgt != 'Unknown Time' else 'N/A'} - "
                        f"{end_time_sgt.strftime('%I:%M %p') if end_time_sgt != 'Unknown Time' else 'N/A'}"
                    )
                )

            return completed_bookings

        except Exception as e:
            print(f"Error retrieving completed bookings for barber: {e}")
            return None
