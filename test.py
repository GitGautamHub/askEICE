# import pdfplumber
# path = "addhar.pdf"
# with pdfplumber.open(path) as pdf:
#     for i, page in enumerate(pdf.pages):
#         text = page.extract_text()
#         print(f"--- Page {i+1} ---")
#         print(text)


import fitz  # PyMuPDF

path = "addhar.pdf"
doc = fitz.open(path)

for i, page in enumerate(doc):
    text = page.get_text().strip()
    if text:
        print(f"✅ Page {i+1}: Text layer found.")
    else:
        print(f"❌ Page {i+1}: No text layer (likely scanned image).")

doc.close()

