# app.py

import streamlit as st
import os
import time
import shutil
import comtypes.client # For Word to PDF conversion
import tempfile
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
from fpdf import FPDF
import glob

from config import (
    UPLOAD_FOLDER, CHROMA_DB_DIRECTORY, poppler_bin_path,
    SUPPORTED_FILE_TYPES, MAX_FILE_SIZE_MB, MAX_FILES, MAX_PAGES
)
from utils.file_processing import (
    get_file_extension, is_valid_file, convert_to_pdf
)
from utils.extraction import get_extracted_text
from utils.rag_pipeline import setup_rag_pipeline

# --- Session state initialization ---
if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.messages = [{"role": "assistant", "content": "Welcome to AskEice! Upload your files to get started."}]
if "approved_files" not in st.session_state:
    st.session_state.approved_files = []
if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None
if "chat_history_titles" not in st.session_state:
    st.session_state.chat_history_titles = []
if "current_chat_title" not in st.session_state:
    st.session_state.current_chat_title = None
if "chroma_dir" not in st.session_state:
    st.session_state.chroma_dir = None


# --- Streamlit UI and Logic ---
st.set_page_config(page_title="askEice - Document QA", layout="wide")

with st.sidebar:
    st.markdown("### askEICE")
    if st.button("New Chat", key="new_chat"):
        if st.session_state.page == "chat" and st.session_state.current_chat_title:
            st.session_state.chat_history_titles.append(st.session_state.current_chat_title)
        
        st.session_state.page = "upload"
        st.session_state.messages.clear()
        st.session_state.approved_files.clear()
        st.session_state.rag_chain = None
        st.session_state.current_chat_title = None
        
        if os.path.exists(UPLOAD_FOLDER):
            shutil.rmtree(UPLOAD_FOLDER)
            os.makedirs(UPLOAD_FOLDER)
        if st.session_state.chroma_dir and os.path.exists(st.session_state.chroma_dir):
            shutil.rmtree(st.session_state.chroma_dir)
        st.rerun()

    if st.session_state.chat_history_titles:
        st.markdown("---")
        st.markdown("#### ⏳ Previous Chats")
        for title in st.session_state.chat_history_titles:
            st.markdown(f"- {title}")

    if st.session_state.approved_files:
        st.markdown("---")
        st.markdown("#### ✅ Uploaded Documents")
        for file_info in st.session_state.approved_files:
            st.write(file_info['File Name'])
    
if st.session_state.page == "upload":
    st.title("Upload Files")
    st.markdown("Please upload documents (PDF, DOCX, JPG, PNG) to create a knowledge base.")

    uploaded_files = st.file_uploader(
        label="Upload files",
        type=[f.strip('.') for f in SUPPORTED_FILE_TYPES],
        accept_multiple_files=True,
        help=f"Supported file types: {', '.join(SUPPORTED_FILE_TYPES)}\n"
             f"Upload limit: Up to {MAX_FILES} files at a time\n"
             f"File size limit: {MAX_FILE_SIZE_MB} MB per file\n"
             f"Document length limit: Maximum {MAX_PAGES} pages per document",
    )

    if uploaded_files:
        if len(uploaded_files) > MAX_FILES:
            st.error(f"You can upload up to {MAX_FILES} files at a time.")
        else:
            approved_files = []
            rejected_files = []

            for file in uploaded_files:
                ext = get_file_extension(file)
                valid, msg = is_valid_file(file)

                if valid:
                    file.seek(0)
                    save_path = os.path.join(UPLOAD_FOLDER, file.name)

                    if ext.lower() == ".pdf":
                        # Already a PDF, just save it
                        with open(save_path, "wb") as f:
                            f.write(file.read())
                        approved_files.append({"File Name": file.name, "PDF Path": save_path})
                    else:
                        success, result = convert_to_pdf(file, ext, save_path)
                        if success:
                            approved_files.append({"File Name": file.name, "PDF Path": result})
                        else:
                            rejected_files.append({"File Name": file.name, "Reason": result})
                else:
                    rejected_files.append({"File Name": file.name, "Reason": msg})

            st.session_state.approved_files = approved_files

            st.markdown("### ✅ Approved Files")
            if approved_files:
                st.table(approved_files)
            else:
                st.write("No files approved.")

            st.markdown("### ❌ Not Approved Files")
            if rejected_files:
                st.table(rejected_files)
            else:
                st.write("All files approved.")

            if st.session_state.approved_files:
                use_ocr = st.checkbox("Enable OCR (for images and scanned docs)", value=False)

                if st.button("Start Processing", key="start_processing"):
                    st.session_state.page = "processing"
                    st.session_state.use_ocr_choice = use_ocr
                    st.rerun()

elif st.session_state.page == "processing":
    st.title("Processing Documents...")
    st.info("Please wait while your documents are being processed.")
    
    if st.session_state.approved_files:
        with st.status("Initializing...", expanded=True) as status_container:
            try:
                status_container.update(label="Extracting text from documents...")
                pdf_paths_to_process = [f['PDF Path'] for f in st.session_state.approved_files]
                combined_extracted_text = get_extracted_text(pdf_paths_to_process, use_ocr=st.session_state.use_ocr_choice)
                if not combined_extracted_text.strip():
                    raise ValueError("No text was extracted from the PDFs. Please check the files.")
                status_container.update(label="Text Extraction Complete!", state="complete")
                
                status_container.update(label="Building RAG pipeline...")
                rag_chain, chroma_dir = setup_rag_pipeline(combined_extracted_text)
                st.session_state['rag_chain'] = rag_chain
                st.session_state.chroma_dir = chroma_dir
                status_container.update(label="RAG Pipeline Built!", state="complete")
                
                st.success("Processing complete!")
                
                st.session_state.page = "chat"
                st.session_state.current_chat_title = f"Chat ({time.strftime('%Y-%m-%d %H:%M')})"
                st.session_state.messages = [{"role": "assistant", "content": "Hey! How can I help you today? Feel free to ask me anything."}]
                st.rerun()

            except Exception as e:
                st.error(f"An error occurred during processing: {e}")
                st.exception(e)
                st.stop()
    else:
        st.warning("No files were approved for processing. Please go back to upload files.")
        st.session_state.page = "upload"
        st.rerun()

# Chat Page
elif st.session_state.page == "chat":
    st.title(st.session_state.get('current_chat_title', 'Ask Anything'))
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_prompt = st.chat_input("Ask me anything...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            if st.session_state.rag_chain:
                try:
                    with st.spinner("Thinking..."):
                        response = st.session_state.rag_chain.invoke(user_prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"An error occurred during interaction: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"An error occurred: {e}"})
            else:
                st.warning("The RAG pipeline is not ready. Please go back and process documents.")
                st.session_state.page = "upload"
                st.rerun()