import streamlit as st
import os
import time
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
from fpdf import FPDF
import comtypes.client  # For Word to PDF conversion
import shutil
import tempfile

# Constants
SUPPORTED_FILE_TYPES = [".doc", ".docx", ".pdf", ".png", ".jpg"]
MAX_FILE_SIZE_MB = 10
MAX_FILES = 10
MAX_PAGES = 150
UPLOAD_FOLDER = r"D:\DemoAskEice\Documents"

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Session state
if "page" not in st.session_state:
    st.session_state.page = "upload"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processed" not in st.session_state:
    st.session_state.processed = False

# Sidebar
with st.sidebar:
    st.markdown("### askeice")
    if st.button("New Chat"):
        st.session_state.page = "upload"
        st.session_state.messages.clear()
        st.session_state.processed = False

# File utilities
def get_file_extension(file):
    return os.path.splitext(file.name)[1].lower()

def is_valid_file(file):
    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    ext = get_file_extension(file)
    if ext not in SUPPORTED_FILE_TYPES:
        return False, "Unsupported file type"
    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"Larger than {MAX_FILE_SIZE_MB}MB"
    if ext == ".pdf":
        try:
            reader = PdfReader(file)
            if len(reader.pages) > MAX_PAGES:
                return False, f"Exceeds {MAX_PAGES} pages"
        except:
            return False, "Failed to read PDF"
    if ext in [".doc", ".docx"]:
        try:
            doc = Document(file)
            if len(doc.paragraphs) > MAX_PAGES:
                return False, f"Exceeds {MAX_PAGES} paragraphs"
        except:
            return False, "Failed to read document"
    return True, "Approved"

def convert_to_pdf(file, ext, save_path):
    temp_file_path = os.path.join(tempfile.gettempdir(), file.name)
    with open(temp_file_path, "wb") as f:
        f.write(file.read())

    pdf_file_path = os.path.splitext(save_path)[0] + ".pdf"

    if ext in [".jpg", ".png"]:
        try:
            image = Image.open(temp_file_path).convert("RGB")
            image.save(pdf_file_path, "PDF", resolution=100.0)
        except Exception as e:
            return False, f"Image to PDF failed: {e}"
    elif ext in [".doc", ".docx"]:
        try:
            word = comtypes.client.CreateObject('Word.Application')
            doc = word.Documents.Open(temp_file_path)
            doc.SaveAs(pdf_file_path, FileFormat=17)
            doc.Close()
            word.Quit()
        except Exception as e:
            return False, f"Word to PDF failed: {e}"
    elif ext == ".pdf":
        shutil.copy(temp_file_path, pdf_file_path)
    else:
        return False, "Unsupported file for conversion"

    return True, pdf_file_path

# Upload Page
if st.session_state.page == "upload":
    st.title("Upload Files")

    uploaded_files = st.file_uploader(
        label="Upload files",
        type=[f.strip('.') for f in SUPPORTED_FILE_TYPES],
        accept_multiple_files=True,
        help="Supported file types: .doc, .docx, .pdf, .png, .jpg\n"
             "Upload limit: Up to 10 files at a time\n"
             "File size limit: 10 MB per file\n"
             "Document length limit: Maximum 150 pages per document",
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
                    pdf_filename = os.path.splitext(file.name)[0] + ".pdf"
                    save_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                    success, result = convert_to_pdf(file, ext, save_path)
                    if success:
                        approved_files.append({"File Name": pdf_filename})
                    else:
                        rejected_files.append({"File Name": file.name, "Reason": result})
                else:
                    rejected_files.append({"File Name": file.name, "Reason": msg})

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

            ocr = st.checkbox("Enable OCR (for images and scanned docs)", value=False)

            if st.button("Start Processing"):
                if not approved_files:
                    st.warning("No approved files to process.")
                else:
                    with st.spinner("Preparing to process..."):
                        time.sleep(1)

                    progress_bar = st.progress(0)
                    for percent in range(0, 101, 10):
                        time.sleep(0.3)
                        progress_bar.progress(percent)

                    st.success("Processing complete!")
                    st.session_state.processed = True

                    if st.session_state.processed:
                        if st.button("Start Interacting"):
                            st.session_state.page = "chat"
                            if not any(msg["role"] == "assistant" and "Hey!" in msg["content"]
                                       for msg in st.session_state.messages):
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": "Hey! How can I help you today? Feel free to ask me anything."
                                })
                            st.rerun()

# Chat Page
elif st.session_state.page == "chat":
    st.title("Ask Anything")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_prompt = st.chat_input("Ask me anything...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            reply = f"You asked: **{user_prompt}**\n\nHere's a placeholder response."
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
