import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore, initialize_app, storage
import pytz
import os

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

# Firebase Web API Key (Required for login)
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_AUTH_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

# GEOCODING API key
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")

timezone = pytz.timezone("Asia/Singapore")