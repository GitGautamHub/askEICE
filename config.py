# config.py

import os
from dotenv import load_dotenv

load_dotenv()


# --- Paths ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(ROOT_DIR, "Documents")
CHROMA_DB_DIRECTORY = os.path.join(ROOT_DIR, "chroma_db_data")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
poppler_bin_path = r"C:\Users\Gautam kumar\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- File Constants ---
SUPPORTED_FILE_TYPES = [".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"]
MAX_FILE_SIZE_MB = 10
MAX_FILES = 10
MAX_PAGES = 150