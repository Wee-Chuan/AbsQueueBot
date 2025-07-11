import pytz
# from google.cloud import storage

# Keep only Firebase imports
from firebase_admin import storage

from barber_side.handlers.menu_handlers import clear_menu

from datetime import datetime as dt
from datetime import timedelta

def initialize_storage_client():
    # Initialize Firebase if not already done
    if not firebase_admin._apps:
        # Initialize with your Firebase config
        cred = firebase_admin.credentials.Certificate("path/to/serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'your-project-id.appspot.com'  # Your actual bucket name
        })
    
    # Get the default bucket
    bucket = storage.bucket()
    return bucket

def generate_signed_url(blob_name, expiration_minutes=30):
    try:
        bucket = initialize_storage_client()
        blob = bucket.blob(blob_name)
        
        # Generate signed URL (expiration in seconds)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET"
        )
        return signed_url
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        return None

# Telegram Bot Function to Display the Image
async def display_start_image(update, context, blob_name):
    try:
        # Generate signed URL
        signed_url = generate_signed_url(blob_name)
        
        if not signed_url:
            await update.callback_query.message.reply_text("Failed to fetch image from storage.")
            return
    
        await update.message.reply_photo(photo=signed_url, caption="Welcome to Absqueue! We're glad to have you on board 🚀")
    
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error displaying image: {e}")

# Telegram Bot Function to Display the Image
async def display_barber_image(update, context, blob_name, caption):
    try:
        # Generate signed URL
        signed_url = generate_signed_url(blob_name)
        
        if not signed_url:
            await update.callback_query.message.reply_text("Failed to fetch image from storage.")
            return

        message = update.message or update.callback_query.message
        message = await message.reply_photo(photo=signed_url, caption = caption)
        await clear_menu(update, context)
        
        menu_messages = context.user_data.get('menu_message', [])
        menu_messages.append(message.message_id)
    
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error displaying image: {e}")

### CLEANING open slots (expired)
import datetime
from google.cloud import firestore
from barber_side.utils.globals import *

import pytz
from firebase_admin import firestore

sg_tz = pytz.timezone("Asia/Singapore")

async def cleanup_expired_open_slots(barber_email: str):
    # Get current time in Singapore timezone
    now = datetime.datetime.now(sg_tz)
    current_minute = now.minute

    print("🧹 Running expired slot cleanup...")
    print(barber_email)
    # Query slots for this barber only
    query = (
        db.collection("open slots")
        .where("barber_email", "==", barber_email)
    )

    docs = query.stream()

    deleted_count = 0

    for doc in docs:
        data = doc.to_dict()
        slot_start_time_str = data.get("start time")  # Make sure this is in ISO format!
        print(slot_start_time_str)
        if not slot_start_time_str:
            continue
        
        # Check if slot_start_time_str is already a datetime object
        if isinstance(slot_start_time_str, datetime.datetime):
            # If it's already a datetime, no need to parse it again
            slot_start_time = slot_start_time_str.astimezone(sg_tz)
        else:
            # If it's a string, make sure it's in ISO format
            try:
                slot_start_time = datetime.datetime.fromisoformat(slot_start_time_str).astimezone(sg_tz)
            except ValueError as e:
                print(f"⚠️ Error while parsing datetime: {e}")
                # Handle the error appropriately (maybe skip the entry or notify)


        if slot_start_time < now:
            print(f"❌ Deleting expired slot: {slot_start_time}")
            doc.reference.delete()
            deleted_count += 1

    print(f"✅ Cleanup done. Deleted {deleted_count} expired slots.")
