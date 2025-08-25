# config.py

import os
from dotenv import load_dotenv

load_dotenv()


# --- Paths ---
# SHARED_DRIVE_PATH = r"\\LAPTOP-H6BPDG3T\Shared_08"
SHARED_DRIVE_PATH = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(SHARED_DRIVE_PATH, "Documents")
CHROMA_DB_DIRECTORY = os.path.join(SHARED_DRIVE_PATH, "chroma_db_data")
CHATS_DIR = os.path.join(SHARED_DRIVE_PATH, "outputs", "chats")
SHARED_PDFS_PATH = os.path.join(SHARED_DRIVE_PATH, "pdfs")

os.makedirs(SHARED_PDFS_PATH, exist_ok=True) 
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHROMA_DB_DIRECTORY, exist_ok=True)
os.makedirs(CHATS_DIR, exist_ok=True)

poppler_bin_path = r"C:\Users\Gautam kumar\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- File Constants ---x
SUPPORTED_FILE_TYPES = [".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"]
MAX_FILE_SIZE_MB = 10
MAX_FILES = 10
MAX_PAGES = 150

AVAILABLE_ROLES = ["user", "admin"]
AVAILABLE_ORGANIZATIONS = ["Eice Technology", "Google", "Public"]

ORGANIZATIONS = {
    "Eice Technology": {"domains": ["eicetechnology.com", "mycompany.com"], "roles": ["user", "admin"]},
    "Google": {"domains": ["google.com"], "roles": ["user"]},
    "Public": {"domains": ["gmail.com", "yahoo.com"], "roles": ["user"]}
}

# --- Database Configuration ---

# akshit
# DB_CONFIG = {
#     "dbname": "postgres",
#     "user": "postgres.tmzlvigxuqfzierxscgt",
#     "password": "abcd1234",
#     "host": "aws-0-ap-southeast-1.pooler.supabase.com",  # or your database host
#     "port": 5432
# }

# gautam
DB_CONFIG = {
    "user":"postgres.pmdqypsgwtgxpgolpuqm",
    "password":"db1234",
    "host":"aws-0-ap-south-1.pooler.supabase.com",
    "port":"6543",
    "dbname":"postgres"
}

EMAIL_CONFIG = {
    'email': 'gautamk8760@gmail.com', 
    'password': 'haqr isxg mndd tpbw'   
}