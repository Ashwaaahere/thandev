"""
Intentionally Vulnerable Web Application for Security Testing
WARNING: This application contains INTENTIONAL security vulnerabilities
DO NOT deploy this in production or expose to the internet!
"""
from flask import Flask, request, render_template_string, make_response, redirect, jsonify
import sqlite3
import os

app = Flask(__name__)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('vulnerable.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT, email TEXT, comment TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY, title TEXT, content TEXT, author TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Home page with links to all vulnerable endpoints
@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vulnerable Test Application</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 8px; max-width: 800px; margin: 0 auto; }
            h1 { color: #d32f2f; }
            .warning { background: #fff3cd; border: 2px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }
            .endpoint { background: #e3f2fd; padding: 15px; margin: 10px 0; border-radius: 4px; }
            a { color: #1976d2; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚠️ Vulnerable Test Application</h1>
            <div class="warning">
                <strong>WARNING:</strong> This application contains intentional security vulnerabilities for testing purposes.
                <br>DO NOT deploy in production or expose to the internet!
            </div>
            
            <h2>XSS Vulnerabilities</h2>
            
            <div class="endpoint">
                <h3>1. Reflected XSS - GET Parameter</h3>
                <p>Direct reflection of user input without encoding</p>
                <a href="/search?q=test">Test: /search?q=test</a><br>
                <a href="/search?q=<script>alert('XSS')</script>">Exploit: /search?q=&lt;script&gt;alert('XSS')&lt;/script&gt;</a>
            </div>
            
            <div class="endpoint">
                <h3>2. Reflected XSS - Multiple Parameters</h3>
                <p>Multiple vulnerable parameters</p>
                <a href="/profile?name=John&email=john@example.com">Test: /profile?name=John&email=john@example.com</a><br>
                <a href="/profile?name=<img src=x onerror=alert('XSS')>&email=test@test.com">Exploit: name parameter</a>
            </div>
            
            <div class="endpoint">
                <h3>3. Reflected XSS - URL Path</h3>
                <p>Vulnerable path parameter</p>
                <a href="/user/admin">Test: /user/admin</a><br>
                <a href="/user/<svg/onload=alert('XSS')>">Exploit: /user/&lt;svg/onload=alert('XSS')&gt;</a>
            </div>
            
            <div class="endpoint">
                <h3>4. Reflected XSS - POST Form</h3>
                <p>POST parameter reflection</p>
                <form action="/comment" method="POST">
                    <input type="text" name="comment" placeholder="Enter comment">
                    <button type="submit">Submit</button>
                </form>
            </div>
            
            <div class="endpoint">
                <h3>5. Stored XSS - Database</h3>
                <p>Persistent XSS via database storage</p>
                <form action="/post" method="POST">
                    <input type="text" name="title" placeholder="Post title"><br>
                    <textarea name="content" placeholder="Post content"></textarea><br>
                    <button type="submit">Create Post</button>
                </form>
                <a href="/posts">View all posts</a>
            </div>
            
            <div class="endpoint">
                <h3>6. DOM-based XSS</h3>
                <p>Client-side DOM manipulation</p>
                <a href="/dom?data=test">Test: /dom?data=test</a><br>
                <a href="/dom?data=<img src=x onerror=alert('DOM-XSS')>">Exploit: DOM-based XSS</a>
            </div>
            
            <div class="endpoint">
                <h3>7. XSS in JSON Response</h3>
                <p>Unescaped JSON data</p>
                <a href="/api/user?name=test">Test: /api/user?name=test</a><br>
                <a href="/api/user?name=<script>alert('JSON-XSS')</script>">Exploit: JSON XSS</a>
            </div>
            
            <div class="endpoint">
                <h3>8. XSS via Cookie</h3>
                <p>Cookie reflection vulnerability</p>
                <a href="/cookie-test">Test cookie reflection</a>
            </div>
            
            <div class="endpoint">
                <h3>9. XSS via User-Agent Header</h3>
                <p>User-Agent header reflection</p>
                <a href="/headers">View headers (check User-Agent)</a>
            </div>
            
            <div class="endpoint">
                <h3>10. XSS via Referer Header</h3>
                <p>Referer header reflection</p>
                <a href="/referer">View referer</a>
            </div>
            
            <h2>Other Vulnerabilities</h2>
            
            <div class="endpoint">
                <h3>SQL Injection</h3>
                <p>Direct SQL query concatenation</p>
                <a href="/login?username=admin&password=password">Test: /login</a><br>
                <a href="/login?username=admin' OR '1'='1&password=anything">Exploit: SQL Injection</a>
            </div>
            
            <div class="endpoint">
                <h3>Open Redirect</h3>
                <p>Unvalidated redirect parameter</p>
                <a href="/redirect?url=https://google.com">Test: /redirect?url=https://google.com</a><br>
                <a href="/redirect?url=https://evil.com">Exploit: Open Redirect</a>
            </div>
            
            <div class="endpoint">
                <h3>SSRF</h3>
                <p>Server-Side Request Forgery</p>
                <a href="/fetch?url=https://example.com">Test: /fetch?url=https://example.com</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# 1. Reflected XSS - GET Parameter
@app.route('/search')
def search():
    query = request.args.get('q', '')
    # VULNERABLE: Direct reflection without escaping
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Search Results</title></head>
    <body>
        <h1>Search Results</h1>
        <p>You searched for: {query}</p>
        <p>No results found for "{query}"</p>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# 2. Reflected XSS - Multiple Parameters
@app.route('/profile')
def profile():
    name = request.args.get('name', '')
    email = request.args.get('email', '')
    # VULNERABLE: Multiple reflection points
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>User Profile</title></head>
    <body>
        <h1>User Profile</h1>
        <p>Name: {name}</p>
        <p>Email: {email}</p>
        <p>Welcome, {name}! Your email is {email}</p>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# 3. Reflected XSS - URL Path
@app.route('/user/<username>')
def user_profile(username):
    # VULNERABLE: Path parameter reflection
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>User: {username}</title></head>
    <body>
        <h1>Profile for {username}</h1>
        <p>Username: {username}</p>
        <p>This is the profile page for user: {username}</p>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# 4. Reflected XSS - POST Form
@app.route('/comment', methods=['GET', 'POST'])
def comment():
    if request.method == 'POST':
        comment_text = request.form.get('comment', '')
        # VULNERABLE: POST parameter reflection
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Comment Submitted</title></head>
        <body>
            <h1>Comment Submitted</h1>
            <p>Your comment: {comment_text}</p>
            <p>Thank you for your comment: {comment_text}</p>
            <a href="/">Back to home</a>
        </body>
        </html>
        """
        return html
    return redirect('/')

# 5. Stored XSS - Database
@app.route('/post', methods=['POST'])
def create_post():
    title = request.form.get('title', '')
    content = request.form.get('content', '')
    author = request.form.get('author', 'Anonymous')
    
    # VULNERABLE: Store unsanitized data
    conn = sqlite3.connect('vulnerable.db')
    c = conn.cursor()
    c.execute("INSERT INTO posts (title, content, author) VALUES (?, ?, ?)", 
              (title, content, author))
    conn.commit()
    conn.close()
    
    return redirect('/posts')

@app.route('/posts')
def view_posts():
    conn = sqlite3.connect('vulnerable.db')
    c = conn.cursor()
    c.execute("SELECT id, title, content, author FROM posts ORDER BY id DESC")
    posts = c.fetchall()
    conn.close()
    
    posts_html = ""
    for post in posts:
        # VULNERABLE: Display unsanitized data from database
        posts_html += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
            <h3>{post[1]}</h3>
            <p>{post[2]}</p>
            <small>By: {post[3]}</small>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>All Posts</title></head>
    <body>
        <h1>All Posts</h1>
        {posts_html}
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# 6. DOM-based XSS
@app.route('/dom')
def dom_xss():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>DOM XSS Demo</title></head>
    <body>
        <h1>DOM-based XSS</h1>
        <div id="output"></div>
        <a href="/">Back to home</a>
        <script>
            // VULNERABLE: Direct DOM manipulation with URL parameter
            var params = new URLSearchParams(window.location.search);
            var data = params.get('data');
            if (data) {
                document.getElementById('output').innerHTML = 'Data: ' + data;
            }
        </script>
    </body>
    </html>
    """
    return html

# 7. XSS in JSON Response
@app.route('/api/user')
def api_user():
    name = request.args.get('name', 'Guest')
    # VULNERABLE: Unescaped JSON (served as HTML)
    response = make_response(f'{{"name": "{name}", "status": "active"}}')
    response.headers['Content-Type'] = 'application/json'
    return response

# 8. XSS via Cookie
@app.route('/cookie-test')
def cookie_test():
    username = request.cookies.get('username', 'Guest')
    # VULNERABLE: Cookie reflection
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Cookie Test</title></head>
    <body>
        <h1>Cookie Reflection</h1>
        <p>Welcome back, {username}!</p>
        <p>Your username from cookie: {username}</p>
        <form action="/set-cookie" method="POST">
            <input type="text" name="username" placeholder="Set username">
            <button type="submit">Set Cookie</button>
        </form>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

@app.route('/set-cookie', methods=['POST'])
def set_cookie():
    username = request.form.get('username', '')
    response = make_response(redirect('/cookie-test'))
    response.set_cookie('username', username)
    return response

# 9. XSS via User-Agent Header
@app.route('/headers')
def headers():
    user_agent = request.headers.get('User-Agent', 'Unknown')
    # VULNERABLE: Header reflection
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Headers</title></head>
    <body>
        <h1>Request Headers</h1>
        <p>Your User-Agent: {user_agent}</p>
        <p>Browser: {user_agent}</p>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# 10. XSS via Referer Header
@app.route('/referer')
def referer():
    referer = request.headers.get('Referer', 'Direct access')
    # VULNERABLE: Referer reflection
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Referer</title></head>
    <body>
        <h1>Referer Information</h1>
        <p>You came from: {referer}</p>
        <p>Previous page: {referer}</p>
        <a href="/">Back to home</a>
    </body>
    </html>
    """
    return html

# SQL Injection
@app.route('/login')
def login():
    username = request.args.get('username', '')
    password = request.args.get('password', '')
    
    # VULNERABLE: SQL Injection
    conn = sqlite3.connect('vulnerable.db')
    c = conn.cursor()
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    try:
        c.execute(query)
        result = c.fetchone()
        conn.close()
        
        if result:
            return f"<h1>Login successful!</h1><p>Welcome {username}</p><a href='/'>Home</a>"
        else:
            return f"<h1>Login failed</h1><p>Invalid credentials for {username}</p><a href='/'>Home</a>"
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p><a href='/'>Home</a>"

# Open Redirect
@app.route('/redirect')
def open_redirect():
    url = request.args.get('url', '/')
    # VULNERABLE: Unvalidated redirect
    return redirect(url)

# SSRF
@app.route('/fetch')
def ssrf():
    url = request.args.get('url', '')
    if url:
        try:
            import urllib.request
            # VULNERABLE: SSRF
            response = urllib.request.urlopen(url)
            content = response.read().decode('utf-8')[:500]
            return f"<h1>Fetched Content</h1><pre>{content}</pre><a href='/'>Home</a>"
        except Exception as e:
            return f"<h1>Error</h1><p>{str(e)}</p><a href='/'>Home</a>"
    return "<h1>Provide a URL parameter</h1><a href='/'>Home</a>"

if __name__ == '__main__':
    print("=" * 60)
    print("⚠️  VULNERABLE TEST APPLICATION")
    print("=" * 60)
    print("WARNING: This application contains intentional vulnerabilities!")
    print("DO NOT deploy in production or expose to the internet!")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  - http://localhost:5000/ (Home page with all links)")
    print("  - Multiple XSS vulnerabilities")
    print("  - SQL Injection")
    print("  - Open Redirect")
    print("  - SSRF")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
