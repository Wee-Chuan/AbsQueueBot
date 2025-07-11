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

# Dictionary to store logged-in user sessions
# KEY: TELEGRAM USERID
# VALUE: FIREBASE UUID
user_sessions = {}

### Loading Environmental Variables ###
load_dotenv()

### Firebase initialisation ###
# Initialize Firebase Admin
if not firebase_admin._apps:
    cred = credentials.Certificate("absqueuebot-firebase-adminsdk-fbsvc-2b8bceded6.json")
    firebase_admin.initialize_app(cred)

db = firestore.Client() # NOTE 
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