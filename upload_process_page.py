import streamlit as st
import os
import shutil
import time
from config import UPLOAD_FOLDER, SUPPORTED_FILE_TYPES, MAX_FILES, MAX_FILE_SIZE_MB, MAX_PAGES, SHARED_PDFS_PATH
from utils.file_processing import get_file_extension, is_valid_file, convert_to_pdf
from utils.extraction import get_extracted_text
# New imports for incremental RAG pipeline update
from utils.rag_pipeline import update_rag_pipeline, get_rag_chain
from utils.auth import get_user_info


def render_processing_status_page():
    # Is page pe sirf success message dikhao.
    # Upar se jo processing_complete flag set kiya tha, use yahan use karo.
    if st.session_state.get('processing_complete'):
        st.success("Knowledge Base successfully updated! You can now navigate to the chat page.")
        
        st.write(
            """
            You can now start interacting with the knowledge base by clicking on *New Chat*.  

            • Use the *Previous Chats* menu in the sidebar to manage and revisit your earlier conversations.  

            • Explore AskEICE and make the most out of it 🚀
            """
        )
    else:
        st.error("Invalid page access. Please go back to the home page.")
        if st.button("Go to Home"):
            st.session_state.page = "upload"
            st.rerun()

# def render_upload_page():
#     st.title("Knowledge Base Management")
#     st.markdown("Click the button below to process all PDF documents from the shared network drive.")
#     st.info(f"Source Directory: **{SHARED_PDFS_PATH}**")

#     # This button replaces the file uploader and starts the processing from the shared path.
#     if st.button("Start Processing Shared PDFs", key="process_shared_pdfs", use_container_width=True):
#         st.info("Searching for PDFs in the shared directory...")

#         try:
#             # Get all PDF file paths from the network location.
#             pdf_paths_to_process = [
#                 os.path.join(SHARED_PDFS_PATH, f) for f in os.listdir(SHARED_PDFS_PATH)
#                 if f.endswith('.pdf')
#             ]

#             if not pdf_paths_to_process:
#                 st.warning("No PDF files found in the shared directory. Please add files and try again.")
#             else:
#                 st.info(f"Found {len(pdf_paths_to_process)} PDF files. Starting to process...")

#                 user_info = get_user_info(st.session_state['user'])
#                 org_name = user_info['organization']
                
#                 with st.spinner("Processing documents and updating knowledge base..."):
#                     # This function call will now handle all the logic to
#                     # add the documents to the vector store.
#                     st.session_state.rag_chain = update_rag_pipeline(pdf_paths_to_process, org_name)
#                     st.session_state.processing_complete = True
#                     st.success("Knowledge Base successfully updated!")
                    
#                     # Redirect to the chat page after processing
#                     st.session_state.page = "processing_status" 
#                     st.rerun()

#         except FileNotFoundError:
#             st.error(f"Error: The directory '{SHARED_PDFS_PATH}' was not found. Please ensure the path is correct and accessible.")
#         except Exception as e:
#             st.error(f"An error occurred during processing: {e}")
#             st.exception(e)



def render_upload_page():
    st.title("Knowledge Base Management")
    st.info(f"Shared Directory: **{SHARED_PDFS_PATH}**")
    st.markdown("Click the button below to process all PDF documents from the shared network drive.")
    


    uploaded_files = st.file_uploader(
        label="Map your files Here",
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
                # --- NEW LOGIC: Directly process and update RAG here ---
                if st.button("Start Processing", key="start_processing"):
                    st.info("Updating knowledge base... This might take a few moments.")
                    user_info = get_user_info(st.session_state['user'])
                    org_name = user_info['organization']
                    
                    pdf_paths_to_process = [f['PDF Path'] for f in st.session_state.approved_files]

                    with st.spinner("Processing documents and updating knowledge base..."):
                        try:
                            st.session_state.rag_chain = update_rag_pipeline(pdf_paths_to_process, org_name)
                            st.session_state.processing_complete = True
                            st.success("Knowledge Base successfully updated with new documents!")
                            
                            # Clear old uploaded files and session state
                            if os.path.exists(UPLOAD_FOLDER):
                                shutil.rmtree(UPLOAD_FOLDER)
                                os.makedirs(UPLOAD_FOLDER)
                            st.session_state.approved_files = []
                            
                            # Navigate to the chat page
                            st.session_state.page = "processing_status" 
                            st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred during processing: {e}")
                            st.exception(e)
                    