import sys
import os

# Add the parent directory of barber_side to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client_side.utils.globals import *

# others
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
import requests

class Customer:
    def __init__(self, id, name, email, phone_number):
        self.id = id
        self.name = name
        self.email = email
        self.phone_number = phone_number

    # Setters
    def set_name(self, name: str):
        self.name = name

    def set_email(self, email: str):
        self.email = email

    def set_phone_number(self, phone_number: str):
        self.phone_number = phone_number

    # Push to Firestore
    def push_to_db(self, db: firestore.Client):
        try:
            client_ref = db.collection('customers').document(self.id)
            client_ref.set({
                "name": self.name,
                "email": self.email,
                "phone_number": self.phone_number
            })
            print(f"Client {self.name} (ID: {self.id}) added successfully to Firestore.")
            return True
        except Exception as e:
            print(f"Error adding client to Firestore: {e}")
            return False

    @staticmethod
    def get_customer_info(email: str, db: firestore.Client):
        try:
            collection_ref = db.collection('clients')
            query = collection_ref.where("email", "==", email)
            result = query.stream()
            result_list = list(result)
            data = result_list[0].to_dict()
            client_name = data.get('name')
            return client_name
        except Exception as e:
            print(f"Error retrieving client name: {e}")
            return None
    
    @staticmethod
    def get_nearby_barbers(db, user_location, api_key, radius_km=3):
        """Fetch barbers near the user's location within a given radius."""
        user_lat = user_location["latitude"]
        user_lon = user_location["longitude"]

        # Fetch all barbers from the database
        barbers = Customer.get_all_barbers(db)

        # Geocode barbers' addresses to get their coordinates
        barbers_with_coordinates = Customer.update_barber_coordinates(barbers, api_key)

        barber_distances = []

        for barber_id, barber_info in barbers_with_coordinates.items():
            barber_lat = barber_info.get("latitude")
            barber_lon = barber_info.get("longitude")

            if barber_lat is None or barber_lon is None:
                continue  # Skip barbers without latitude/longitude

            # barber_lat = radians(barber_lat)
            # barber_lon = radians(barber_lon)

            # Calculate the distance using the Haversine formula
            # dlat = barber_lat - user_lat
            # dlon = barber_lon - user_lon
            # a = sin(dlat / 2)**2 + cos(user_lat) * cos(barber_lat) * sin(dlon / 2)**2
            # c = 2 * atan2(sqrt(a), sqrt(1 - a))
            # distance_km = 6371 * c  # Radius of Earth in kilometers

            distance_km = Customer.calculate_distance(user_lat, user_lon, barber_lat, barber_lon)

            if distance_km <= radius_km:
                barber_distances.append((distance_km, barber_id, barber_info))

        # Sort by distance and create ordered dictionary
        barber_distances.sort(key=lambda x: x[0])

        return {
            barber_id: {
                **barber_info,
                "distance_km": round(distance, 2),
                "latitude": barber_info.get("latitude"),  # Include latitude
                "longitude": barber_info.get("longitude"),  # Include longitude
            }
            for distance, barber_id, barber_info in barber_distances
        }
    
    @staticmethod
    def get_barbers_location(db, api_key):
        """Fetch barbers location."""
        # Fetch all barbers from the database
        barbers = Customer.get_all_barbers(db)

        # Geocode barbers' addresses to get their coordinates
        barbers_with_coordinates = Customer.update_barber_coordinates(barbers, api_key)

        # Extract only the location information
        barber_locations = {
            barber_id: {
                "latitude": barber_info.get("latitude"),
                "longitude": barber_info.get("longitude")
            }
            for barber_id, barber_info in barbers_with_coordinates.items()
            if barber_info.get("latitude") is not None and barber_info.get("longitude") is not None
        }

        return barber_locations
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ Location Functions ~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate the distance between two geographical points using Haversine formula."""
        R = 6371
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a)) 
        distance = R * c
        return distance

    @staticmethod
    def geocode_address(address: str, api_key: str):
        """Convert an address into latitude and longitude using Google Maps API."""
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "OK":
                location = data["results"][0]["geometry"]["location"]
                return location["lat"], location["lng"]
            else:
                return None, None
        else:
            print(f"HTTP error: {response.status_code}")
            return None, None
    
    @staticmethod
    def update_barber_coordinates(barbers, api_key):
        """Geocode all barbers' addresses and update their coordinates"""
        barbers_with_coordinates = {}

        for barber_id, barber_info in barbers.items():
            address = barber_info["address"]
            lat, lng = Customer.geocode_address(address, api_key)
            if lat is not None and lng is not None:
                barbers_with_coordinates[barber_id] = {
                    "name": barber_info["name"],
                    "email": barber_info["email"],
                    "address": barber_info["address"],
                    "postal": barber_info["postal"],
                    "latitude": lat,
                    "longitude": lng,
                }
            else:
                print(f"Failed to geocode address for barber {barber_info['name']}: {address}")

        return barbers_with_coordinates
    
    @staticmethod
    def is_user_following(db, barber_id, user_id):
        """Check if user is following a barber."""
        user_id = str(user_id) # Ensure user_id is a string
        doc_ref = db.collection('followers').document(barber_id).collection('users').document(user_id)
        doc = doc_ref.get()
        return doc.exists
    
    @staticmethod
    def follow_barber(db, barber_id, username, user_id):
        """Add user to barber's followers."""
        print(f"Attempting to follow barber: barber_id={barber_id}, username={username}, user_id={user_id}")
        
        user_id = str(user_id) # Ensure user_id is a string

        barber_ref = db.collection('barbers').document(barber_id)
        barber_doc = barber_ref.get()
        
        if not barber_doc.exists:
            raise ValueError("Barber not found")
        
        barber_data = barber_doc.to_dict()
        barber_name = barber_data.get('name', 'Unknown Barber')  # Default if name not found
        
        # Reference to the barber's document in followers collection
        barber_follower_ref = db.collection('followers').document(barber_id)
        # Update or create the barber's document with their name
        barber_follower_ref.set({
            'name': barber_name,
            'barber_id': barber_id,
        }, merge=True)

        # Create the user's follow document in the subcollection
        user_follow_ref = barber_follower_ref.collection('users').document(user_id)
        user_follow_ref.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'username': username,
            'user_id': user_id,
        })

    @staticmethod
    def unfollow_barber(db, barber_id, user_id):
        """Remove user from barber's followers."""
        user_id = str(user_id) # Ensure user_id is a string

        doc_ref = db.collection('followers').document(barber_id).collection('users').document(user_id)
        doc_ref.delete()
    
    @staticmethod
    def get_followed_barbers(db, user_id):
        """Get all barbers followed by the user."""
        user_id = str(user_id)
        followers_ref = db.collection('followers')
        followed_barbers = {}

        # Get all documents in the followers collection
        barbers_docs = followers_ref.stream()

        for barber_doc in barbers_docs:
            # Check if user exists in this barber's followers subcollection
            user_ref = barber_doc.reference.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                # Get barber details
                barber_data = barber_doc.to_dict()
                followed_barbers[barber_doc.id] = {
                    'name': barber_data.get('name', 'Unknown Barber'),
                }
        
        return followed_barbers

    @staticmethod
    def get_all_barbers(db: firestore.Client):
        """Fetch all barbers from Firestore. Return a dictionary of barbers."""
        try:
            query = db.collection('barbers').stream()
            barbers = {}

            for doc in query:
                data = doc.to_dict()
                doc_id = doc.id
                barber_email = data.get('email', "No email available")
                barber_name = data.get('name', "Unknown Barber")
                description_ref = data.get('description_id')
                ig_link = data.get('ig_link')
                tiktok_link = data.get('tiktok_link')
                region = data.get('region', "No region available")
                address = data.get('address', "No address available")
                postal = data.get('postal code', "No postal code available")

                # Fetch the description if exists
                description_text = "No active description available."
                if description_ref:
                    description_doc = description_ref.get()
                    if description_doc.exists:
                        description_text = description_doc.to_dict().get('description', description_text)

                barbers[doc_id] = {
                    'email': barber_email,
                    'name': barber_name,
                    'description': description_text,
                    'ig_link': ig_link,
                    'tiktok_link': tiktok_link,
                    'region': region,
                    'address': address,
                    'postal': postal
                }

            return barbers

        except Exception as e:
            print(f"❌ Error retrieving barbers: {e}")
            return None