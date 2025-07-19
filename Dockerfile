# Use Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy only requirements first (for Docker caching)
COPY requirements.txt .

ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_RETRIES=10

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project into container
COPY . .

# Expose both ports
EXPOSE 8000
EXPOSE 8501

# Run both FastAPI and Streamlit
CMD ["python", "run_servers.py"]
