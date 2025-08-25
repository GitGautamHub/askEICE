# app.py
import streamlit as st
from utils.auth import init_db, logout_user, load_user_chats, create_new_chat
from upload_process_page import render_upload_page
from chat_page import render_chat_page
from auth_flow import render_auth_flow
import bcrypt
from utils.auth import load_chat, get_user_info, get_users_by_organization
from utils.rag_pipeline import get_or_create_vectorstore, get_rag_chain
import time
from upload_process_page import render_processing_status_page


# --- Session state initialization ---
if "user" not in st.session_state:
    st.session_state.page = "login"
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "messages" not in st.session_state:
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
if st.session_state.page == 'processing_status':
    render_processing_status_page()

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
        user_info = get_user_info(st.session_state['user'])
        if user_info:
            # Display user info with role and organization
            st.sidebar.success(f"Logged in as: **{user_info['first_name']}**\n\nRole: **{user_info['role']}**\n\nOrg: **{user_info['organization']}**")
        else:
            st.sidebar.success(f"Logged in as: {st.session_state['user']}")

        if st.sidebar.button(" Logout", use_container_width=True):
            logout_user()
            st.rerun()

    # st.markdown("---")

    # Admin ke liye "New Chat" button
    if st.session_state.get("user"):
        user_info = get_user_info(st.session_state['user'])
        if user_info and user_info["role"] == "admin":
            st.markdown("---")
            st.markdown("#### Knowledge Base Management")
            if st.button(" Upload Documents", key="admin_upload_btn", use_container_width=True):
                # Admin clicks this to add to the shared knowledge base
                st.session_state.page = "upload"

                # st.session_state.current_chat_title = "Update Knowledge Base" # A fixed title for this action
                st.rerun()
            # This "New Chat" button is for starting a fresh, new conversation
    if st.button(" New Chat", use_container_width=True):
        # Admin ke liye, yeh button seedhe chat page par redirect karega with the shared RAG pipeline
        if user_info and user_info["role"] == "admin":
            org_name = user_info['organization']
            vectorstore = get_or_create_vectorstore(org_name)
            st.session_state.rag_chain = get_rag_chain(vectorstore)
            create_new_chat()
            st.session_state.page = "chat"
            st.session_state.current_chat_title = f"Chat with Knowledge Base"
            st.rerun()
        # Normal user ke liye, yeh button naya chat session shuru karega
        else:
            create_new_chat()
            st.session_state.page = "chat"
            st.session_state.current_chat_title = f"New Chat"
            st.rerun()

    # Previous chat history section
    if st.session_state.get("user"):
        st.markdown("---")
        st.markdown("####  Previous Chats")
        
        # Load chats for the logged-in user
        all_chats = load_user_chats(st.session_state['user'])
        
        
        if all_chats:
            for chat in all_chats:
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
    user_info = get_user_info(st.session_state['user'])
    if user_info and user_info["role"] == "admin":
        # st.session_state.page = "chat"
        render_upload_page()
    else:
        st.title(f"Welcome {user_info['first_name']} to AskEICE 👋")

        st.write(
            """
            You can now start interacting with the knowledge base by clicking on *New Chat*.  

            • Use the *Previous Chats* menu in the sidebar to manage and revisit your earlier conversations.  

            • Explore AskEICE and make the most out of it 
            """
        )


elif st.session_state.page == "chat":
    # User's RAG pipeline will be loaded here
    user_info = get_user_info(st.session_state['user'])
    if user_info:
        org_name = user_info['organization']
        vectorstore = get_or_create_vectorstore(org_name)
        st.session_state.rag_chain = get_rag_chain(vectorstore)
    render_chat_page()
