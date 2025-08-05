# utils/extraction.py

import os
import time
import glob
import pdfplumber
from pdf2image import convert_from_path
import numpy as np
import torch
from doctr.models import ocr_predictor

from config import poppler_bin_path
import logging

global_doctr_model = None

def get_extracted_text(pdf_files, use_ocr):
    combined_text = ""
    if use_ocr:
        global global_doctr_model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Using {device} for DocTR.")
        global_doctr_model = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True).to(device)
        for i, pdf_file_path in enumerate(pdf_files):
            logging.info(f"Processing PDF {i+1}/{len(pdf_files)} with OCR: '{os.path.basename(pdf_file_path)}'")
            combined_text += extract_text_from_pdf_with_doctr(pdf_file_path)
    else:
        for i, pdf_file_path in enumerate(pdf_files):
            logging.info(f"Processing PDF {i+1}/{len(pdf_files)} with pdfplumber: '{os.path.basename(pdf_file_path)}'")
            combined_text += extract_text_with_pdfplumber(pdf_file_path)
    return combined_text

def extract_text_with_pdfplumber(pdf_path):
    extracted_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_text += f"\n--- PDF: {os.path.basename(pdf_path)} | Page: {page_idx + 1} ---\n"
                    extracted_text += page_text + "\n"
    except Exception as e:
        logging.error(f"Error during pdfplumber extraction for '{os.path.basename(pdf_path)}': {e}")
        extracted_text = ""
    return extracted_text

def extract_text_from_pdf_with_doctr(pdf_path):
    extracted_pdf_text = ""
    try:
        if os.name == 'nt' and poppler_bin_path:
            images_pil = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_bin_path)
        else:
            images_pil = convert_from_path(pdf_path, dpi=300)

        if not images_pil:
            return ""

        all_pages_np = [np.array(img) for img in images_pil]
        global global_doctr_model
        result = global_doctr_model(all_pages_np)
        
        for page_idx, page in enumerate(result.pages):
            extracted_pdf_text += f"\n--- PDF: {os.path.basename(pdf_path)} | Page: {page_idx + 1} ---\n"
            for block in page.blocks:
                for line in block.lines:
                    line_text = " ".join([word.value for word in line.words])
                    extracted_pdf_text += line_text + "\n"
        return extracted_pdf_text
    except Exception as e:
        logging.error(f"Error during DocTR processing for '{os.path.basename(pdf_path)}': {e}")
        import traceback
        return ""