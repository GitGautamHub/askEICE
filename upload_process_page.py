import streamlit as st
import os
import shutil
import time
from config import UPLOAD_FOLDER, SUPPORTED_FILE_TYPES, MAX_FILES, MAX_FILE_SIZE_MB, MAX_PAGES
from utils.file_processing import get_file_extension, is_valid_file, convert_to_pdf
from utils.extraction import get_extracted_text
from utils.rag_pipeline import setup_rag_pipeline

def render_upload_page():
    st.title("Upload Files")
    st.markdown("Please upload documents (PDF, DOCX, JPG, PNG) to create a knowledge base.")

    uploaded_files = st.file_uploader(
        label="Choose your files",
        type=[f.strip('.') for f in SUPPORTED_FILE_TYPES],
        accept_multiple_files=True,
        key="file_uploader",
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
            
            user_upload_dir = os.path.join(UPLOAD_FOLDER, st.session_state['user'])
            os.makedirs(user_upload_dir, exist_ok=True)
            
            for file in uploaded_files:
                ext = get_file_extension(file)
                valid, msg = is_valid_file(file)

                if valid:
                    file.seek(0)
                    save_path = os.path.join(user_upload_dir, file.name)
                    
                    if ext.lower() == ".pdf":
                        try:
                            with open(save_path, "wb") as f:
                                f.write(file.read())
                            approved_files.append({"File Name": file.name, "PDF Path": save_path})
                        except Exception as e:
                            rejected_files.append({"File Name": file.name, "Reason": f"Failed to save PDF: {str(e)}"})
                    else:
                        success, result = convert_to_pdf(file, ext, user_upload_dir)
                        if success:
                            approved_files.append({"File Name": file.name, "PDF Path": result})
                        else:
                            rejected_files.append({"File Name": file.name, "Reason": result})
                else:
                    rejected_files.append({"File Name": file.name, "Reason": msg})

            st.session_state.approved_files = approved_files
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Approved Files")
                if approved_files:
                    st.dataframe(approved_files, use_container_width=True)
                else:
                    st.info("No files approved yet.")
            with col2:
                st.markdown("### Rejected Files")
                if rejected_files:
                    st.dataframe(rejected_files, use_container_width=True)
                else:
                    st.success("All files approved!")
            
            if st.session_state.approved_files:
                if st.button("Start Processing", key="start_processing"):
                    st.session_state.page = "processing"
                    st.rerun()

def render_processing_page():
    st.title("Processing Documents...")
    st.info("Please wait while your documents are being processed.")
    
    if st.session_state.approved_files:
        with st.status("Initializing...", expanded=True) as status_container:
            try:
                status_container.update(label="Extracting text from documents...")
                pdf_paths_to_process = [f['PDF Path'] for f in st.session_state.approved_files]
                combined_extracted_text = get_extracted_text(pdf_paths_to_process, st.session_state['user'])
                if not combined_extracted_text.strip():
                    raise ValueError("No text was extracted from the PDFs. Please check the files.")
                status_container.update(label="Text Extraction Complete!", state="complete")
                
                status_container.update(label="Building RAG pipeline...")
                rag_chain, chroma_dir = setup_rag_pipeline(combined_extracted_text, st.session_state['user'])
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