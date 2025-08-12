

import os
import shutil
import tempfile
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import fitz
import platform
import subprocess
from pathlib import Path

from config import SUPPORTED_FILE_TYPES, MAX_FILE_SIZE_MB, MAX_PAGES, UPLOAD_FOLDER

# Conditional import for comtypes (Windows only)
if platform.system() == "Windows":
    import comtypes.client


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

def is_scanned_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        for page in doc:
            if page.get_text():
                doc.close()
                return False
        doc.close()
        return True
    except Exception:
        return True

def copy_file(source_path, destination_path):
    try:
        with open(source_path, 'rb') as src_file:
            with open(destination_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        return True, "File copied successfully."
    except Exception as e:
        return False, f"File copy failed: {e}"

def convert_to_pdf(uploaded_file_obj, ext, user_upload_dir):
    os.makedirs(user_upload_dir, exist_ok=True)
    
    save_path = os.path.join(user_upload_dir, uploaded_file_obj.name)
    pdf_file_path = os.path.splitext(save_path)[0] + ".pdf"
    
    if os.path.exists(pdf_file_path):
        os.remove(pdf_file_path)

    try:
        with open(save_path, "wb") as f:
            f.write(uploaded_file_obj.read())

        ext = ext.lower()

        if ext in [".jpg", ".jpeg", ".png"]:
            image = Image.open(save_path).convert("RGB")
            image.save(pdf_file_path, "PDF", resolution=100.0)
            return True, pdf_file_path
        if ext == ".pdf":
            return True, save_path

        if ext in [".doc", ".docx"]:
            current_platform = platform.system()
            if current_platform == "Windows":
                try:
                    import pythoncom
                    pythoncom.CoInitialize()

                    word = comtypes.client.CreateObject("Word.Application")
                    word.Visible = False
                    word.DisplayAlerts = False

                    abs_save_path = os.path.abspath(save_path)
                    abs_pdf_file_path = os.path.abspath(pdf_file_path)

                    doc = word.Documents.Open(abs_save_path)
                    doc.SaveAs(abs_pdf_file_path, FileFormat=17)
                    doc.Close(False)
                    word.Quit()
                    pythoncom.CoUninitialize()
                    return True, pdf_file_path

                except Exception as e:
                    try:
                        word.Quit()
                        pythoncom.CoUninitialize()
                    except:
                        pass
                    return False, f"[Windows] Word to PDF failed: {str(e)}. Ensure MS Word is installed."
            else:
                try:
                    output_dir = os.path.dirname(pdf_file_path)
                    command = [
                        "libreoffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", output_dir,
                        save_path
                    ]
                    result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.path.exists(pdf_file_path):
                        return True, pdf_file_path
                    else:
                        return False, f"[Linux/macOS] LibreOffice conversion failed: Output PDF not found. Stderr: {result.stderr.decode()}"
                except FileNotFoundError:
                    return False, "[Linux/macOS] LibreOffice not found."
                except subprocess.CalledProcessError as e:
                    return False, f"[Linux/macOS] LibreOffice conversion failed with error: {e.stderr.decode()}"
                except Exception as e:
                    return False, f"[Linux/macOS] Word to PDF failed: {str(e)}"
        
        return False, f"Unsupported file type for conversion: {ext}"

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        if os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        return False, f"File processing failed: {str(e)}"

