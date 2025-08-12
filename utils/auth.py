# utils/auth.py

import streamlit as st
import os
import json
import bcrypt
import psycopg2
import datetime
from config import DB_CONFIG, CHATS_DIR, UPLOAD_FOLDER
import shutil
import time
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from utils.rag_pipeline import get_rag_chain

MAX_CHAT_HISTORY = 10
NOTES_FILE = os.path.join(CHATS_DIR, "admin_notes.json")

# --- PostgreSQL Connection Helper ---
def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- Init DB ---
def init_db():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password BYTEA NOT NULL
                )
            """)
            conn.commit()

        # Add columns if missing
        alter_statements = [
            ("first_name TEXT", "first_name"),
            ("last_name TEXT DEFAULT ''", "last_name"),
            ("role TEXT DEFAULT 'user'", "role")
        ]
        for column_def, column_name in alter_statements:
            with conn.cursor() as cur:
                try:
                    cur.execute(f"ALTER TABLE users ADD COLUMN {column_def}")
                    conn.commit()
                except psycopg2.errors.DuplicateColumn:
                    conn.rollback()
                except Exception as e:
                    conn.rollback()
                    print(f"Error adding '{column_name}': {e}")

        # OTP table
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_otps (
                        username TEXT PRIMARY KEY,
                        otp TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                """)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Error creating OTP table: {e}") 

# --- Create User ---
def create_user(username, password, role="user"):
    username = username.strip().lower()
    role = role.lower() if role.lower() in ["admin", "user"] else "user"
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, hashed_pw, role)
                )
                conn.commit()
        return True, "Account created successfully!"
    except psycopg2.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"DB Error: {str(e)}"

# --- Authenticate User ---
def authenticate_user(username, password):
    username = username.strip().lower()
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password, role FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row and bcrypt.checkpw(password.encode(), row[0].tobytes()):
                    return True, row[1]  # Return role
                elif row:
                    return False, "Incorrect password."
                else:
                    return False, "User not found."
    except Exception as e:
        return False, f"DB Error: {str(e)}"

# --- Chat Title Helper ---
def get_chat_title(chat_data, filename):
    if isinstance(chat_data, dict) and chat_data.get('title'):
        if chat_data['title'] != "Untitled Chat":
            return chat_data['title']
    user_messages = [msg for msg in chat_data.get('messages', []) if msg.get('role') == 'user']
    if user_messages and user_messages[0].get('content'):
        first_message = user_messages[0]["content"]
        return first_message[:40] + "..." if len(first_message) > 40 else first_message
    return filename.replace('.json', '').replace('chat_', 'Chat ')

# --- Load Chats Based on Role ---
def load_user_chats(username, role="user"):
    chats = []
    if role == "admin":
        # Admin → own chats only
        user_chat_dir = os.path.join(CHATS_DIR, username)
        os.makedirs(user_chat_dir, exist_ok=True)
        chat_files = sorted([f for f in os.listdir(user_chat_dir) if f.endswith('.json')], reverse=True)
        for file in chat_files:
            try:
                file_path = os.path.join(user_chat_dir, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                chats.append({"file": file, "title": get_chat_title(data, file), "path": file_path})
            except:
                continue
    else:
        # User → no direct chats shown (they see notes instead)
        return []
    return chats

# --- User Info ---
def get_user_info(username):
    """Returns (first_name, email, role)"""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT first_name, username, role FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row:
                    return row[0], row[1], row[2]
                else:
                    return None, None, None
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return None, None, None

# --- Save Chat ---
def save_current_chat():
    if not st.session_state.get('current_chat_file'):
        return
    if not st.session_state.get('messages'):
        return
    try:
        os.makedirs(os.path.dirname(st.session_state.current_chat_file), exist_ok=True)
        chat_data = {
            "title": st.session_state.get("current_chat_title", "Untitled Chat"),
            "created_at": st.session_state.get("chat_created_at", datetime.datetime.now().isoformat()),
            "updated_at": datetime.datetime.now().isoformat(),
            "messages": st.session_state.messages,
            "approved_files": st.session_state.approved_files,
            "user": st.session_state["user"],
            "chroma_dir": st.session_state.chroma_dir 
        }
        with open(st.session_state.current_chat_file, "w", encoding="utf-8") as f:
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Error saving chat: {e}")

# --- Create New Chat ---
def create_new_chat():
    if (st.session_state.get('current_chat_file') and
        st.session_state.get('messages') and
        len(st.session_state.messages) > 1):
        save_current_chat()
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    chat_filename = f"chat_{timestamp}.json"
    user_chat_dir = os.path.join(CHATS_DIR, st.session_state["user"])
    os.makedirs(user_chat_dir, exist_ok=True)
    
    new_chat_path = os.path.join(user_chat_dir, chat_filename)
    new_chat_data = {
        "title": "Untitled Chat",
        "messages": [{"role": "assistant", "content": "Welcome to AskEice! Upload your files to get started."}],
        "approved_files": [],
        "chroma_dir": None 
    }
    with open(new_chat_path, "w", encoding="utf-8") as f:
        json.dump(new_chat_data, f, indent=2, ensure_ascii=False)

    if st.session_state.get('rag_chain'):
        st.session_state.rag_chain = None
    
    if st.session_state.get('chroma_dir') and os.path.exists(st.session_state.chroma_dir):
        time.sleep(1)
        try:
            shutil.rmtree(st.session_state.chroma_dir)
        except PermissionError:
            pass

    st.session_state.current_chat_file = new_chat_path
    st.session_state.current_chat_title = new_chat_data["title"]
    st.session_state.page = "upload"
    st.session_state.messages = [{"role": "assistant", "content": "Hey! How can I help you today? Feel free to ask me anything."}]
    st.session_state.approved_files = []
    st.session_state.chroma_dir = None
    
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
        os.makedirs(UPLOAD_FOLDER)

    # Save initial state
    new_chat_data["title"] = f"Chat ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})"
    with open(new_chat_path, "w", encoding="utf-8") as f:
        json.dump(new_chat_data, f, indent=2, ensure_ascii=False)
        
    st.session_state.current_chat_file = new_chat_path
    st.session_state.current_chat_title = new_chat_data["title"]

# --- Rename Chat ---
def rename_chat(chat_path, new_title):
    try:
        if not os.path.exists(chat_path):
            return False, "Chat file not found."
        with open(chat_path, "r+", encoding="utf-8") as f:
            chat_data = json.load(f)
            chat_data["title"] = new_title
            f.seek(0)
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
            f.truncate()
        st.session_state.current_chat_title = new_title
        return True, "Chat renamed successfully."
    except Exception as e:
        return False, f"Error renaming chat: {e}"

# --- Load Chat ---
def load_chat(chat_path):
    if (st.session_state.get('current_chat_file') and
        st.session_state.get('messages') and
        len(st.session_state.messages) > 1):
        save_current_chat()
    try:
        with open(chat_path, "r", encoding="utf-8") as f:
            chat_data = json.load(f)
        st.session_state.current_chat_file = chat_path
        st.session_state.messages = chat_data.get("messages", [])
        st.session_state.approved_files = chat_data.get("approved_files", [])
        st.session_state.chat_created_at = chat_data.get("created_at", datetime.datetime.now().isoformat())
        st.session_state.chroma_dir = chat_data.get("chroma_dir", None)
        st.session_state.current_chat_title = chat_data.get('title', os.path.basename(chat_path))

        if os.path.exists(st.session_state.chroma_dir):
            embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
            vectorstore = Chroma(persist_directory=st.session_state.chroma_dir, embedding_function=embeddings_model)
            st.session_state.rag_chain = get_rag_chain(vectorstore)
            st.session_state.page = "chat"
            st.rerun()
        else:
            st.session_state.page = "upload"
            st.warning("This chat's documents are missing. Please re-upload.")
            st.rerun()
    except Exception as e:
        print(f"Error loading chat: {e}")

# --- Admin Notes ---
def load_admin_notes():
    if not os.path.exists(NOTES_FILE):
        return {}
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_admin_notes(notes_data):
    os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes_data, f, indent=2, ensure_ascii=False)

# --- Logout ---
def logout_user():
    if "user" in st.session_state:
        save_current_chat()
        del st.session_state["user"]
