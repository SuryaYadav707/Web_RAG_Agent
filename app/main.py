from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.agent import initialize_rag_agent
import json
import asyncio
from typing import Dict, List
import uuid
import uvicorn
from datetime import datetime


app = FastAPI(title="Website RAG Chat", version="1.0.0")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
active_connections: Dict[str, WebSocket] = {}
chat_history: List[Dict] = []

rag_agent, chroma_indexer = initialize_rag_agent()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        return connection_id
    
    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
    
    async def send_message(self, connection_id: str, message: dict):
        if connection_id in self.active_connections:
            await self.active_connections[connection_id].send_text(json.dumps(message))
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.get("/")
async def get_home():
    """Simple home page with basic chat interface"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Website RAG Chat</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .chat-container { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; border-radius: 5px; }
            .user-message { background: #e3f2fd; text-align: right; }
            .bot-message { background: #f5f5f5; }
            .input-container { display: flex; gap: 10px; }
            input[type="text"] { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Website RAG Chat</h1>
            <div id="chat-container" class="chat-container"></div>
            <div class="input-container">
                <input type="text" id="messageInput" placeholder="Ask me anything about the website..." />
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket("ws://localhost:8000/ws");
            const chatContainer = document.getElementById('chat-container');
            const messageInput = document.getElementById('messageInput');
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                displayMessage(data.message, data.sender);
            };
            
            function displayMessage(message, sender) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}-message`;
                messageDiv.textContent = message;
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            function sendMessage() {
                const message = messageInput.value.trim();
                if (message) {
                    ws.send(JSON.stringify({type: 'message', message: message}));
                    displayMessage(message, 'user');
                    messageInput.value = '';
                }
            }
            
            messageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
        </script>
    </body>
    </html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    
    try:
        # Send welcome message
        await manager.send_message(connection_id, {
            "type": "message",
            "message": "Hello! I'm your website assistant. Ask me anything about the website content!",
            "sender": "bot",
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_message = message_data.get("message", "")
                
                # Process message with RAG agent
                if rag_agent and user_message:
                    try:
                        # Send typing indicator
                        await manager.send_message(connection_id, {
                            "type": "typing",
                            "sender": "bot"
                        })
                        
                        # Get response from RAG agent
                        response =  await rag_agent.ainvoke({"input": user_message})
                        bot_response = response.get('output', 'Sorry, I could not process your request.')
                        
                        # Send bot response
                        await manager.send_message(connection_id, {
                            "type": "message",
                            "message": bot_response,
                            "sender": "bot",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        await manager.send_message(connection_id, {
                            "type": "message",
                            "message": "Sorry, I encountered an error while processing your request.",
                            "sender": "bot",
                            "timestamp": datetime.now().isoformat()
                        })
                        
    except WebSocketDisconnect:
        manager.disconnect(connection_id)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "rag_agent_available": rag_agent is not None,
        "active_connections": len(manager.active_connections)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)