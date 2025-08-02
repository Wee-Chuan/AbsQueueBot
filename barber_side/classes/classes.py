from datetime import datetime
from firebase_admin import firestore
import re
from barber_side.utils.globals import *
import asyncio

class Barber:
    def __init__(self, name, email, address, postal, region, doc_id=None, desc_id=None, portfolio=None, services=None, notify = False, uuid = None):
        self.name = name
        self.email = email
        self.address = address
        self.postal = postal
        self.region = region
        self.desc_id = desc_id
        self.doc_id = doc_id  # Firestore document ID, immutable.
        self.services = services if services else []  # Default empty list if none provided.
        self.notify = notify
        self.portfolio = portfolio
        self.uuid = uuid

    def push_to_db(self, db: firestore.Client):
        """
        Update the existing Firestore barber document.
        """
        if self.doc_id is None:
            print("❌ Cannot update barber profile: doc_id is None.")
            return False

        try:
            barber_data = {
                "name": self.name,
                "email": self.email,
                "address": self.address,
                "postal": self.postal,
                "region": self.region,
                "services": self.services,
                "notify": self.notify,
                "portfolio": self.portfolio,
                "description_id": self.desc_id,
                "uuid": self.uuid
            }
            barber_ref = db.collection('barbers').document(self.doc_id)
            barber_ref.update(barber_data)
            print(f"✅ Updated barber '{self.name}' (ID: {self.doc_id}) successfully in Firestore.")
            return True

        except Exception as e:
            print(f"❌ Error updating Firestore: {e}")
            return False

    def add_to_db_with_auth(self, db: firestore.Client, password: str):
        """
        Create Firebase Authentication user with email/password,
        then add the barber profile to Firestore using the Firebase UID as doc_id.
        """
        try:
            # Create Firebase Auth user
            user_record = auth.create_user(
                email=self.email,
                password=password
            )
            self.doc_id = user_record.uid  # Use Firebase UID as Firestore doc ID # importanttttt

            barber_data = {
                "name": self.name,
                "email": self.email,
                "address": self.address,
                "postal": self.postal,
                "region": self.region,
                "services": self.services,
                "notify": self.notify,
                "portfolio": self.portfolio,
                "description_id": self.desc_id,
                "uuid":user_record.uid
            }

            # Add document with the Firebase UID as the doc_id to 'barbers'
            db.collection('barbers').document(self.doc_id).set(barber_data)
            
            # add document to 'followers'
            follower_document = {
                "name" : self.name
            }
            db.collection('followers').document(self.doc_id).set(follower_document)
            
            print(f"✅ Created Firebase Auth user and Firestore profile for '{self.name}' (UID: {self.doc_id})")
            return True

        except Exception as e:
            print(f"❌ Error adding barber with Firebase Auth: {e}")
            return False

    ### static methods ###
    @staticmethod
    def get_barber_name(email: str, db: firestore.Client):
        """Fetch the barber's name based on their email."""
        try:
            collection_ref = db.collection('barbers')
            query = collection_ref.where("email", "==", email).stream()
            result_list = list(query)

            if not result_list:
                return None

            data = result_list[0].to_dict()
            return data.get('name')
        except Exception as e:
            print(f"❌ Error retrieving barber name: {e}")
            return None

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
                instagram = data.get('instagram')
                facebook = data.get('facebook')
                website = data.get('website')
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
                    'instagram': instagram,
                    'facebook': facebook,
                    'website': website,
                    'region': region,
                    'address': address,
                    'postal': postal
                }

            return barbers

        except Exception as e:
            print(f"❌ Error retrieving barbers: {e}")
            return None

class Service:
    # service_id is == its document id
    # barber_name is the barber it belongs to
    
    def __init__(self, barber_name, name, price : float, description, barber_email, service_id=None):
        self.service_id = service_id
        self.barber_name = barber_name
        self.name = name
        self.price = price
        self.description = description
        self.barber_email = barber_email

    # Setters
    def set_service_id(self, service_id: str):
        self.service_id = service_id

    def set_barber_name(self, barber_name: str):
        self.barber_name = barber_name

    def set_name(self, name: str):
        self.name = name

    def set_price(self, price: float):
        if price > 0:
            self.price = price
        else:
            raise ValueError("Price must be a positive number.")

    def set_description(self, description: str):
        self.description = description
    
    def set_barber_name(self, name: str):
        self.barber_name = name
    
    # Push to Firestore
    def push_to_db(self, db : firestore.Client):  # returns new service_id
        service_data = {
            "barber_id": self.barber_name,
            "name": self.name,
            "price": self.price,
            "description": self.description,
            "email": self.barber_email
        }

        # Save to Firestore in the 'services' collection
        doc_ref = db.collection('services').add(service_data)
        
        # add it to the barber's list of service IDs
        service_id = doc_ref[1].id
        
        print(f"Service '{self.name}' pushed to Firestore successfully!")
        return service_id

    def edit_service(self, db: firestore.Client, name=None, price=None, description=None):
        """Edit the service attributes and push the updated data to Firestore."""
        # Update only if new values are provided
        if name is not None:
            self.set_name(name)
        if price is not None:
            self.set_price(price)
        if description is not None:
            self.set_description(description)

        # Make sure service_id is present
        if not hasattr(self, 'service_id') or not self.service_id:
            print("Error: service_id is missing. Cannot update document.")
            return

        # Prepare the updated data
        updated_data = {
            "barber_id": self.barber_name,
            "name": self.name,
            "price": self.price,
            "description": self.description,
            "email": self.barber_email
        }

        # Reference the existing document and update
        doc_ref = db.collection('services').document(self.service_id)
        doc_ref.update(updated_data)

        print(f"Service '{self.service_id}' updated successfully!")

        
    def delete_service(self, db: firestore.Client):
        """Delete this service from Firestore."""
        try:
            db.collection("services").document(self.service_id).delete()
            print(f"Service '{self.service_id}' deleted successfully from Firestore!")
        except Exception as e:
            print(f"Error deleting service '{self.service_id}': {e}")

class Description:
    def __init__(self, barber_name: str, description: str, email: str, doc_id: str = None, when_added: datetime = None):
        self.barber_name = barber_name
        self.description = description
        self.email = email
        self.when_added = when_added or datetime.utcnow()
        self.doc_id = doc_id 

    @staticmethod
    async def get_all_descriptions(update: Update, context: CallbackContext):
        barber_email = context.user_data.get('current_user').email
        collection_ref = db.collection('descriptions')
        query = collection_ref.where("email", "==", barber_email)

        result_list = await get_account_document(update, context)
        curr_desc_ref = result_list[0].to_dict().get('description_id')  # DocumentReference
        active_desc_id = curr_desc_ref.id if curr_desc_ref else None  # Now it's a string

        description_objects = []
        for doc in query.stream():
            data = doc.to_dict()
            desc_obj = Description(
                barber_name=data.get('barber', ''),
                description=data.get('description', ''),
                email=data.get('email', ''),
                doc_id=doc.id,
                when_added=data.get('when_added')
            )
            if doc.id == active_desc_id:
                description_objects.insert(0, desc_obj)
            else:
                description_objects.append(desc_obj)


        return description_objects

    @staticmethod
    async def activate_description(update: Update, context: CallbackContext):
        current_user = context.user_data.get('current_user')
        new_description_id = context.user_data.get("curr_desc_id_displayed_on_bot")
        new_description_ref = db.collection('descriptions').document(new_description_id)
        barber_doc_ref = db.collection('barbers').document(current_user.doc_id)

        try:
            barber_doc_ref.update({'description_id': new_description_ref})
            current_user.desc_id = new_description_ref

            # send the confirmation
            msg = await update.callback_query.message.reply_text(
                f"Description is now active."
            )

            # wait 1 second, then delete that confirmation message
            await asyncio.sleep(1)
            await context.bot.delete_message(
                chat_id=msg.chat_id,
                message_id=msg.message_id
            )

        except Exception as e:
            await update.callback_query.message.reply_text(f"Error updating description: {e}")

    @staticmethod
    async def delete_description(update: Update, context: CallbackContext):
        doc_id = context.user_data.get("curr_desc_id_displayed_on_bot")
        if not doc_id:
            await update.callback_query.answer("No description selected.", show_alert=True)
            return

        try:
            # Get current active description from barber profile
            current_user = context.user_data.get("current_user")
            barber_doc = db.collection('barbers').document(current_user.doc_id).get()
            active_desc_ref = barber_doc.to_dict().get("description_id")

            # Check if the one being deleted is active
            is_active = active_desc_ref and active_desc_ref.id == doc_id

            # Delete the description
            db.collection('descriptions').document(doc_id).delete()
            msg = await update.callback_query.message.reply_text("🗑️ Description deleted.")

            # Short delay then delete the notification
            await asyncio.sleep(1)
            await context.bot.delete_message(
                chat_id=msg.chat_id,
                message_id=msg.message_id
            )

            # If deleted one was active, let you handle the logic (e.g. clearing, asking for a new one, etc.)
            if is_active:
                await Description.delete_active(update, context)
                

        except Exception as e:
            await update.callback_query.message.reply_text(f"Error deleting description: {e}")

    @staticmethod
    async def delete_active(update: Update, context: CallbackContext):
        current_user = context.user_data.get('current_user')
        barber_doc_ref = db.collection('barbers').document(current_user.doc_id)

        try:
            # Set the reference field to null (None in Python)
            barber_doc_ref.update({'description_id': None})
            current_user.desc_id = None

            # Send confirmation
            msg = await update.callback_query.message.reply_text(
                "‼️ You have deleted your active description!"
            )

            # Wait 1 second, then delete confirmation message
            await asyncio.sleep(1)
            await context.bot.delete_message(
                chat_id=msg.chat_id,
                message_id=msg.message_id
            )

        except Exception as e:
            await update.callback_query.message.reply_text(f"Error clearing active description: {e}")

                