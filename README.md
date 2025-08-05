# askEice: RAG-Powered Document Q&A Engine 📄

**askEice** is an intelligent, RAG (Retrieval-Augmented Generation) based application that allows users to upload multiple documents and interact with them through a natural language chat interface. It leverages state-of-the-art open-source and cloud-based models to provide accurate, context-aware answers.

---

## ✨ Features

- **Multi-Format Document Ingestion**: Seamlessly handles and converts various document types (`.pdf`, `.doc`, `.docx`, `.png`, `.jpg`) into a unified PDF format for processing. This ensures a consistent pipeline for all uploaded files.
- **Hybrid Text Extraction**: Offers a choice between two powerful text extraction methods to suit your document type:
  - **PDF Plumber**: For fast and accurate extraction from native (searchable) PDF documents.
  - **DocTR (Deep Learning OCR)**: For high-quality Optical Character Recognition on scanned PDFs and images, leveraging **GPU acceleration** for efficiency.
- **Scalable RAG Pipeline**: Implements a robust Retrieval-Augmented Generation (RAG) architecture to handle large volumes of data:
  - **Text Chunking**: Breaks down documents into manageable chunks to optimize LLM performance and manage context windows.
  - **Open-Source Embeddings**: Uses Sentence Transformers (`all-mpnet-base-v2`) for generating high-quality vector embeddings, ensuring semantic search without a dependency on paid embedding APIs.
  - **Persistent Vector Store**: Utilizes **ChromaDB**, an open-source and persistent vector database, to store and quickly retrieve relevant document chunks. This ensures your knowledge base is saved between sessions.
- **Interactive Streamlit Interface**: A user-friendly and modern web application built with Streamlit, featuring:
  - A simple upload page for documents and a choice of extraction method.
  - A clean, state-of-the-art chat interface for natural language queries.
  - Session management to maintain chat history and allow for new, separate conversations.
- **Cloud-Powered Generation**: Uses the **Google Gemini API (`gemini-2.0-flash`)** as the core Large Language Model (LLM) to generate accurate and contextual answers based on the retrieved information.

---

## How to Run

### **Prerequisites**

- Python 3.10+
- A Google Gemini API Key
- A system with an NVIDIA GPU (e.g., GTX 1650) is highly recommended for optimal performance with DocTR.

### **Setup Instructions**

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/GitGautamHub/AskEice.git](https://github.com/GitGautamHub/AskEice.git)
    cd AskEice
    ```

2.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    # For Windows:
    .\venv\Scripts\activate
    # For Linux/macOS:
    source venv/bin/activate
    ```
    
3.  **Install the required dependencies:**
    *(Note: You will need to manually create a `requirements.txt` file from the `pip install` commands in your code, or run them one by one.)*
    ```bash
    pip install -r requirements.txt
    ```
    
4.  **Install PyTorch with CUDA support (Crucial for GPU acceleration):**
    This step is highly dependent on your operating system and CUDA version.
    
    #### **Windows Setup**
    - Ensure your **NVIDIA drivers**, **CUDA Toolkit**, and **cuDNN** are installed and configured. You can check your CUDA version by running `nvcc --version` in a terminal.
    - Visit the [PyTorch website](https://pytorch.org/get-started/locally/) to get the correct command for your specific CUDA version (e.g., for CUDA 12.1, the command would be `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`).
    
    #### **Linux (Arch) Setup**
    - Ensure your **NVIDIA drivers**, **CUDA Toolkit**, and **cuDNN** are installed via `pacman` (e.g., `sudo pacman -S nvidia cuda cudnn`).
    - After installing, verify your CUDA version with `nvcc --version`.
    - Install the compatible PyTorch version using the command from the [PyTorch website](https://pytorch.org/get-started/locally/).
    
5.  **Set your Google Gemini API key as an environment variable:**
    - **For Windows (PowerShell):**
      ```powershell
      $env:GEMINI_API_KEY="your_api_key_here"
      ```
    - **For Linux/macOS:**
      ```bash
      export GEMINI_API_KEY="your_api_key_here"
      ```
    
6.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```

---

## Technologies Used

- **Python**: Core programming language.
- **Streamlit**: For the interactive web interface.
- **DocTR**: For deep learning-based OCR.
- **PDF Plumber**: For text extraction from native PDFs.
- **LangChain**: For building the RAG pipeline.
- **HuggingFace Embeddings**: For creating text embeddings.
- **ChromaDB**: For the persistent vector store.
- **Google Gemini API**: As the primary Large Language Model.
- **PyTorch**: Deep learning framework, essential for GPU acceleration.

---


Feel free to connect, contribute, or open an issue!