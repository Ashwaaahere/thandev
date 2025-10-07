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
    && rm -rf /var/lib/apt/lists/*

# Install Go 1.21 (compatible with Nuclei)
RUN wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz && \
    rm go1.21.6.linux-amd64.tar.gz

# Set Go environment
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/go"
ENV GOBIN="/go/bin"

# Install Nuclei
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# Install additional security tools
RUN pip3 install requests aiohttp

# Create app directory
WORKDIR /app

# Copy the scanner script
COPY scanner.py .

# Make the script executable
RUN chmod +x scanner.py

# Expose port
EXPOSE 8080

# Run the scanner
CMD ["python3", "scanner.py"]
