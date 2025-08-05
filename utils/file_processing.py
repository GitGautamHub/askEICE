# utils/file_processing.py

import os
import shutil
import tempfile
import comtypes.client
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image

from config import SUPPORTED_FILE_TYPES, MAX_FILE_SIZE_MB, MAX_PAGES, UPLOAD_FOLDER

def get_file_extension(file):
    return os.path.splitext(file.name)[1].lower()

def is_valid_file(file):
    try:
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
            except Exception as e:
                return False, f"Failed to read PDF: {str(e)}"
        elif ext in [".doc", ".docx"]:
            try:
                # Need to read from a temporary path for pydocx to handle docx properly
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(file.read())
                    file.seek(0)
                    tmp_path = tmp.name
                doc = Document(tmp_path)
                if len(doc.paragraphs) > MAX_PAGES:
                    os.remove(tmp_path)
                    return False, f"Exceeds {MAX_PAGES} paragraphs"
                os.remove(tmp_path)
            except Exception as e:
                return False, f"Failed to read Word document: {str(e)}"
        return True, "Approved"
    except Exception as e:
        return False, f"Unhandled validation error: {str(e)}"

def convert_to_pdf(uploaded_file_obj, ext, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    pdf_file_path = os.path.splitext(save_path)[0] + ".pdf"
    
    if os.path.exists(pdf_file_path):
        os.remove(pdf_file_path)

    # Save the uploaded file object directly
    try:
        with open(pdf_file_path, "wb") as f:
            f.write(uploaded_file_obj.read())

        if ext in [".jpg", ".png", ".jpeg"]:
            image = Image.open(pdf_file_path).convert("RGB")
            image.save(pdf_file_path, "PDF", resolution=100.0)
        elif ext in [".doc", ".docx"]:
            word = comtypes.client.CreateObject('Word.Application')
            doc = word.Documents.Open(pdf_file_path)
            doc.SaveAs(pdf_file_path, FileFormat=17)
            doc.Close()
            word.Quit()
        return True, pdf_file_path

    except Exception as e:
        if os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        return False, f"File conversion failed: {e}"