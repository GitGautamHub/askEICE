# utils/extraction.py

import os
import time
import glob
import pdfplumber
from pdf2image import convert_from_path
import numpy as np
import torch
from doctr.models import ocr_predictor
from utils.file_processing import is_scanned_pdf
from config import poppler_bin_path
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
from spellchecker import SpellChecker
from rapidfuzz import fuzz, process
import re

global_doctr_model = None
import fitz 


def clean_extracted_text(text):
    # Step 1: Quality check
    if is_text_quality_good(text):
        print("Text quality is good. Skipping cleaning.")
        return text
    else:
        print("Text quality is bad. Cleaning in progress...")

    # Step 2: Cleaning logic
    logging.info(f'time before cleaning: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    spell = SpellChecker()
    lines = text.splitlines()
    corrected_lines = []

    # Updated regex to keep dot-separated initials as one token
    token_pattern = r"[A-Za-z](?:\.[A-Za-z])+\.?|[A-Za-z]+|\d+|[^\w\s]"

    for line in lines:
        words_tokens = re.findall(token_pattern, line)
        unique_words = list(set(w for w in words_tokens if w.isalpha()))
        corrected_words = []

        for word in words_tokens:
            if not word.isalpha():
                # Punctuation or numbers, keep as is
                corrected_words.append(word)
                continue

            if word.lower() in spell:
                corrected_words.append(word)
            else:
                similar_match = process.extractOne(word, unique_words, scorer=fuzz.ratio)
                if (
                    similar_match
                    and similar_match[1] >= 85
                    and similar_match[0].lower() != word.lower()
                ):
                    corrected_words.append(similar_match[0])
                else:
                    corrected_words.append(spell.correction(word) or word)

        # Reconstruct line with proper spaces
        corrected_line = ""
        for i, token in enumerate(corrected_words):
            if i > 0:
                prev_token = corrected_words[i-1]
                if (token.isalnum() or token.isalpha()) and (prev_token.isalnum() or prev_token.isalpha()):
                    corrected_line += " "
            corrected_line += token


        corrected_lines.append(corrected_line)

    logging.info(f'time after cleaning: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    return "\n".join(corrected_lines)


def is_text_quality_good(text):
    """
    Checks if the extracted text has a good linguistic quality using a spell checker.
    Returns True if the text is likely to be valid, False otherwise.
    """
    if not text or len(text.strip()) < 100: # Heuristic: if text is too short, it might be junk
        return False

    spell = SpellChecker()
    words = text.split()
    misspelled = spell.unknown(words)
    
    # Heuristic: if more than 15% of words are unknown, it's likely bad OCR
    if len(misspelled) / len(words) > 0.15:
        return False

    return True



def is_valid_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        return doc.page_count > 0
    except Exception:
        return False
    

def get_extracted_text(pdf_files, org_name):
    combined_text = ""
    global global_doctr_model
    global_doctr_model = None

    for i, pdf_file_path in enumerate(pdf_files):
        pdfplumber_text = extract_text_with_pdfplumber(pdf_file_path)

        if pdfplumber_text and is_text_quality_good(pdfplumber_text):
            logging.info(f"Processing PDF {i+1}/{len(pdf_files)} with PDF Plumber (✓ Quality Check): '{os.path.basename(pdf_file_path)}'")
            combined_text += pdfplumber_text
            # combined_text_clean += clean_extracted_text(combined_text)
        else:
            logging.info(f"Processing PDF {i+1}/{len(pdf_files)} with OCR (✗ Quality Check): '{os.path.basename(pdf_file_path)}'")
            
            if not global_doctr_model:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logging.info(f"Using {device} for DocTR.")
                global_doctr_model = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True).to(device)
            

            combined_text = extract_text_from_pdf_with_doctr(pdf_file_path)

    
    
    return combined_text

def extract_text_with_pdfplumber(pdf_path):
    extracted_text = ""
    total_pages = 0
    blank_pages = 0

    try:
        print(f"🔍 Extracting text from PDF: {os.path.basename(pdf_path)}")
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"📄 Total pages: {total_pages}")

            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    extracted_text += f"\n--- PDF: {os.path.basename(pdf_path)} | Page: {page_idx + 1} ---\n"
                    extracted_text += page_text.strip() + "\n"
                else:
                    print(f"⚠️ Blank or unreadable page: {page_idx + 1}")
                    blank_pages += 1

        print(f"✅ Extraction complete: {total_pages - blank_pages}/{total_pages} pages had readable text.")
    
    except Exception as e:
        print(f"❌ Error during extraction with pdfplumber for '{os.path.basename(pdf_path)}': {e}")
        import traceback
        traceback.print_exc()
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
