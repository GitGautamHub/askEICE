# AskEice: RAG-Powered Document Q&A Engine 📄

**AskEice** is an intelligent, RAG (Retrieval-Augmented Generation) based application that allows users to upload multiple documents and interact with them through a natural language chat interface. It leverages state-of-the-art open-source and cloud-based models to provide accurate, context-aware answers.

---

## Features

### Multi-Format Document Ingestion
Seamlessly handles and converts various document types (`.pdf`, `.doc`, `.docx`, `.png`, `.jpg`) into a unified PDF format for processing. This ensures a consistent pipeline for all uploaded files.

### Hybrid Text Extraction
Offers a choice between two powerful text extraction methods to suit your document type:

- **PDF Plumber**: For fast and accurate extraction from native (searchable) PDF documents.
- **DocTR (Deep Learning OCR)**: For high-quality Optical Character Recognition on scanned PDFs and images, leveraging GPU acceleration for efficiency.

### Scalable RAG Pipeline
Implements a robust Retrieval-Augmented Generation (RAG) architecture to handle large volumes of data:

- **Text Chunking**: Breaks down documents into manageable chunks to optimize LLM performance and manage context windows.
- **Open-Source Embeddings**: Uses Sentence Transformers (`all-mpnet-base-v2`) for generating high-quality vector embeddings, ensuring semantic search without a dependency on paid embedding APIs.
- **Persistent Vector Store**: Utilizes ChromaDB, an open-source and persistent vector database, to store and quickly retrieve relevant document chunks. This ensures your knowledge base is saved between sessions.

### Interactive Streamlit Interface
A user-friendly and modern web application built with Streamlit, featuring:

- A simple upload page for documents and a choice of extraction method.
- A clean, state-of-the-art chat interface for natural language queries.
- Session management to maintain chat history and allow for new, separate conversations.

### Cloud-Powered Generation
Uses the **Google Gemini API (`gemini-2.0-flash`)** as the core Large Language Model (LLM) to generate accurate and contextual answers based on the retrieved information.

---

### Prerequisites
- Python 3.10+
- A Google Gemini API Key
- A system with an NVIDIA GPU (e.g., GTX 1650) is highly recommended for optimal performance with DocTR.
