# SQLMap Root Cause Analysis

## Problem Statement
SQL injection is manually reproducible on `http://testphp.vulnweb.com/login.php`, but Thandev's SQLMap tool run returns success with 0 findings.

## Current Implementation

### Command Executed
Thandev currently runs SQLMap with:
```bash
sqlmap -u http://testphp.vulnweb.com/login.php \
  --forms \
  --batch \
  --risk=3 \
  --level=5 \
  --timeout=60 \
  --time-sec=10 \
  --random-agent \
  --crawl=2 \
  --technique=BEUSTQ \
  --fresh-queries \
  --threads=1 \
  --tamper=space2comment,charencode \
  --dbms=all \
  --no-cast \
  --no-escape \
  -v 3 \
  --output-dir <output_dir>
```

### Root Cause

**The `--forms` flag is insufficient for login forms that require:**
1. **POST method**: The login form uses POST, but `--forms` may not properly capture the POST request body
2. **Form field names**: SQLMap needs to know the exact parameter names (e.g., `uname`, `pass`) 
3. **Cookies/Session**: Login forms often require session cookies that are set when fetching the login page
4. **CSRF tokens**: Some forms include CSRF tokens that must be included in the POST request
5. **Hidden fields**: Forms may have hidden fields that must be included

**Why `-u <url> --forms` fails:**
- SQLMap's `--forms` flag attempts to auto-detect forms, but it:
  - May not properly handle POST requests
  - May not capture cookies set during the initial GET request
  - May not include hidden form fields
  - May not handle CSRF tokens that change per request

## Solution

The most reliable method for testing login forms is to use SQLMap's `-r` (raw request file) option:

1. **Fetch the login page** (`GET http://testphp.vulnweb.com/login.php`)
2. **Parse the HTML form** to extract:
   - Form action URL
   - Form method (POST)
   - Input field names (username, password, hidden fields)
   - CSRF token (if present)
3. **Capture cookies** from the GET response
4. **Build a raw HTTP request** with:
   - POST method
   - Proper headers (including cookies)
   - POST body with form data (including placeholders for SQLMap to inject)
5. **Save as a raw request file** and pass to SQLMap with `-r request.txt`

This ensures SQLMap tests the actual POST request that the login form uses, not just a GET request with `--forms`.

## Evidence

Manual testing shows:
- `http://testphp.vulnweb.com/login.php` accepts POST requests with `uname` and `pass` parameters
- SQL injection is reproducible with payloads like `uname=admin' OR '1'='1&pass=test`
- SQLMap with `-u <url> --forms` does not detect this vulnerability

## Next Steps

1. Implement a request recorder utility to build raw HTTP requests for login forms
2. Add new SQLMap modes to catalog: `sqli_raw_request`, `sqli_forms_login`, `sqli_post_data`
3. Update SQLMap execution to support these modes
4. Fix parsing to ensure findings are created when SQLMap detects SQLi

