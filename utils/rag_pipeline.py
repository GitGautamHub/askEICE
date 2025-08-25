import os
import uuid
import logging
import torch
import shutil
import time
import google.generativeai as genai
from typing import List

# LlamaIndex imports
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.schema import Document as LlamaIndexDocument
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# LangChain imports
from langchain.schema import Document as LangChainDocument
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings # Import the base class for embeddings

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.docstore.document import Document
from sentence_transformers import CrossEncoder

from config import CHATS_DIR, CHROMA_DB_DIRECTORY, GEMINI_API_KEY
from utils.extraction import get_extracted_text

device = "cuda" if torch.cuda.is_available() else "cpu"

reranker = CrossEncoder('BAAI/bge-reranker-large', device=device)
print("Reranker device:", reranker.model.device)

# --- Wrapper Class for Compatibility ---
class LlamaIndexEmbeddingWrapper(Embeddings):
    """
    A wrapper to make a LlamaIndex embedding model compatible with LangChain's Chroma.
    This class implements the 'embed_documents' and 'embed_query' methods that Chroma expects.
    """
    def __init__(self, llama_index_embed_model: HuggingFaceEmbedding):
        self.llama_index_embed_model = llama_index_embed_model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of documents using the underlying LlamaIndex model.
        """
        # Note: We use get_text_embedding_batch here.
        # It's a more efficient method for batch embedding.
        return self.llama_index_embed_model.get_text_embedding_batch(texts, show_progress=False)

    def embed_query(self, text: str) -> List[float]:
        """
        Embeds a single query using the underlying LlamaIndex model.
        """
        return self.llama_index_embed_model.get_text_embedding(text)

# --- Helper Functions ---
def format_docs_with_metadata(docs):
    """Formats documents with their source metadata clearly marked."""
    return "\n\n".join([
        f"--- DOCUMENT START ---\nSource: {doc.metadata.get('source', 'Unknown')}\nText: {doc.page_content}\n--- DOCUMENT END ---"
        for doc in docs
    ])

def rerank_documents_with_scores(query, docs, score_threshold=0):
    pairs = [(query, doc.page_content) for doc in docs]
    scores = reranker.predict(pairs)
    ranked_results = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    logging.info("--- RETRIEVED CHUNKS FOR DEBUGGING (Reranked) ---")
    for i, (doc, score) in enumerate(ranked_results):
        logging.info(f"Chunk {i+1}: Score={score:.4f} Content='{doc.page_content[:150]}...'")
    logging.info("-------------------------------------")

    # Filter low-confidence docs
    filtered = [(doc, score) for doc, score in ranked_results if score >= score_threshold]

    final_chunks = [doc for doc, score in filtered[:7]]
    return final_chunks

# --- RAG Chain Setup ---
def get_rag_chain(vectorstore):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        google_api_key=GEMINI_API_KEY
    )
    template = """
    You are an AI assistant for question answering. 
    Your goal is to provide clear, detailed, and well-structured answers.

    Rules:
    - Use only the provided documents as context.
    - Always display the information found in the documents, even if it is partial or incomplete.
    - If some part of the answer is missing, clearly say what is missing instead of ignoring the available details.
    - If the documents contain no relevant information at all, state: 
    "The available documents do not contain information about this."
    - Organize the answer in Following parts:
    1. Direct answer (based on what is available)
    2. Supporting evidence from documents
    3. Short conclusion that highlights missing details if any
    - Always list the document names actually used at the end.

    Chat History:
    {chat_history}
    Context:
    {context}
    Question: {question}
    Answer:
    """
    custom_rag_prompt = PromptTemplate.from_template(template)

    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 20})

    # Step 1: String ko dict me todna
    def parse_input(x: str):
        try:
            # assume format: "question, history"
            q, h = x.split(",", 1)
            return {"query": q.strip(), "chat_history": h.strip()}
        except:
            return {"query": x, "chat_history": ""}
    
    preprocessor = RunnableLambda(parse_input)

    # Step 2: Answer chain with reranked docs cached
    def process_docs(x):
        docs = retriever.invoke(x["query"])
        reranked = rerank_documents_with_scores(x["query"], docs)
        return {
            "reranked_docs": reranked,
            "query": x["query"],
            "chat_history": x["chat_history"],
        }

    doc_processor = RunnableLambda(process_docs)

    answer_chain = (
        {
            "context": RunnableLambda(lambda x: format_docs_with_metadata(x["reranked_docs"])),
            "question": RunnableLambda(lambda x: x["query"]),
            "chat_history": RunnableLambda(lambda x: x["chat_history"]),
        }
        | custom_rag_prompt
        | llm
        | StrOutputParser()
    )

    rag_chain = (
        preprocessor
        | doc_processor
        | {
            "answer": answer_chain,
            "sources": RunnableLambda(lambda x: list(set(doc.metadata.get("source", "Unknown") for doc in x["reranked_docs"])))
        }
    )
    return rag_chain

# --- Incremental Update for Admins ---
def update_rag_pipeline(pdf_paths_to_add: List[str], org_name: str):
    """
    Updates an existing RAG pipeline with new documents.
    The documents are chunked using the semantic splitter.

    Args:
        pdf_paths_to_add: A list of file paths to the new PDF documents.
        org_name: The organization name to get the existing vector store.

    Returns:
        The updated RAG chain.
    """
    print("Updating RAG pipeline with new documents...")
    
    # Get the existing vector store
    vectorstore = get_or_create_vectorstore(org_name)
    
    # Use the LlamaIndex version of the embedding model
    llama_embeddings_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
    
    # Initialize the SemanticSplitterNodeParser
    splitter = SemanticSplitterNodeParser(
        buffer_size=2,
        breakpoint_percentile_threshold=95,
        embed_model=llama_embeddings_model,  # The splitter expects the original LlamaIndex model
    )

    new_docs = []
    for pdf_path in pdf_paths_to_add:
        extracted_text = get_extracted_text([pdf_path], org_name)
        
        if not extracted_text.strip():
            print(f"Skipping empty document: {os.path.basename(pdf_path)}")
            continue

        # Create a LlamaIndex Document object
        llama_index_doc = LlamaIndexDocument(text=extracted_text, metadata={"source": os.path.basename(pdf_path)})
        
        # Use the semantic splitter to get nodes (chunks).
        nodes = splitter.get_nodes_from_documents([llama_index_doc])
        
        # Convert LlamaIndex Nodes to LangChain Documents
        for node in nodes:
            lc_doc = LangChainDocument(
                page_content=node.get_content(),
                metadata=node.metadata
            )
            new_docs.append(lc_doc)
            
        print(f"Prepared chunks from '{os.path.basename(pdf_path)}'.")

    # Add new documents to the existing vector store.
    # The embedding model is not needed here as it was passed during initialization.
    if new_docs:
        vectorstore.add_documents(new_docs)
        print(f"Added {len(new_docs)} new chunks to the vector store.")
    else:
        print("No new documents to add.")
    
    print("Vector store updated with new documents.")
    
    # Rebuild and return the RAG chain
    return get_rag_chain(vectorstore)

def get_or_create_vectorstore(org_name):
    """
    Retrieves or creates a shared ChromaDB vector store for an organization.
    """
    chroma_dir = os.path.join(CHROMA_DB_DIRECTORY, org_name)
    os.makedirs(chroma_dir, exist_ok=True)
    
    # Use the LlamaIndex version of the embedding model for compatibility
    llama_embeddings_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
    
    # Use the new wrapper class to make it compatible with LangChain's Chroma API
    embeddings_model = LlamaIndexEmbeddingWrapper(llama_embeddings_model)
    
    # Check if a vector store already exists
    if len(os.listdir(chroma_dir)) > 0 and 'index' in os.listdir(chroma_dir):
        print("Loading existing ChromaDB vector store.")
        # Pass the wrapped embeddings model to the Chroma constructor
        vectorstore = Chroma(persist_directory=chroma_dir, embedding_function=embeddings_model)
    else:
        print("Creating a new ChromaDB vector store.")
        # A dummy document is used for initialization
        dummy_doc = [""]
        # Pass the wrapped embeddings model to from_texts
        vectorstore = Chroma.from_texts(texts=dummy_doc, embedding=embeddings_model, persist_directory=chroma_dir)
        
    return vectorstore

def setup_rag_pipeline(pdf_files: List[str], username: str):
    """
    Sets up a RAG pipeline using a semantic splitter for chunking.

    Args:
        pdf_files: A list of file paths to the PDF documents.
        username: The username to create a unique ChromaDB directory.

    Returns:
        A tuple containing the RAG chain and the ChromaDB directory path.
    """
    logging.info("Building RAG pipeline with Semantic Splitter...")

    # Use the LlamaIndex version of the embedding model
    llama_embeddings_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
    
    # Use the new wrapper class to make it compatible with LangChain's Chroma API
    embeddings_model = LlamaIndexEmbeddingWrapper(llama_embeddings_model)

    # Initialize the SemanticSplitterNodeParser
    # The splitter expects the original LlamaIndex model
    splitter = SemanticSplitterNodeParser(
        buffer_size=2,
        breakpoint_percentile_threshold=95,
        embed_model=llama_embeddings_model,
    )
    
    user_chroma_dir = os.path.join(CHROMA_DB_DIRECTORY, username, str(uuid.uuid4()))
    
    docs = []
    
    for pdf_file_path in pdf_files:
        extracted_text = get_extracted_text([pdf_file_path], username)
        
        if extracted_text.strip():
            llama_index_doc = LlamaIndexDocument(text=extracted_text, metadata={"source": os.path.basename(pdf_file_path)})
            nodes = splitter.get_nodes_from_documents([llama_index_doc])
            
            for node in nodes:
                lc_doc = LangChainDocument(
                    page_content=node.get_content(),
                    metadata=node.metadata
                )
                docs.append(lc_doc)
    
    if not docs:
        raise ValueError("No text was extracted or chunks were created from the PDFs.")

    # Pass the wrapped embeddings model to the Chroma constructor
    vectorstore = Chroma.from_documents(docs, embeddings_model, persist_directory=user_chroma_dir)
    logging.info(f"ChromaDB created and persisted to '{user_chroma_dir}'.")
    
    rag_chain = get_rag_chain(vectorstore)
    
    return rag_chain, user_chroma_dir
