import streamlit as st
from utils.auth import rename_chat

# --- Custom CSS for a clean and modern look ---
st.markdown("""
<style>
    /* Main title styling */
    .title-text {
        font-size: 2.2em;
        font-weight: 600;
        color: #333;
        text-align: center;
        margin-top: -20px;
        margin-bottom: 30px;
    }
    
    /* Overall styling for the chat container */
    .stChatMessages {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-bottom: 70px; /* Space for the input box */
    }

    /* User message bubble */
    div[data-testid="stChatMessage"][data-author="user"] {
        background-color: #e6f7ff; /* Light blue */
        border-radius: 20px;
        padding: 12px 18px;
        max-width: 75%;
        margin-left: auto;
        word-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        font-size: 16px;
        border-bottom-right-radius: 5px; /* Little notch effect */
    }

    /* Assistant message bubble */
    div[data-testid="stChatMessage"][data-author="assistant"] {
        background-color: #f0f2f5; /* Light grey */
        border-radius: 20px;
        padding: 12px 18px;
        max-width: 75%;
        word-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        font-size: 16px;
        border-bottom-left-radius: 5px; /* Little notch effect */
    }
    
    /* Fix for Streamlit's icon background */
    div[data-testid="stChatMessage"] div[data-testid="stChatMessageAvatar"] {
        background-color: transparent !important;
    }
    
    /* Input box styling to look more integrated */
    .stChatInput > div > div > div {
        border-radius: 25px;
        border: 1px solid #ccc;
        padding: 5px 15px;
        background-color: #fff;
    }
    .stChatInput button {
        background-color: #007bff;
        color: white;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
    }
</style>
""", unsafe_allow_html=True)


def render_chat_page():
    # --- Title Section with Rename Feature ---
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.markdown(f'<h1 class="title-text">{st.session_state.get("current_chat_title", "Ask Anything")}</h1>', unsafe_allow_html=True)
    with col2:
        if st.button("✏️", key="rename_button"):
            st.session_state.rename_mode = not st.session_state.get("rename_mode", False)

    # If rename mode is active, show the input field
    if st.session_state.get("rename_mode", False):
        new_title = st.text_input("Enter new chat title:", value=st.session_state.current_chat_title)
        if st.button("Save", key="save_rename_button"):
            rename_chat(st.session_state.current_chat_file, new_title)
            st.session_state.current_chat_title = new_title
            st.session_state.rename_mode = False
            st.rerun()
    
    # Display chat messages directly using st.chat_message
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input logic
    user_prompt = st.chat_input("Ask me anything...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        
        # Display the user's message immediately
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            if st.session_state.rag_chain:
                try:
                    with st.spinner("Thinking..."):
                        chat_history = st.session_state.messages[-5:]
                        
                        formatted_history = "\n".join([
                            f"Human: {msg['content']}" if msg['role'] == 'user' else f"AI: {msg['content']}"
                            for msg in chat_history
                        ])
                        
                        response = st.session_state.rag_chain.invoke(
                            user_prompt, chat_history=formatted_history
                        )

                    # Display the assistant's response
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"An error occurred during interaction: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"An error occurred: {e}"})
            else:
                st.warning("The RAG pipeline is not ready. Please go back and process documents.")
                st.session_state.page = "upload"
                st.rerun()