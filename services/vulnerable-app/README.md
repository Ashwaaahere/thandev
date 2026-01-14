# Vulnerable Test Application

⚠️ **WARNING**: This application contains **INTENTIONAL** security vulnerabilities for testing purposes.

**DO NOT** deploy this in production or expose it to the internet!

## Purpose

This application is designed to test security scanners and penetration testing tools. It contains multiple types of vulnerabilities including:

### XSS Vulnerabilities (10+ variants)

1. **Reflected XSS - GET Parameter** (`/search?q=`)
2. **Reflected XSS - Multiple Parameters** (`/profile?name=&email=`)
3. **Reflected XSS - URL Path** (`/user/<username>`)
4. **Reflected XSS - POST Form** (`/comment`)
5. **Stored XSS - Database** (`/post` and `/posts`)
6. **DOM-based XSS** (`/dom?data=`)
7. **XSS in JSON Response** (`/api/user?name=`)
8. **XSS via Cookie** (`/cookie-test`)
9. **XSS via User-Agent Header** (`/headers`)
10. **XSS via Referer Header** (`/referer`)

### Other Vulnerabilities

- **SQL Injection** (`/login?username=&password=`)
- **Open Redirect** (`/redirect?url=`)
- **SSRF** (`/fetch?url=`)

## Running the Application

### Option 1: Direct Python

```bash
cd services/vulnerable-app
pip install -r requirements.txt
python app.py
```

### Option 2: Docker

```bash
cd services/vulnerable-app
docker build -t vulnerable-app .
docker run -p 5000:5000 vulnerable-app
```

### Option 3: Docker Compose

Add to your `docker-compose.yml`:

```yaml
  vulnerable-app:
    build: ./services/vulnerable-app
    ports:
      - "5000:5000"
    networks:
      - thandev-network
```

## Testing

Once running, visit:
- **http://localhost:5000/** - Home page with all vulnerability links

### Example XSS Payloads

```bash
# Reflected XSS - GET parameter
http://localhost:5000/search?q=<script>alert('XSS')</script>

# Reflected XSS - Multiple parameters
http://localhost:5000/profile?name=<img src=x onerror=alert('XSS')>&email=test@test.com

# Reflected XSS - URL path
http://localhost:5000/user/<svg/onload=alert('XSS')>

# DOM-based XSS
http://localhost:5000/dom?data=<img src=x onerror=alert('DOM-XSS')>

# SQL Injection
http://localhost:5000/login?username=admin' OR '1'='1&password=anything

# Open Redirect
http://localhost:5000/redirect?url=https://evil.com

# SSRF
http://localhost:5000/fetch?url=http://169.254.169.254/latest/meta-data/
```

## Security Scanner Testing

This application is perfect for testing:
- **Nuclei** - XSS templates
- **Dalfox** - XSS scanner
- **SQLMap** - SQL injection
- **Nikto** - Web vulnerability scanner
- **OWASP ZAP** - Web application scanner
- **Burp Suite** - Manual and automated testing

### Example Nuclei Scan

```bash
nuclei -u http://localhost:5000 -t /root/nuclei-templates/http/vulnerabilities/
```

### Example Dalfox Scan

```bash
# Scan search endpoint
dalfox url http://localhost:5000/search?q=FUZZ

# Scan profile endpoint
dalfox url "http://localhost:5000/profile?name=FUZZ&email=FUZZ"
```

### Example SQLMap Scan

```bash
sqlmap -u "http://localhost:5000/login?username=test&password=test" --batch --risk=3 --level=5
```

## Expected Findings

A properly configured security scanner should detect:

- ✅ 10+ XSS vulnerabilities (reflected, stored, DOM-based)
- ✅ SQL Injection in login endpoint
- ✅ Open Redirect vulnerability
- ✅ SSRF vulnerability
- ✅ Missing security headers (CSP, X-Frame-Options, etc.)
- ✅ Insecure cookie handling

## Disclaimer

This application is for **EDUCATIONAL AND TESTING PURPOSES ONLY**.

- Only run in isolated test environments
- Never expose to the public internet
- Do not use on production networks
- Always obtain proper authorization before testing

## License

This is a test application for security research. Use at your own risk.
