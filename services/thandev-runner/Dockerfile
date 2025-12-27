# Thandev Runner Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and security tools
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    wget \
    git \
    nmap \
    sslscan \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Install Go (required for Nuclei, FFuF, Dalfox)
RUN wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz \
    && rm go1.21.5.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:${PATH}"

# Install security tools
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
    && go install -v github.com/ffuf/ffuf/v2@latest \
    && go install -v github.com/hahwul/dalfox/v2@latest \
    && go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Install SQLMap (Python-based)
RUN git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap \
    && ln -s /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for tool execution
RUN mkdir -p /app/data/jobs /app/data/wordlists \
    && chmod -R 755 /app/data

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Set environment variables
ENV TOOLS_BASE_DIR=/app
ENV DATA_DIR=/app/data
ENV JOBS_DIR=/app/data/jobs
ENV WORDLISTS_DIR=/app/data/wordlists
ENV PATH="/home/app/go/bin:${PATH}"

# Runner is a worker, not an HTTP service
# No port exposed, no healthcheck (monitored via process health)

# Start the worker
CMD ["python", "-m", "app.tasks"]

