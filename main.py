import streamlit as st
import os
import time
import uuid  # <-- Added missing import
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
from fpdf import FPDF
import comtypes.client  # For Word to PDF conversion
import shutil
import tempfile
import glob
import pdfplumber
from pdf2image import convert_from_path
import numpy as np
import torch
from doctr.models import ocr_predictor
import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

# --- Suppress LangChain warnings for a cleaner Streamlit app ---
logging.getLogger("langchain.text_splitter").setLevel(logging.ERROR)
logging.getLogger("langchain.embeddings").setLevel(logging.ERROR)
logging.getLogger("langchain.vectorstores").setLevel(logging.ERROR)
logging.getLogger("langchain.chains").setLevel(logging.ERROR)

# --- Constants & Globals ---
CHROMA_DB_DIRECTORY = "./chroma_db_data"
UPLOAD_FOLDER = "./Documents"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
poppler_bin_path = r"C:\Users\Gautam kumar\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"

global_doctr_model = None

# --- File Constants ---
SUPPORTED_FILE_TYPES = [".doc", ".docx", ".pdf", ".png", ".jpg"]
MAX_FILE_SIZE_MB = 10
MAX_FILES = 10
MAX_PAGES = 150

# --- File and conversion utilities ---
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
    
    if os.path.exists(pdf_file_path):
        os.remove(pdf_file_path)

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
    
    os.remove(temp_file_path)
    return True, pdf_file_path

# --- Extraction Functions ---
def get_extracted_text(pdf_files, use_ocr):
    combined_text = ""
    if use_ocr:
        global global_doctr_model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            print(f"GPU found: {torch.cuda.get_device_name(0)}. Using GPU for DocTR.")
        else:
            print("No GPU found or CUDA not configured. Using CPU for DocTR. This will be slower.")
        print("Loading DocTR OCR model. This may take a moment...")
        global_doctr_model = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True).to(device)
        print("DocTR OCR model loaded.")
        for i, pdf_file_path in enumerate(pdf_files):
            print(f"\nProcessing PDF {i+1}/{len(pdf_files)} with OCR: '{os.path.basename(pdf_file_path)}'")
            combined_text += extract_text_from_pdf_with_doctr(pdf_file_path)
    else:
        for i, pdf_file_path in enumerate(pdf_files):
            print(f"\nProcessing PDF {i+1}/{len(pdf_files)} with pdfplumber: '{os.path.basename(pdf_file_path)}'")
            combined_text += extract_text_with_pdfplumber(pdf_file_path)
    return combined_text

def extract_text_with_pdfplumber(pdf_path):
    extracted_text = ""
    try:
        print(f"  Extracting text from PDF '{os.path.basename(pdf_path)}' using pdfplumber...")
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_text += f"\n--- PDF: {os.path.basename(pdf_path)} | Page: {page_idx + 1} ---\n"
                    extracted_text += page_text + "\n"
        print(f"  pdfplumber extraction for '{os.path.basename(pdf_path)}' completed.")
    except Exception as e:
        print(f"  An error occurred during pdfplumber extraction for '{os.path.basename(pdf_path)}': {e}")
        extracted_text = ""
    return extracted_text

def extract_text_from_pdf_with_doctr(pdf_path):
    extracted_pdf_text = ""
    try:
        print(f"  Converting PDF '{os.path.basename(pdf_path)}' to images (DPI 300)...")
        conversion_start_time = time.time()
        if os.name == 'nt' and poppler_bin_path:
            images_pil = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_bin_path)
        else:
            images_pil = convert_from_path(pdf_path, dpi=300)
        conversion_end_time = time.time()
        print(f"  PDF conversion for '{os.path.basename(pdf_path)}' completed in {conversion_end_time - conversion_start_time:.2f} seconds.")

        if not images_pil:
            print(f"  No pages found in '{os.path.basename(pdf_path)}' or conversion failed. Skipping.")
            return ""

        print(f"  Loaded {len(images_pil)} pages from '{os.path.basename(pdf_path)}'.")
        all_pages_np = [np.array(img) for img in images_pil]

        print(f"  Processing {len(all_pages_np)} pages with DocTR...")
        ocr_start_time = time.time()
        global_doctr_model
        result = global_doctr_model(all_pages_np)
        ocr_end_time = time.time()
        print(f"  DocTR OCR processing for '{os.path.basename(pdf_path)}' completed in {ocr_end_time - ocr_start_time:.2f} seconds.")

        for page_idx, page in enumerate(result.pages):
            extracted_pdf_text += f"\n--- PDF: {os.path.basename(pdf_path)} | Page: {page_idx + 1} ---\n"
            for block in page.blocks:
                for line in block.lines:
                    line_text = " ".join([word.value for word in line.words])
                    extracted_pdf_text += line_text + "\n"

        return extracted_pdf_text

    except Exception as e:
        print(f"  An error occurred during DocTR processing for '{os.path.basename(pdf_path)}': {e}")
        import traceback
        traceback.print_exc()
        return ""

def get_rag_chain(vectorstore):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    template = """You are an AI assistant for question-answering tasks.
    Use the following pieces of retrieved context to answer the question.
    If you don't know the answer, just say that you don't know.
    If the context provided is empty, state that the information is not available in the document.

    Context:
    {context}
    Question: {question}
    Answer:
    """
    custom_rag_prompt = PromptTemplate.from_template(template)
    rag_chain = (
        {"context": vectorstore.as_retriever(), "question": RunnablePassthrough()}
        | custom_rag_prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain

# --- Streamlit UI and Logic ---
st.set_page_config(page_title="AskEice - Document QA", layout="wide")

# Session state initialization
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


with st.sidebar:
    st.markdown("## askEICE")
    if st.button("New Chat", key="new_chat"):
        if st.session_state.page == "chat" and st.session_state.current_chat_title:
            st.session_state.chat_history_titles.append(st.session_state.current_chat_title)
        
        st.session_state.page = "upload"
        st.session_state.messages.clear()
        st.session_state.approved_files.clear()
        st.session_state.rag_chain = None
        st.session_state.current_chat_title = None
        
        # if os.path.exists(UPLOAD_FOLDER):
        #     shutil.rmtree(UPLOAD_FOLDER)
        #     os.makedirs(UPLOAD_FOLDER)
        # if st.session_state.chroma_dir and os.path.exists(st.session_state.chroma_dir):
        #     shutil.rmtree(st.session_state.chroma_dir)
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
                    pdf_filename = os.path.splitext(file.name)[0] + ".pdf"
                    save_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                    success, result = convert_to_pdf(file, ext, save_path)
                    if success:
                        approved_files.append({"File Name": pdf_filename, "PDF Path": result})
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
        with st.spinner("Preparing to process..."):
            progress_bar = st.progress(0)
            
            try:
                # Step 1: Extract text
                with st.status("Extracting text from documents...", expanded=True) as status:
                    pdf_paths_to_process = [f['PDF Path'] for f in st.session_state.approved_files]
                    combined_extracted_text = get_extracted_text(pdf_paths_to_process, use_ocr=st.session_state.use_ocr_choice)
                    status.update(label="Text Extraction Complete!", state="complete")
                    progress_bar.progress(33)
                
                if not combined_extracted_text.strip():
                    st.error("No text was extracted from the PDFs. Please check the files.")
                    st.stop()
                
                # Step 2: RAG Setup
                with st.status("Building RAG pipeline...", expanded=True) as status:
                    embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
                    st.session_state.chroma_dir = os.path.join("./chroma_db_data", str(uuid.uuid4()))
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                    texts = text_splitter.create_documents([combined_extracted_text])
                    vectorstore = Chroma.from_documents(texts, embeddings_model, persist_directory=st.session_state.chroma_dir)
                    st.session_state['rag_chain'] = get_rag_chain(vectorstore)
                    status.update(label="RAG Pipeline Built!", state="complete")
                    progress_bar.progress(66)
                
                progress_bar.progress(100)
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