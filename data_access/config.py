import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Path to your Firebase service account key file
FIREBASE_CREDENTIALS_PATH = json.loads(os.getenv("FIREBASE_CREDENTIALS"))


# Initialize Firebase (Singleton Pattern: Initialize only once)
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)

# Firestore database instance
db = firestore.client()