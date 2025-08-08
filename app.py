# app.py
import streamlit as st
from utils.auth import init_db, logout_user, load_user_chats, create_new_chat
from upload_process_page import render_upload_page, render_processing_page
from chat_page import render_chat_page
from auth_flow import render_auth_flow
import bcrypt
from utils.auth import load_chat, get_user_info

# --- Session state initialization ---
if "user" not in st.session_state:
    st.session_state.page = "login"
if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.messages = [{"role": "assistant", "content": "Welcome to AskEice! Upload your files to get started."}]
if "approved_files" not in st.session_state:
    st.session_state.approved_files = []
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "current_chat_file" not in st.session_state:
    st.session_state.current_chat_file = None
if "chroma_dir" not in st.session_state:
    st.session_state.chroma_dir = None
if "current_chat_title" not in st.session_state:
    st.session_state.current_chat_title = None

st.set_page_config(page_title="AskEice - Document QA", layout="wide")

# --- Authentication Flow ---
if st.session_state.page == "login":
    init_db()
    render_auth_flow()
    st.stop()
    
# --- Main App Sidebar & Routing ---
with st.sidebar:
    st.markdown("### askEICE")
    
    if "user" in st.session_state:
        first_name, email = get_user_info(st.session_state['user'])
        
        if first_name:
            st.sidebar.success(f"Logged in as: **{first_name}**\n\n{email}") # <-- ye line change karo
        else:
            st.sidebar.success(f"Logged in as: {email}") # Fallback if name is not found
            
        if st.sidebar.button(" 🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()

    st.markdown("---")
    if st.button("✨ New Chat", use_container_width=True):
        create_new_chat()
        st.rerun()

    # Previous chat history section with visual improvements
    if st.session_state.get("user"):
        st.markdown("---")
        st.markdown("#### ⏳ Previous Chats")
        user_chats = load_user_chats(st.session_state["user"])
        if user_chats:
            for chat in user_chats:
                button_label = f" {chat['title']}"
                if len(button_label) > 40:
                    button_label = button_label[:37] + "..."
                
                # Use a single, styled button for each chat
                button_type = "primary" if st.session_state.get('current_chat_file') == chat['path'] else "secondary"
                if st.button(button_label, key=chat['path'], use_container_width=True, type=button_type):
                    load_chat(chat['path'])
                    st.rerun()
        else:
            st.info("No previous chats found.")
            
    if st.session_state.approved_files:
        st.markdown("---")
        st.markdown("#### 📄 Uploaded Documents")
        for file_info in st.session_state.approved_files:
            st.write(f"- {file_info['File Name']}")


# --- Main Page Content based on session state ---
if st.session_state.page == "upload":
    render_upload_page()
elif st.session_state.page == "processing":
    render_processing_page()
elif st.session_state.page == "chat":
    render_chat_page()