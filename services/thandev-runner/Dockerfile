FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc curl wget git nmap sslscan dnsutils ca-certificates jq \
    && rm -rf /var/lib/apt/lists/*

# Install Go
RUN wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz \
    && rm go1.21.5.linux-amd64.tar.gz

ENV GOBIN=/usr/local/bin
ENV GOPATH=/tmp/go
ENV PATH="/usr/local/bin:/usr/local/go/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Python deps first (so they can't overwrite Go binaries later)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install SQLMap
RUN git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap \
    && ln -s /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap

# Now install Go tools AFTER pip (so Go binaries take final ownership)
RUN rm -f /usr/local/bin/httpx || true \
 && go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@v3.1.0 \
 && go install -v github.com/ffuf/ffuf/v2@v2.1.0 \
 && go install -v github.com/hahwul/dalfox/v2@v2.9.2 \
 && go install -v github.com/projectdiscovery/httpx/cmd/httpx@v1.3.7 \
 && chmod +x /usr/local/bin/nuclei /usr/local/bin/ffuf /usr/local/bin/dalfox /usr/local/bin/httpx

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
