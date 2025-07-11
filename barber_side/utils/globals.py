import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pytz
from telegram import Update
from telegram.ext import CallbackContext
from firebase_admin import auth
from telegram.ext import ConversationHandler
from firebase_admin import firestore, initialize_app, storage

# Dictionary to store logged-in user sessions
# KEY: TELEGRAM USERID
# VALUE: FIREBASE UUID
user_sessions = {}

### Loading Environmental Variables ###
load_dotenv()

if not firebase_admin._apps:
    firebase_credentials = {
        "type": os.getenv("type"),
        "project_id": os.getenv("project_id"),
        "private_key_id": os.getenv("private_key_id"),
        "private_key": os.getenv("private_key").replace("\\n", "\n"),
        "client_email": os.getenv("client_email"),
        "client_id": os.getenv("client_id"),
        "auth_uri": os.getenv("auth_uri"),
        "token_uri": os.getenv("token_uri"),
        "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
        "client_x509_cert_url": os.getenv("client_x509_cert_url"),
        "universe_domain": os.getenv("universe_domain")
    }
    cred = credentials.Certificate(firebase_credentials)
    initialize_app(cred, {
        "storageBucket": "absqueuebot.firebasestorage.app"
    })
    

db = firestore.client() # NOTE 
TOKEN = os.getenv("BOT_TOKEN")

# Firebase Web API Key (Required for login)
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_AUTH_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

timezone = pytz.timezone("Asia/Singapore")
view_my_descriptions_end_flag = False

#### FUNCTIONS
# helper function to get own document details
async def get_account_document(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        return  # or handle the unexpected case

    firebase_user_id = user_sessions.get(user_id)

    user = auth.get_user(firebase_user_id)
    email = user.email
    # email gotten from firebase authentication user list
    
    # now use it to query for collection 'barbers'
    collection_ref = db.collection('barbers')
    
    # Perform the query to find slots matching the user's email
    field_name = "email"  # The field name for email in the collection
    value = email  # The logged-in user's email
    query = collection_ref.where(field_name, "==", value)
    
    # get the result from the query
    result = query.stream()
    result_list = list(result)
    return result_list

async def check_login(update:Update, context: CallbackContext) -> bool:
    logged_in = context.user_data.get('logged_in')
    if not logged_in:
        return False
    return True