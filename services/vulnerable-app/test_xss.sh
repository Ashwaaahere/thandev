#!/bin/bash
# XSS Vulnerability Test Script
# Tests all 10 XSS vulnerabilities in the vulnerable application

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     XSS VULNERABILITY VERIFICATION TEST                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

BASE_URL="http://localhost:5000"
PASS=0
FAIL=0

# Function to test XSS
test_xss() {
    local name="$1"
    local url="$2"
    local payload="$3"
    local expected="$4"
    
    echo "Testing: $name"
    echo "URL: $url"
    
    response=$(curl -s "$url")
    
    if echo "$response" | grep -q "$expected"; then
        echo "✅ VULNERABLE - XSS payload reflected!"
        ((PASS++))
    else
        echo "❌ NOT VULNERABLE - Payload was sanitized"
        ((FAIL++))
    fi
    echo ""
}

echo "Starting XSS vulnerability tests..."
echo ""

# Test 1: Reflected XSS - GET Parameter
test_xss \
    "1. Reflected XSS - GET Parameter" \
    "$BASE_URL/search?q=<script>alert('XSS')</script>" \
    "<script>alert('XSS')</script>" \
    "<script>alert('XSS')</script>"

# Test 2: Reflected XSS - Multiple Parameters
test_xss \
    "2. Reflected XSS - Multiple Parameters (name)" \
    "$BASE_URL/profile?name=<img src=x onerror=alert(1)>&email=test@test.com" \
    "<img src=x onerror=alert(1)>" \
    "<img src=x onerror=alert(1)>"

# Test 3: Reflected XSS - URL Path
test_xss \
    "3. Reflected XSS - URL Path" \
    "$BASE_URL/user/<svg/onload=alert(1)>" \
    "<svg/onload=alert(1)>" \
    "<svg/onload=alert(1)>"

# Test 4: DOM-based XSS
test_xss \
    "4. DOM-based XSS" \
    "$BASE_URL/dom?data=<img src=x onerror=alert('DOM')>" \
    "<img src=x onerror=alert('DOM')>" \
    "innerHTML"

# Test 5: XSS in JSON Response
test_xss \
    "5. XSS in JSON Response" \
    "$BASE_URL/api/user?name=<script>alert('JSON')</script>" \
    "<script>alert('JSON')</script>" \
    "<script>alert('JSON')</script>"

# Test 6: Cookie Reflection
echo "Testing: 6. XSS via Cookie"
echo "URL: $BASE_URL/cookie-test"
response=$(curl -s -b "username=<script>alert('Cookie')</script>" "$BASE_URL/cookie-test")
if echo "$response" | grep -q "<script>alert('Cookie')</script>"; then
    echo "✅ VULNERABLE - Cookie XSS payload reflected!"
    ((PASS++))
else
    echo "❌ NOT VULNERABLE - Cookie payload was sanitized"
    ((FAIL++))
fi
echo ""

# Test 7: User-Agent Header
echo "Testing: 7. XSS via User-Agent Header"
echo "URL: $BASE_URL/headers"
response=$(curl -s -A "<script>alert('UA')</script>" "$BASE_URL/headers")
if echo "$response" | grep -q "<script>alert('UA')</script>"; then
    echo "✅ VULNERABLE - User-Agent XSS payload reflected!"
    ((PASS++))
else
    echo "❌ NOT VULNERABLE - User-Agent payload was sanitized"
    ((FAIL++))
fi
echo ""

# Test 8: Referer Header
echo "Testing: 8. XSS via Referer Header"
echo "URL: $BASE_URL/referer"
response=$(curl -s -e "http://evil.com/<script>alert('Referer')</script>" "$BASE_URL/referer")
if echo "$response" | grep -q "<script>alert('Referer')</script>"; then
    echo "✅ VULNERABLE - Referer XSS payload reflected!"
    ((PASS++))
else
    echo "❌ NOT VULNERABLE - Referer payload was sanitized"
    ((FAIL++))
fi
echo ""

# Test 9: POST Form XSS
echo "Testing: 9. Reflected XSS - POST Form"
echo "URL: $BASE_URL/comment"
response=$(curl -s -X POST -d "comment=<script>alert('POST')</script>" "$BASE_URL/comment")
if echo "$response" | grep -q "<script>alert('POST')</script>"; then
    echo "✅ VULNERABLE - POST XSS payload reflected!"
    ((PASS++))
else
    echo "❌ NOT VULNERABLE - POST payload was sanitized"
    ((FAIL++))
fi
echo ""

# Test 10: Stored XSS
echo "Testing: 10. Stored XSS - Database"
echo "URL: $BASE_URL/post"
# Create a post with XSS
curl -s -X POST -d "title=<script>alert('Stored')</script>&content=Test" "$BASE_URL/post" > /dev/null
# Check if it's reflected on the posts page
response=$(curl -s "$BASE_URL/posts")
if echo "$response" | grep -q "<script>alert('Stored')</script>"; then
    echo "✅ VULNERABLE - Stored XSS payload persisted and reflected!"
    ((PASS++))
else
    echo "❌ NOT VULNERABLE - Stored payload was sanitized"
    ((FAIL++))
fi
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Total Tests: $((PASS + FAIL))"
echo "✅ Vulnerable: $PASS"
echo "❌ Protected: $FAIL"
echo ""

if [ $PASS -ge 8 ]; then
    echo "🎯 SUCCESS! Application has STRONG XSS vulnerabilities!"
    echo "Your security scanner should detect these easily."
else
    echo "⚠️  WARNING: Some vulnerabilities may not be working correctly."
fi
echo ""
