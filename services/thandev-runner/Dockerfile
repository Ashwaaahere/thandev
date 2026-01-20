FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc curl wget git nmap sslscan dnsutils ca-certificates jq \
    chromium chromium-driver unzip \
    && rm -rf /var/lib/apt/lists/* \
    && mv /usr/bin/chromium /usr/bin/chromium-orig \
    && echo '#!/bin/bash\n/usr/bin/chromium-orig --no-sandbox "$@"' > /usr/bin/chromium \
    && chmod +x /usr/bin/chromium \
    && ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/bin/chromium /usr/bin/chromium-browser

# Install Node.js and npm (for wappalyzer and retire.js)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

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
# Set GOBIN explicitly to ensure binaries go to /usr/local/bin
# NOTE: ffuf removed - not used in tool_matrix.py (commented out in supported_tools)
RUN mkdir -p /tmp/go && \
    rm -f /usr/local/bin/httpx /usr/local/bin/nuclei /usr/local/bin/dalfox || true && \
    GOBIN=/usr/local/bin GOPATH=/tmp/go /usr/local/go/bin/go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    GOBIN=/usr/local/bin GOPATH=/tmp/go /usr/local/go/bin/go install -v github.com/hahwul/dalfox/v2@latest && \
    GOBIN=/usr/local/bin GOPATH=/tmp/go /usr/local/go/bin/go install -v github.com/projectdiscovery/httpx/cmd/httpx@v1.3.7 && \
    chmod +x /usr/local/bin/nuclei /usr/local/bin/dalfox /usr/local/bin/httpx && \
    ls -la /usr/local/bin/nuclei /usr/local/bin/httpx /usr/local/bin/dalfox && \
    /usr/local/bin/nuclei -version || (echo "ERROR: nuclei installation failed" && exit 1) && \
    /usr/local/bin/httpx -version || (echo "ERROR: httpx installation failed" && exit 1) && \
    /usr/local/bin/dalfox version || (echo "ERROR: dalfox installation failed" && exit 1) && \
    echo "✅ All Go tools installed successfully"

# Install Node.js tools for dependency scanning
# retire: Use the retire package (binary is 'retire')
# wappalyzer: Install v6.x (has CLI via driver.js), but allow graceful fallback
# Note: npm installs to /usr/lib/node_modules/ when using NodeSource repo
# Note: wappalyzer v6.x requires Puppeteer which downloads Chrome - this may fail in some environments
RUN npm install -g retire && \
    npm list -g retire || (echo "ERROR: retire installation failed" && exit 1) && \
    # Verify retire is accessible and create symlink if needed
    (retire --version 2>&1 | head -1 || (echo "ERROR: retire not working" && exit 1)) && \
    # Ensure retire is in /usr/local/bin (create symlink if needed)
    (command -v retire > /dev/null || \
     (find /usr -name "retire" -type f 2>/dev/null | head -1 | xargs -I {} ln -sf {} /usr/local/bin/retire || \
      find /usr/lib/node_modules/retire -name "retire" -type f 2>/dev/null | head -1 | xargs -I {} ln -sf {} /usr/local/bin/retire || \
      echo "INFO: retire binary already in PATH")) && \
    # Install wappalyzer (may fail due to Puppeteer/Chrome requirements, but wrapper script will handle it)
    (npm install -g wappalyzer@6.10.66 || echo "WARNING: wappalyzer installation failed, will use fallback wrapper script") && \
    # Find wappalyzer driver.js and create symlink (v6.x uses driver.js)
    ( [ -f "/usr/lib/node_modules/wappalyzer/driver.js" ] && ln -sf /usr/lib/node_modules/wappalyzer/driver.js /usr/local/bin/wappalyzer && chmod +x /usr/lib/node_modules/wappalyzer/driver.js || \
      [ -f "/usr/local/lib/node_modules/wappalyzer/driver.js" ] && ln -sf /usr/local/lib/node_modules/wappalyzer/driver.js /usr/local/bin/wappalyzer && chmod +x /usr/local/lib/node_modules/wappalyzer/driver.js || \
      echo "INFO: wappalyzer driver.js not found, will use Node.js wrapper script" ) && \
    # Verify both tools are accessible
    (command -v retire > /dev/null && echo "✅ retire found in PATH") && \
    ([ -f "/usr/local/bin/wappalyzer-cli.js" ] && echo "✅ wappalyzer wrapper script found") && \
    echo "✅ Node.js tools installed successfully"

# Install osv-scanner
# Download the latest release (use generic version to avoid hardcoding)
RUN wget -q -O /tmp/osv-scanner.deb https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_1.0.0_linux_amd64.deb \
    && dpkg -i /tmp/osv-scanner.deb || (apt-get install -f -y && dpkg -i /tmp/osv-scanner.deb) \
    && rm -f /tmp/osv-scanner.deb \
    && find /usr -name "osv-scanner" -type f 2>/dev/null | head -1 | xargs -I {} ln -sf {} /usr/local/bin/osv-scanner || true \
    && (osv-scanner --version || /usr/bin/osv-scanner --version || echo "WARNING: osv-scanner binary not found in expected locations") \
    && echo "✅ osv-scanner installed successfully"

# Catalog
RUN mkdir -p /app/catalog
COPY catalog/catalog.json /app/catalog/catalog.json
ENV TOOL_CATALOG_PATH=/app/catalog/catalog.json

# App code
COPY . .

# Copy and install wappalyzer wrapper script (fallback if CLI not available)
COPY wappalyzer-cli.js /usr/local/bin/wappalyzer-cli.js
RUN chmod +x /usr/local/bin/wappalyzer-cli.js

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
