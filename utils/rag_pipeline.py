# utils/rag_pipeline.py

import os
import uuid
import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

from config import CHROMA_DB_DIRECTORY, GEMINI_API_KEY


def get_rag_chain(vectorstore):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        google_api_key=GEMINI_API_KEY
    )
    template = """You are an AI assistant for question-answering tasks.
    Use the following pieces of retrieved context to answer the question.
    If you don't know the answer, just say that you don't know.
    If the context provided is empty, state that the information is not available in the document.

    Chat History:
    {chat_history}
    Context:
    {context}
    Question: {question}
    Answer:
    """
    custom_rag_prompt = PromptTemplate.from_template(template)
    rag_chain = (
        {"context": vectorstore.as_retriever(), "question": RunnablePassthrough(), "chat_history": RunnablePassthrough()}
        | custom_rag_prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain


def setup_rag_pipeline(combined_extracted_text, username):
    logging.info("Building RAG pipeline...")
    embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    
    user_chroma_dir = os.path.join(CHROMA_DB_DIRECTORY, username, str(uuid.uuid4()))
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.create_documents([combined_extracted_text])
    
    vectorstore = Chroma.from_documents(texts, embeddings_model, persist_directory=user_chroma_dir)
    logging.info(f"ChromaDB created and persisted to '{user_chroma_dir}'.")
    
    rag_chain = get_rag_chain(vectorstore)
    
    return rag_chain, user_chroma_dir