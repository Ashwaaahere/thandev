# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    locust==2.17.0 \
    requests==2.32.3 \
    google-cloud-storage==2.10.0

# Copy the locust file and runner script
COPY locustfile.py .
COPY run_locust.py .

# Make the runner script executable
RUN chmod +x run_locust.py

# Set the entrypoint
ENTRYPOINT ["python", "run_locust.py"]


