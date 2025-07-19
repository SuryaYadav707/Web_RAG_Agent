# streamlit_app.py
import streamlit as st
import requests
import json
from datetime import datetime
import time

# Configure Streamlit page
st.set_page_config(
    page_title="Website RAG Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Chat message styling */
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .chat-message.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    
    .chat-message.assistant {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        margin-right: 20%;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Connection status styling */
    .status-connected {
        background: linear-gradient(90deg, #56ab2f, #a8e6cf);
        padding: 0.5rem 1rem;
        border-radius: 25px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin: 1rem 0;
    }
    
    .status-disconnected {
        background: linear-gradient(90deg, #ff416c, #ff4b2b);
        padding: 0.5rem 1rem;
        border-radius: 25px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin: 1rem 0;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* File uploader styling */
    .uploadedFile {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Metric styling */
    .metric-card {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 1rem 0;
    }
    
    /* Chat input styling */
    .stChatInput > div > div > input {
        border-radius: 25px;
        border: 2px solid #667eea;
        padding: 0.75rem 1rem;
        font-size: 1rem;
    }
    
    /* Title styling */
    .main-title {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 2rem;
    }
    
    /* Loading animation */
    .loading-dots {
        display: inline-block;
        animation: loading 1.5s infinite;
    }
    
    @keyframes loading {
        0%, 80%, 100% { opacity: 0; }
        40% { opacity: 1; }
    }
    
    /* Typing indicator */
    .typing-indicator {
        background: #f0f0f0;
        padding: 1rem;
        border-radius: 25px;
        margin: 1rem 0;
        font-style: italic;
        color: #666;
    }
    
    /* Success/Error messages */
    .success-message {
        background: linear-gradient(135deg, #56ab2f, #a8e6cf);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
    }
    
    .error-message {
        background: linear-gradient(135deg, #ff416c, #ff4b2b);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False
if "typing" not in st.session_state:
    st.session_state.typing = False

# Configuration
FASTAPI_URL = "http://localhost:8000"

# Sidebar with enhanced design
with st.sidebar:
    st.markdown('<div style="text-align: center; margin-bottom: 2rem;">', unsafe_allow_html=True)
    st.markdown("# 🤖 Website RAG Chat")
    st.markdown("### *Your AI-Powered Website Assistant*")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Connection status with custom styling
    if st.session_state.connected:
        st.markdown('<div class="status-connected">🟢 Connected to Backend</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-disconnected">🔴 Not Connected</div>', unsafe_allow_html=True)
    
    # Connection controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Connect" if not st.session_state.connected else "🔌 Disconnect"):
            if not st.session_state.connected:
                with st.spinner("Connecting..."):
                    try:
                        response = requests.get(f"{FASTAPI_URL}/health", timeout=5)
                        if response.status_code == 200:
                            st.session_state.connected = True
                            st.success("Connected successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Backend not available")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
            else:
                st.session_state.connected = False
                st.session_state.messages = []
                st.info("Disconnected")
                time.sleep(1)
                st.rerun()
    
    with col2:
        if st.button("🧹 Clear Chat"):
            st.session_state.messages = []
            st.success("Chat cleared!")
            time.sleep(1)
            st.rerun()
    
    st.markdown("---")
    
    # Enhanced chat statistics
    st.markdown("### 📊 Chat Statistics")
    
    total_messages = len(st.session_state.messages)
    user_messages = len([m for m in st.session_state.messages if m["role"] == "user"])
    bot_messages = len([m for m in st.session_state.messages if m["role"] == "assistant"])
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💬 Total", total_messages)
    with col2:
        st.metric("🤖 Bot", bot_messages)
    
    st.markdown("---")
    
    # Enhanced data upload section
    st.markdown("### 📤 Upload Data")
    st.markdown("*Upload JSON data to enhance the knowledge base*")
    
    uploaded_file = st.file_uploader(
        "Choose a JSON file", 
        type=['json'],
        help="Upload your website data in JSON format"
    )
    
    if uploaded_file is not None:
        try:
            json_data = json.load(uploaded_file)
            
            st.success(f"✅ File loaded: {len(json_data)} entries")
            
            if st.button("🚀 Upload to Database"):
                with st.spinner("Processing data..."):
                    try:
                        response = requests.post(
                            f"{FASTAPI_URL}/upload-data",
                            json={"json_data": json_data},
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.balloons()
                            st.success(f"🎉 {result.get('message', 'Success')}")
                            st.info(f"Processed {result.get('entries_processed', 0)} entries")
                        else:
                            st.error("❌ Failed to upload data")
                    except Exception as e:
                        st.error(f"❌ Upload error: {e}")
                        
        except Exception as e:
            st.error(f"❌ Error processing file: {e}")
    
    st.markdown("---")
    
    # Help section
    st.markdown("### ❓ Help")
    with st.expander("How to use"):
        st.markdown("""
        1. **Connect**: Click the connect button to establish connection with the backend
        2. **Upload Data**: Use the file uploader to add new website data
        3. **Chat**: Ask questions about the website content
        4. **Clear**: Use the clear button to reset the conversation
        """)
    
    with st.expander("Tips"):
        st.markdown("""
        - Be specific in your questions for better responses
        - Upload comprehensive JSON data for better results
        - The AI can answer questions about website content, products, services, etc.
        """)

# Main chat interface with enhanced design
st.markdown('<h1 class="main-title">💬 Website RAG Assistant</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem; margin-bottom: 2rem;">Ask me anything about the website content and I\'ll help you find the information you need!</p>', unsafe_allow_html=True)

# Chat container
chat_container = st.container()

with chat_container:
    # Display chat messages with enhanced styling
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
            st.markdown(message["content"])
            if "timestamp" in message:
                st.caption(f"🕐 {message['timestamp']}")
    
    # Show typing indicator
    if st.session_state.typing:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("*Thinking...*")

# Enhanced chat input
if prompt := st.chat_input("💭 Ask me anything about the website...", key="chat_input"):
    if not st.session_state.connected:
        st.error("🔌 Please connect to the backend first!")
    else:
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        # Show typing indicator
        st.session_state.typing = True
        st.rerun()

# Process the latest message if typing
if st.session_state.typing and st.session_state.messages:
    last_message = st.session_state.messages[-1]
    if last_message["role"] == "user":
        with st.spinner("🤖 AI is thinking..."):
            try:
                # Make API call to your FastAPI backend
                response = requests.post(
                    f"{FASTAPI_URL}/chat",
                    json={"message": last_message["content"]},
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    bot_response = result.get("response", "No response received")
                else:
                    bot_response = "Sorry, I couldn't process your request. Please try again."
                
            except Exception as e:
                bot_response = f"❌ Error: {str(e)}"
            
            # Add bot response to chat
            st.session_state.messages.append({
                "role": "assistant", 
                "content": bot_response,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
            # Reset typing indicator
            st.session_state.typing = False
            st.rerun()

# Enhanced footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-top: 2rem;">
    <h3 style="color: white; margin-bottom: 1rem;">🚀 Built with Modern Technology</h3>
    <p style="color: white; margin: 0;">Powered by <strong>Streamlit 🎈</strong> and <strong>FastAPI ⚡</strong></p>
    <p style="color: white; margin: 0; font-size: 0.9rem; opacity: 0.8;">AI-powered website assistant for better user experience</p>
</div>
""", unsafe_allow_html=True)