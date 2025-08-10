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


# Constants for chat history
MAX_CHAT_HISTORY = 10

# --- PostgreSQL Connection Helper ---
# @st.cache_resource
def get_pg_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- Init DB ---
def init_db():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password BYTEA NOT NULL
                )
            """)
            conn.commit()  # Commit right after table creation

        # Try ALTERs in separate cursor blocks with rollback safety
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
                conn.commit()
            except psycopg2.errors.DuplicateColumn:
                conn.rollback()  # Rollback only this failed ALTER
            except Exception as e:
                conn.rollback()
                print(f"Error adding 'first_name': {e}")

        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN last_name TEXT DEFAULT ''")
                conn.commit()
            except psycopg2.errors.DuplicateColumn:
                conn.rollback()
            except Exception as e:
                conn.rollback()
                print(f"Error adding 'last_name': {e}")
        
        # Create OTP table for password reset
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
def create_user(username, password):
    username = username.strip().lower()
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
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
                cur.execute("SELECT password FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row and bcrypt.checkpw(password.encode(), row[0].tobytes()):
                    return True, "Login successful!"
                elif row:
                    return False, "Incorrect password."
                else:
                    return False, "User not found."
    except Exception as e:
        return False, f"DB Error: {str(e)}"

# --- Chat History Functions ---
def get_chat_title(chat_data, filename):
    if chat_data and len(chat_data) > 0 and "content" in chat_data[0]:
        first_message = chat_data[0]["content"]
        if first_message and len(first_message) > 40:
            return first_message[:40] + "..."
        return first_message
    return filename.replace('.json', '').replace('chat_', 'Chat ')

def load_user_chats(username):
    user_chat_dir = os.path.join(CHATS_DIR, username)
    if not os.path.exists(user_chat_dir):
        os.makedirs(user_chat_dir)
        return []
    
    chat_files = sorted([f for f in os.listdir(user_chat_dir) if f.endswith('.json')], reverse=True)
    chats = []
    for file in chat_files:
        try:
            file_path = os.path.join(user_chat_dir, file)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # user_messages = [msg for msg in data.get('messages', []) if msg.get('role') == 'user']
            title = data.get('title')
            title = get_chat_title(data, file)
            
            chats.append({
                "file": file, 
                "title": title,
                "path": file_path
            })
        except Exception as e:
            continue
    return chats

def get_user_info(username):
    """Fetches user's first name and email from the database."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT first_name, username FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row:
                    first_name, email = row
                    return first_name, email
                else:
                    return None, None
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return None, None

def save_current_chat():
    """Saves the current chat session to a JSON file, including the title."""
    if not st.session_state.get('current_chat_file'):
        return
    if not st.session_state.get('messages'):
        return
    
    try:
        os.makedirs(os.path.dirname(st.session_state.current_chat_file), exist_ok=True)
        
        chat_data = {
            "title": st.session_state.get("current_chat_title", "Untitled Chat"), # <-- Ye line add karo
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

    
    # NEW LOGIC: Explicitly close the vectorstore and delete the directory
    if st.session_state.get('rag_chain'):
        st.session_state.rag_chain = None
    
    if st.session_state.get('chroma_dir') and os.path.exists(st.session_state.chroma_dir):
        time.sleep(1)
        try:
            shutil.rmtree(st.session_state.chroma_dir)
            print(f"Successfully removed old ChromaDB directory: {st.session_state.chroma_dir}")
        except PermissionError as e:
            print(f"Failed to remove directory: {e}. Skipping deletion.")
            # st.warning("Could not clean up old session data. Please manually delete the old 'chroma_db_data' folder.")

    # Rest of the cleanup
    st.session_state.current_chat_file = new_chat_path
    st.session_state.current_chat_title = new_chat_data["title"]
    st.session_state.page = "upload"
    st.session_state.messages = [{"role": "assistant", "content": "Hey! How can I help you today? Feel free to ask me anything."}]
    st.session_state.approved_files = []
    st.session_state.chroma_dir = None
    
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
        os.makedirs(UPLOAD_FOLDER)

    # // CRUCIAL FIX: Create the new chat file and update the session state
    # // This ensures the new chat appears in the sidebar immediately.
    new_chat_data = {
        "title": f"Chat ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})",
        "messages": st.session_state.messages,
        "approved_files": st.session_state.approved_files,
        "chroma_dir": st.session_state.chroma_dir 
    }
    with open(new_chat_path, "w", encoding="utf-8") as f:
        json.dump(new_chat_data, f, indent=2, ensure_ascii=False)
        
    st.session_state.current_chat_file = new_chat_path
    st.session_state.current_chat_title = new_chat_data["title"]


def rename_chat(chat_path, new_title):
    """Renames a saved chat file's title."""
    try:
        if not os.path.exists(chat_path):
            return False, "Chat file not found."
            
        with open(chat_path, "r+", encoding="utf-8") as f:
            chat_data = json.load(f)
            chat_data["title"] = new_title
            
            # Go back to the beginning of the file and write the new data
            f.seek(0)
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
            f.truncate() # Remove any trailing content
        st.session_state.current_chat_title = new_title
        return True, "Chat renamed successfully."
    except Exception as e:
        return False, f"Error renaming chat: {e}"

def load_chat(chat_path):
    if (st.session_state.get('current_chat_file') and
        st.session_state.get('messages') and
        len(st.session_state.messages) > 1):
        save_current_chat()
        
    try:
        with open(chat_path, "r", encoding="utf-8") as f:
            chat_data = json.load(f)

        chat_title = chat_data.get('title', os.path.basename(chat_path).replace('.json', '').replace('chat_', 'Chat '))
        st.session_state.current_chat_file = chat_path
        st.session_state.messages = chat_data.get("messages", [])
        st.session_state.approved_files = chat_data.get("approved_files", [])
        st.session_state.chat_created_at = chat_data.get("created_at", datetime.datetime.now().isoformat())
        st.session_state.chroma_dir = chat_data.get("chroma_dir", None)
        st.session_state.current_chat_title = chat_title 

        # Check if the ChromaDB directory still exists
        if os.path.exists(st.session_state.chroma_dir):
            # Rebuilding the vector store from the saved directory is the key!
            embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
            vectorstore = Chroma(persist_directory=st.session_state.chroma_dir, embedding_function=embeddings_model)
            
            # Rebuilding the RAG chain
            st.session_state.rag_chain = get_rag_chain(vectorstore)
            
            st.session_state.page = "chat"
            # st.session_state.current_chat_title = get_chat_title(st.session_state.messages, os.path.basename(chat_path))
            st.rerun()
        else:
            # If ChromaDB directory is missing, give a warning
            st.session_state.page = "upload"
            st.warning("This chat's documents or knowledge base could not be found. Please re-upload documents to continue.")
            st.rerun()
    except Exception as e:
        print(f"Error loading chat: {e}")

def get_chat_title(chat_data, filename):
    """
    Generates a user-friendly title from the first user message, or a fallback.
    It first checks for a saved 'title' key in the chat data.
    """
    # First, check if a custom title is already saved in the chat data.
    # We assume chat_data here is the full JSON object loaded from the file.
    if isinstance(chat_data, dict) and chat_data.get('title'):
        # If the title is a placeholder, we'll generate a new one.
        if chat_data['title'] != "Untitled Chat":
            return chat_data['title']

    # If no custom title, fall back to generating one from the first user message.
    user_messages = [msg for msg in chat_data.get('messages', []) if msg.get('role') == 'user']
    if user_messages and user_messages[0].get('content'):
        first_message = user_messages[0]["content"]
        if len(first_message) > 40:
            return first_message[:40] + "..."
        return first_message

    # If no user messages either, return a default filename-based title.
    return filename.replace('.json', '').replace('chat_', 'Chat ')

def logout_user():
    if "user" in st.session_state:
        save_current_chat()
        del st.session_state["user"]