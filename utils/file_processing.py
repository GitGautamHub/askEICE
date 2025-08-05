# utils/file_processing.py

import os
import shutil
import tempfile
import comtypes.client
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import fitz
import platform
import subprocess

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

def is_scanned_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        i=0;
        j=0;
        for page in doc:
            i=i+1
            if page.get_text():
                doc.close()
                print(f"This is not a scanned PDF.{i}")
                return False # Not a scanned PDF
        doc.close()
        j=j+1
        print(f"This is a scanned PDF.{j}")
        return True
    except Exception:
        return True 


def copy_file(source_path, destination_path):
    """
    Copies a file from source_path to destination_path.
    """
    try:
        with open(source_path, 'rb') as src_file:
            with open(destination_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        return True, "File copied successfully."
    except Exception as e:
        return False, f"File copy failed: {e}"

def convert_to_pdf(uploaded_file_obj, ext, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    base_path = os.path.splitext(save_path)[0]
    pdf_file_path = base_path + ".pdf"

    if os.path.exists(pdf_file_path):
        os.remove(pdf_file_path)

    try:
        # Save uploaded file temporarily
        with open(save_path, "wb") as f:
            f.write(uploaded_file_obj.read())

        ext = ext.lower()

        # Convert images to PDF using PIL (cross-platform)
        if ext in [".jpg", ".jpeg", ".png"]:
            image = Image.open(save_path).convert("RGB")
            image.save(pdf_file_path, "PDF", resolution=100.0)
            return True, pdf_file_path

        # If already PDF
        if ext == ".pdf":
            return True, save_path

        # Word Docs (.doc/.docx)
        if ext in [".doc", ".docx"]:
            current_platform = platform.system()

            if current_platform == "Windows":
                # --- Windows logic using comtypes ---
                try:
                    import pythoncom
                    import comtypes.client

                    pythoncom.CoInitialize()
                    word = comtypes.client.CreateObject("Word.Application")
                    word.Visible = False
                    doc = word.Documents.Open(save_path)
                    doc.SaveAs(pdf_file_path, FileFormat=17)  # 17 = PDF
                    doc.Close()
                    word.Quit()
                    pythoncom.CoUninitialize()
                    return True, pdf_file_path

                except Exception as e:
                    try:
                        word.Quit()
                        pythoncom.CoUninitialize()
                    except:
                        pass
                    return False, f"[Windows] Word to PDF failed: {str(e)}"

            else:
                # --- Linux/macOS logic using libreoffice ---
                try:
                    output_dir = os.path.dirname(save_path)
                    command = [
                        "libreoffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", output_dir,
                        save_path
                    ]
                    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    converted_pdf_path = str(Path(save_path).with_suffix(".pdf"))
                    return True, converted_pdf_path

                except subprocess.CalledProcessError as e:
                    return False, f"[Linux/macOS] LibreOffice conversion failed: {e.stderr.decode()}"

        # Unsupported
        return False, f"Unsupported file type: {ext}"

    except Exception as e:
        if os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        return False, f"File conversion failed: {str(e)}"
