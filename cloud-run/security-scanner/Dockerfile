FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    python3 \
    python3-pip \
    nmap \
    sslscan \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Go 1.21 (compatible with Nuclei)
RUN wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz && \
    rm go1.21.6.linux-amd64.tar.gz

# Set Go environment
ENV PATH="/usr/local/go/bin:/go/bin:${PATH}"
ENV GOPATH="/go"
ENV GOBIN="/go/bin"

# Create go directories
RUN mkdir -p /go/bin

# Install Nuclei
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Install additional Go security tools
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Install additional security tools and GCS client
RUN pip3 install requests aiohttp google-cloud-storage

# Verify installations
RUN which nuclei && nuclei -version
RUN which subfinder && subfinder -version

# Create app directory
WORKDIR /app

# Copy the scanner script and utilities
COPY scanner.py .
COPY result_processor.py .

# Make the scripts executable
RUN chmod +x scanner.py

# Expose port
EXPOSE 8080

# Run the scanner
CMD ["python3", "scanner.py"]
