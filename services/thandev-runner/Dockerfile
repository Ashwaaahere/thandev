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
    ca-certificates \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Go (required for Nuclei, FFuF, Dalfox)
RUN wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz \
    && rm go1.21.5.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:${PATH}"

# Install security tools (pinned versions for reproducibility)
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@v3.1.0 \
    && go install -v github.com/ffuf/ffuf/v2@v2.1.0 \
    && go install -v github.com/hahwul/dalfox/v2@v2.9.2 \
    && go install -v github.com/projectdiscovery/httpx/cmd/httpx@v1.3.7

# Install SQLMap (Python-based)
RUN git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap \
    && ln -s /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (includes wordlists if present)
COPY . .

# Move wordlists to final location if they exist
# wordlists are copied via COPY . . above, now move to /opt/thandev/wordlists
RUN mkdir -p /opt/thandev/wordlists && \
    if [ -d wordlists ] && [ "$(ls -A wordlists 2>/dev/null)" ]; then \
        cp -r wordlists/* /opt/thandev/wordlists/ 2>/dev/null || true; \
    fi

# Copy and set permissions for startup script (before switching user)
COPY check_tools.sh /app/check_tools.sh
RUN chmod +x /app/check_tools.sh

# Create directories for tool execution
RUN mkdir -p /app/data/jobs \
    && chmod -R 755 /app/data \
    && chmod -R 755 /opt/thandev/wordlists

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Set environment variables
ENV TOOLS_BASE_DIR=/app
ENV DATA_DIR=/app/data
ENV JOBS_DIR=/app/data/jobs
ENV WORDLISTS_DIR=/opt/thandev/wordlists
ENV PATH="/home/app/go/bin:/usr/local/go/bin:${PATH}"

# Runner is a worker, not an HTTP service
# No port exposed, no healthcheck (monitored via process health)

# Start the worker (run tool checks first, then start worker)
CMD ["/bin/bash", "-c", "/app/check_tools.sh && python -m app.tasks"]

