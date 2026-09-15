from datetime import datetime
import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_FILE_NAME = "uploads_database"  # Old collection for subscriptions

# Build Firebase credentials
firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
}

# Initialize Firebase app
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
db = firestore.client()
# -----------------------
# User tracking functions
# -----------------------
def update_user_status(user_id, username, first_name, is_blocked=False):
    """Create/update user record with activity & block status"""
    try:
        doc_ref = db.collection("bot_users").document(str(user_id))
        doc_ref.set({
            "username": username or "Unknown",
            "first_name": first_name or "Unknown",
            "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_blocked": is_blocked
        }, merge=True)
    except Exception as e:
        print(f"❌ Failed to update user status: {e}")

def get_user_stats():
    """Return total, active, and blocked users count"""
    try:
        users_ref = db.collection("bot_users").stream()
        total = blocked = 0
        for user in users_ref:
            total += 1
            if user.to_dict().get("is_blocked"):
                blocked += 1
        return {
            "total_users": total,
            "active_users": total - blocked,
            "blocked_users": blocked
        }
    except Exception as e:
        print(f"❌ Failed to get user stats: {e}")
        return {"total_users": 0, "active_users": 0, "blocked_users": 0}


def get_all_users():
    try:
        users = db.collection("bot_users").stream()
        return [user.id for user in users]
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        return []
