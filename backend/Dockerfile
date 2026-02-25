FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create cache directory (will be overridden by Fly volume mount)
RUN mkdir -p /app/cache

# Expose port (Fly.io uses 8080 by default)
EXPOSE 8080

# Start uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
