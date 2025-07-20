import subprocess
import sys
import time
import os
import threading

def run_fastapi():
    """Run FastAPI server"""
    # Use Render's PORT environment variable, fallback to 8000 for local
    port = os.getenv('PORT', '8000')
    host = '0.0.0.0'
    
    print(f"🚀 Starting FastAPI on {host}:{port}")
    
    # Change to app directory if it exists
    if os.path.exists('app'):
        os.chdir('app')
    
    cmd = [
        sys.executable, '-m', 'uvicorn', 
        'main:app', 
        '--host', host, 
        '--port', port,
        '--reload'
    ]
    subprocess.run(cmd)

def run_streamlit():
    """Run Streamlit app"""
    # Wait for FastAPI to start
    time.sleep(5)
    
    # For Render, we need to use a different port for Streamlit
    streamlit_port = '8501'
    if os.getenv('RENDER'):
        # On Render, we'll run Streamlit on a different port
        streamlit_port = '8501'
    
    print(f"🎨 Starting Streamlit on port {streamlit_port}")
    
    cmd = [
        sys.executable, '-m', 'streamlit', 'run', 
        'streamlit_app.py',  # Make sure this filename matches
        '--server.port', streamlit_port,
        '--server.address', '0.0.0.0'
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    # Check if we're on Render
    if os.getenv('RENDER'):
        print("🌐 Running on Render")
        print(f"📍 PORT env var: {os.getenv('PORT', 'Not set')}")
    else:
        print("💻 Running locally")
    
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # Start Streamlit in main thread
    run_streamlit()