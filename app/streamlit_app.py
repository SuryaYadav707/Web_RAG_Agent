import streamlit as st
import asyncio
import websockets
import json
import threading
import time
from datetime import datetime
from typing import List, Dict
import queue
import sys
import io
import contextlib

# Completely suppress all threading warnings
original_stderr = sys.stderr
sys.stderr = io.StringIO()

# Configure Streamlit page
st.set_page_config(
    page_title="Website RAG Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "websocket_client" not in st.session_state:
    st.session_state.websocket_client = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "message_queue" not in st.session_state:
    st.session_state.message_queue = queue.Queue()
if "websocket_thread" not in st.session_state:
    st.session_state.websocket_thread = None
if "waiting_for_response" not in st.session_state:
    st.session_state.waiting_for_response = False
if "processed_message_ids" not in st.session_state:
    st.session_state.processed_message_ids = set()
if "last_user_message" not in st.session_state:
    st.session_state.last_user_message = ""

# WebSocket configuration
WEBSOCKET_URL = "ws://localhost:8000/ws"

class WebSocketManager:
    def __init__(self):
        self.websocket = None
        self.running = False
    
    @contextlib.contextmanager
    def suppress_warnings(self):
        """Context manager to suppress all warnings and stderr"""
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            yield
        finally:
            sys.stderr = old_stderr
    
    async def connect_and_listen(self, message_queue):
        """Connect to WebSocket and listen for messages"""
        with self.suppress_warnings():
            try:
                self.websocket = await websockets.connect(
                    WEBSOCKET_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                self.running = True
                
                # Signal successful connection
                message_queue.put({"type": "connection", "status": "connected"})
                
                # Listen for messages continuously
                while self.running:
                    try:
                        # Check if connection is still alive (compatible way)
                        if hasattr(self.websocket, 'closed'):
                            if self.websocket.closed:
                                break
                        elif hasattr(self.websocket, 'close_code'):
                            if self.websocket.close_code is not None:
                                break
                        
                        # Wait for incoming messages with longer timeout
                        message = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                        data = json.loads(message)
                        
                        # Debug: print received message
                        print(f"📨 Streamlit received: {data}")
                        
                        # Put message in queue for Streamlit to process
                        message_queue.put(data)
                        
                    except asyncio.TimeoutError:
                        # This is normal - just continue listening
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        print("🔌 WebSocket connection closed")
                        break
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error: {e}")
                        continue
                    except Exception as e:
                        print(f"❌ Error receiving message: {e}")
                        break
                        
            except Exception as e:
                print(f"❌ Connection error: {e}")
                message_queue.put({"type": "connection", "status": "error", "message": str(e)})
            finally:
                self.running = False
                message_queue.put({"type": "connection", "status": "disconnected"})
                print("🔌 WebSocket listener ended")
    
    async def send_message(self, message: str):
        """Send message through WebSocket"""
        with self.suppress_warnings():
            try:
                # Check if connection is still alive (compatible way)
                connection_alive = True
                if hasattr(self.websocket, 'closed'):
                    connection_alive = not self.websocket.closed
                elif hasattr(self.websocket, 'close_code'):
                    connection_alive = self.websocket.close_code is None
                
                if self.websocket and connection_alive:
                    message_data = {
                        "type": "message",
                        "message": message
                    }
                    await self.websocket.send(json.dumps(message_data))
                    print(f"📤 Sent message: {message}")  # Debug line
                else:
                    print("❌ WebSocket not connected")
            except Exception as e:
                print(f"❌ Error sending message: {e}")
    
    def stop(self):
        """Stop the WebSocket connection"""
        self.running = False

def websocket_worker(message_queue):
    """Worker function to run WebSocket in separate thread"""
    def run():
        with contextlib.redirect_stderr(io.StringIO()):
            manager = WebSocketManager()
            st.session_state.websocket_manager = manager
            asyncio.run(manager.connect_and_listen(message_queue))
    
    return run

def process_message_queue():
    """Process messages from the WebSocket queue"""
    messages_processed = False
    
    while not st.session_state.message_queue.empty():
        try:
            data = st.session_state.message_queue.get_nowait()
            print(f"🔄 Processing queue message: {data}")  # Debug line
            
            if data.get("type") == "connection":
                status = data.get("status")
                if status == "connected":
                    st.session_state.connected = True
                    messages_processed = True
                elif status == "disconnected":
                    st.session_state.connected = False
                    messages_processed = True
                elif status == "error":
                    st.session_state.connected = False
                    st.error(f"Connection error: {data.get('message', 'Unknown error')}")
                    messages_processed = True
            
            elif data.get("type") == "message":
                sender = data.get("sender")
                message_content = data.get("message", "")
                timestamp = data.get("timestamp", datetime.now().isoformat())
                
                # Create a unique message ID to prevent duplicates
                message_id = f"{sender}_{message_content[:50]}_{timestamp}"
                
                print(f"👤 Message from {sender}: {message_content}")  # Debug line
                
                if sender == "bot" and message_id not in st.session_state.processed_message_ids:
                    # Only add bot messages that we haven't seen before
                    message = {
                        "role": "assistant",
                        "content": message_content,
                        "timestamp": timestamp,
                        "id": message_id
                    }
                    st.session_state.messages.append(message)
                    st.session_state.processed_message_ids.add(message_id)
                    st.session_state.waiting_for_response = False
                    messages_processed = True
                    print("✅ Bot message added to chat")  # Debug line
                elif sender == "bot":
                    print(f"🔄 Skipping duplicate message: {message_id}")
            
            elif data.get("type") == "typing":
                # Handle typing indicator if needed
                pass
            
        except queue.Empty:
            break
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            break
    
    return messages_processed

async def send_message_to_websocket(message: str):
    """Send message through WebSocket"""
    if hasattr(st.session_state, 'websocket_manager') and st.session_state.websocket_manager:
        try:
            await st.session_state.websocket_manager.send_message(message)
            return True
        except Exception as e:
            st.error(f"Failed to send message: {e}")
            return False
    return False

# Sidebar
with st.sidebar:
    st.title("🤖 RAG Chat Settings")
    
    # Connection status
    if st.session_state.connected:
        status_color = "🟢"
        status_text = "Connected"
    else:
        status_color = "🔴"  
        status_text = "Disconnected"
    
    st.write(f"**Connection Status:** {status_color} {status_text}")
    
    # Show connection details
    if st.session_state.connected:
        st.success("✅ WebSocket Connected")
    else:
        st.info(f"🔗 Ready to connect")
    
    # Connect/Disconnect buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Connect", disabled=st.session_state.connected):
            # Clear any previous connection state
            st.session_state.connected = False
            
            # Start WebSocket client in a separate thread
            worker = websocket_worker(st.session_state.message_queue)
            websocket_thread = threading.Thread(target=worker, daemon=True)
            st.session_state.websocket_thread = websocket_thread
            websocket_thread.start()
            
            st.info("🔄 Connecting...")
            time.sleep(1)
            st.rerun()
    
    with col2:
        if st.button("Disconnect", disabled=not st.session_state.connected):
            if hasattr(st.session_state, 'websocket_manager'):
                st.session_state.websocket_manager.stop()
            st.session_state.connected = False
            st.warning("⚠️ Disconnected")
            st.rerun()
    
    st.divider()
    
    # Chat statistics
    st.write("**Chat Statistics**")
    st.metric("Total Messages", len(st.session_state.messages))
    
    # Clear chat button
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    # Instructions
    st.write("**Instructions**")
    st.write("""
    1. Click 'Connect' to establish WebSocket connection
    2. Type your questions about the website content
    3. The RAG agent will provide relevant answers
    4. Use 'Clear Chat History' to start fresh
    """)

# Main chat interface
st.title("🤖 Website RAG Chat Assistant")
st.write("Ask me anything about the website content!")

# Process any pending messages and check if we need to rerun
should_rerun = process_message_queue()

# Display chat messages
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if "timestamp" in message:
            st.caption(f"Sent at: {message['timestamp']}")

# Chat input
if prompt := st.chat_input("Type your message here...", disabled=not st.session_state.connected):
    if not st.session_state.connected:
        st.error("Please connect to the WebSocket first!")
    else:
        # Check if this is the same message as the last one
        if prompt.strip() != st.session_state.last_user_message:
            # Add user message to chat
            user_message = {
                "role": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.messages.append(user_message)
            st.session_state.last_user_message = prompt.strip()
            st.session_state.waiting_for_response = True
            
            # Send message through WebSocket
            def send_message():
                async def send():
                    with contextlib.redirect_stderr(io.StringIO()):
                        await send_message_to_websocket(prompt)
                
                def run_send():
                    with contextlib.redirect_stderr(io.StringIO()):
                        asyncio.run(send())
                
                thread = threading.Thread(target=run_send, daemon=True)
                thread.start()
            
            send_message()
            
            # Force rerun to show user message immediately
            st.rerun()
        else:
            print(f"🔄 Skipping duplicate user message: {prompt}")

# Auto-refresh to check for new messages
if st.session_state.connected:
    # Check for new messages more frequently
    new_messages = process_message_queue()
    if new_messages:
        print("🔄 New messages found, rerunning...")
        st.rerun()
    
    # Auto refresh every 2 seconds when connected
    time.sleep(2)
    st.rerun()

# Footer
st.divider()
st.caption("Powered by FastAPI WebSocket and Streamlit | RAG Chat Assistant")

# Restore stderr at the end
sys.stderr = original_stderr