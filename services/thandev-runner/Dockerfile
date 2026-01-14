FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc curl wget git nmap sslscan dnsutils ca-certificates jq \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/* \
    && mv /usr/bin/chromium /usr/bin/chromium-orig \
    && echo '#!/bin/bash\n/usr/bin/chromium-orig --no-sandbox "$@"' > /usr/bin/chromium \
    && chmod +x /usr/bin/chromium \
    && ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/bin/chromium /usr/bin/chromium-browser

# Install Go
RUN wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz \
    && rm go1.21.5.linux-amd64.tar.gz

# Set Go environment variables
ENV GOROOT=/usr/local/go
ENV GOBIN=/usr/local/bin
ENV GOPATH=/tmp/go
ENV PATH="/usr/local/bin:/usr/local/go/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Verify Go installation
RUN /usr/local/go/bin/go version || (echo "ERROR: Go installation failed" && exit 1)

# Python deps first (so they can't overwrite Go binaries later)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install SQLMap
RUN git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap \
    && ln -s /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap

# Now install Go tools AFTER pip (so Go binaries take final ownership)
# CRITICAL: Use full path to go binary and verify each installation
RUN rm -f /usr/local/bin/httpx || true \
    && /usr/local/go/bin/go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
    && /usr/local/go/bin/go install -v github.com/ffuf/ffuf/v2@v2.1.0 \
    && /usr/local/go/bin/go install -v github.com/hahwul/dalfox/v2@latest \
    && /usr/local/go/bin/go install -v github.com/projectdiscovery/httpx/cmd/httpx@v1.3.7 \
    && chmod +x /usr/local/bin/nuclei /usr/local/bin/ffuf /usr/local/bin/dalfox /usr/local/bin/httpx \
    && /usr/local/bin/nuclei -version || (echo "ERROR: nuclei installation failed" && exit 1) \
    && /usr/local/bin/httpx -version || (echo "ERROR: httpx installation failed" && exit 1) \
    && /usr/local/bin/dalfox version || (echo "ERROR: dalfox installation failed" && exit 1)

# Catalog
RUN mkdir -p /app/catalog
COPY catalog/catalog.json /app/catalog/catalog.json
ENV TOOL_CATALOG_PATH=/app/catalog/catalog.json

# App code
COPY . .

# Wordlists
RUN mkdir -p /opt/thandev/wordlists && \
    if [ -d wordlists ] && [ "$(ls -A wordlists 2>/dev/null)" ]; then \
    cp -r wordlists/* /opt/thandev/wordlists/ 2>/dev/null || true; \
    fi

COPY check_tools.sh /app/check_tools.sh
RUN chmod +x /app/check_tools.sh

RUN mkdir -p /app/data/jobs \
    && chmod -R 755 /app/data \
    && chmod -R 755 /opt/thandev/wordlists

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app /opt/thandev

USER app
ENV HOME=/home/app

ENV TOOLS_BASE_DIR=/app
ENV DATA_DIR=/app/data
ENV JOBS_DIR=/app/data/jobs
ENV WORDLISTS_DIR=/opt/thandev/wordlists
ENV PATH="/usr/local/bin:/usr/local/go/bin:/usr/sbin:/usr/bin:/sbin:/bin"

CMD ["/bin/bash", "-c", "/app/check_tools.sh && python -m app.tasks"]
