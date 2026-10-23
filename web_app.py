"""CyberNews Tracker - main Flask entry point."""

import hmac
import os
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, make_response, redirect, render_template, request, url_for
from markupsafe import escape
from werkzeug.security import check_password_hash, generate_password_hash

from database import CATEGORIES, close_db, get_db, init_db

# Read KEY=value pairs from .env into the environment (system variables take precedence)
load_dotenv()

app = Flask(__name__)
app.teardown_appcontext(close_db)
init_db()

SESSION_COOKIE = "session_token"
SESSION_LIFETIME = timedelta(minutes=30)
CSRF_COOKIE = "csrf_token"

# Brute-force protection: this many failed logins from one IP within the window -> temporarily blocked
MAX_FAILED_LOGINS = 5
LOGIN_WINDOW_MINUTES = 5

NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_API_PLACEHOLDER = "your_api_key_here"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", NEWS_API_PLACEHOLDER)

# Local fallback headlines for /api/news (used when the live API is unavailable)
LOCAL_NEWS = [
    {"title": "New Malware Targets Industrial Systems", "source": "CyberDaily"},
    {"title": "Researchers Discover AI-Powered Phishing Campaign", "source": "TechWatch"},
    {"title": "Ransomware Gang Hits Regional Hospital Network", "source": "SecureWire"},
    {"title": "Critical Router Flaw Patched After Mass Exploitation", "source": "PatchNews"},
]

# Server-side session store: session_token -> {user_id, username, role, login_time}
# The browser only ever sees the random token, never the data itself.
SESSIONS = {}


@app.before_request
def load_current_user():
    """Look up the session_token cookie on every request and expose the user as g.user."""
    g.user = None
    token = request.cookies.get(SESSION_COOKIE)
    session = SESSIONS.get(token) if token else None
    if session is None:
        return
    if datetime.now() - session["login_time"] > SESSION_LIFETIME:
        SESSIONS.pop(token, None)  # expired -> forget it server-side
        return
    g.user = session


@app.before_request
def protect_against_csrf():
    """Double-submit token: every POST must carry the same random value as the csrf_token cookie."""
    g.csrf_token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not hmac.compare_digest(sent, request.cookies.get(CSRF_COOKIE, "")) or not sent:
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


@app.after_request
def add_security_headers(response):
    if request.cookies.get(CSRF_COOKIE) != g.get("csrf_token"):
        response.set_cookie(CSRF_COOKIE, g.csrf_token, httponly=True, samesite="Lax", secure=request.is_secure)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": g.get("csrf_token", "")}


def login_required(view):
    """Only let requests with a valid server-side session through."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def role_required(role):
    """Only let logged-in users with the given role through - the role comes from SESSIONS, never from the client."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if g.user["role"] != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="This page does not exist."), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=error.description), 400


@app.route("/")
def home():
    db = get_db()
    featured = db.execute("SELECT * FROM articles WHERE featured = 1 ORDER BY published DESC, id DESC LIMIT 3").fetchall()
    latest = db.execute("SELECT * FROM articles ORDER BY published DESC, id DESC LIMIT 6").fetchall()
    stats = db.execute("SELECT COUNT(*) AS articles, COUNT(DISTINCT source) AS sources FROM articles").fetchone()
    return render_template("home.html", featured=featured, latest=latest, stats=stats, categories=CATEGORIES)


@app.route("/status")
def status():
    return "Application is running."


@app.route("/info")
def info():
    return f"Today's date is {date.today().isoformat()}"


@app.route("/greet/<name>")
def greet(name):
    return f"Hello, {escape(name)}!"


@app.route("/calculate/add/<int:num1>/<int:num2>")
def add(num1, num2):
    result = num1 + num2
    return f"The sum of {num1} and {num2} is {result}."


def search_articles(query="", category="", source=""):
    """Filter articles with parameterised SQL (user input is never pasted into the query string)."""
    sql = "SELECT * FROM articles WHERE 1 = 1"
    params = []
    if query:
        sql += " AND (title LIKE ? OR summary LIKE ? OR content LIKE ?)"
        params += [f"%{query}%"] * 3
    if category:
        sql += " AND category = ?"
        params.append(category)
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY published DESC, id DESC"
    return get_db().execute(sql, params).fetchall()


def article_to_dict(row):
    return {key: row[key] for key in ("id", "title", "summary", "category", "source", "published", "featured")}


@app.route("/news")
def news():
    username = g.user["username"] if g.user else "Guest"
    sources = [r["source"] for r in get_db().execute("SELECT DISTINCT source FROM articles ORDER BY source")]
    return render_template(
        "news.html",
        username=username,
        categories=CATEGORIES,
        sources=sources,
        last_updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/articles")
def api_articles():
    """Filterable article list as JSON - the news page loads it with fetch()."""
    rows = search_articles(
        request.args.get("q", "").strip()[:100],
        request.args.get("category", ""),
        request.args.get("source", ""),
    )
    return jsonify([article_to_dict(row) for row in rows])


@app.route("/article/<int:article_id>")
def article(article_id):
    row = get_db().execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        abort(404)
    saved = False
    if g.user:
        saved = get_db().execute(
            "SELECT 1 FROM bookmarks WHERE user_id = ? AND article_id = ?", (g.user["user_id"], article_id)
        ).fetchone() is not None
    return render_template("article.html", article=row, saved=saved)


def back_after_bookmark(article_id):
    """Go back to where the click came from - only to two known pages, never to a URL from the form."""
    if request.form.get("next") == "dashboard":
        return redirect(url_for("dashboard"))
    return redirect(url_for("article", article_id=article_id))


@app.route("/article/<int:article_id>/save", methods=["POST"])
@login_required
def bookmark_add(article_id):
    db = get_db()
    if db.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,)).fetchone() is None:
        abort(404)
    db.execute("INSERT OR IGNORE INTO bookmarks (user_id, article_id) VALUES (?, ?)", (g.user["user_id"], article_id))
    db.commit()
    return back_after_bookmark(article_id)


@app.route("/article/<int:article_id>/unsave", methods=["POST"])
@login_required
def bookmark_remove(article_id):
    db = get_db()
    db.execute("DELETE FROM bookmarks WHERE user_id = ? AND article_id = ?", (g.user["user_id"], article_id))
    db.commit()
    return back_after_bookmark(article_id)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/api/news")
def api_news():
    """Local fallback source: a small static list of headlines as JSON."""
    return jsonify(LOCAL_NEWS)


@app.route("/api/live-news")
def api_live_news():
    """Fetch real cybersecurity headlines from NewsAPI and return a slim JSON list."""
    # The key stays on the server - it comes from the environment / .env, never sent to the browser
    if NEWS_API_KEY in ("", NEWS_API_PLACEHOLDER):
        return jsonify({"error": "NEWS_API_KEY is not set on the server."}), 500

    params = {"q": "cybersecurity", "language": "en", "apiKey": NEWS_API_KEY}
    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=5)
        data = response.json()
    except (requests.RequestException, ValueError):
        # No connection, timeout or a response that isn't JSON
        return jsonify({"error": "Could not reach NewsAPI."}), 502

    if response.status_code != 200 or data.get("status") != "ok":
        return jsonify({"error": data.get("message", "NewsAPI returned an error.")}), 502

    # Only pass on what the frontend needs: title, source name and link
    articles = [
        {
            "title": article.get("title"),
            "source": (article.get("source") or {}).get("name"),
            "url": article.get("url"),
        }
        for article in data.get("articles", [])[:10]
        if article.get("title") and article.get("title") != "[Removed]"
    ]
    return jsonify(articles)


# Keyword -> category, checked in order; anything else is filed under "Research"
CATEGORY_KEYWORDS = [
    ("Ransomware", ("ransom",)),
    ("Data Breach", ("breach", "leak", "exposed", "stolen")),
    ("Phishing", ("phish", "scam", "social engineering")),
    ("Malware", ("malware", "trojan", "botnet", "spyware", "stealer", "backdoor")),
    ("Vulnerabilities", ("vulnerab", "cve-", "zero-day", "exploit", "patch", "flaw")),
]


def guess_category(text):
    text = text.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "Research"


def import_live_news():
    """Store fresh NewsAPI articles in the database (skips links that are already saved).

    Returns (number_imported, error_message) - error_message is None on success.
    """
    if NEWS_API_KEY in ("", NEWS_API_PLACEHOLDER):
        return 0, "NEWS_API_KEY is not set on the server."

    params = {
        # Search the titles only, for typical security topics - keeps out unrelated press releases
        "q": "ransomware OR malware OR phishing OR vulnerability OR \"data breach\" OR cyberattack OR \"zero-day\"",
        "searchIn": "title",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 30,
        "apiKey": NEWS_API_KEY,
    }
    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        data = response.json()
    except (requests.RequestException, ValueError):
        return 0, "Could not reach NewsAPI."
    if response.status_code != 200 or data.get("status") != "ok":
        return 0, data.get("message", "NewsAPI returned an error.")

    db = get_db()
    has_featured = db.execute("SELECT 1 FROM articles WHERE featured = 1").fetchone() is not None
    imported = 0
    for item in data.get("articles", []):
        title = (item.get("title") or "").strip()
        url = item.get("url") or ""
        if not title or title == "[Removed]" or not url.startswith(("http://", "https://")):
            continue
        if db.execute("SELECT 1 FROM articles WHERE source_url = ?", (url,)).fetchone():
            continue

        summary = (item.get("description") or title).strip()[:500]
        # NewsAPI cuts "content" off with "[+1234 chars]" - drop that marker
        content = re.sub(r"\s*\[\+\d+ chars\]$", "", (item.get("content") or "").strip()) or summary
        db.execute(
            "INSERT INTO articles (title, summary, content, category, source, source_url, published, featured)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                title[:200],
                summary,
                content,
                guess_category(f"{title} {summary}"),
                ((item.get("source") or {}).get("name") or "Unknown")[:80],
                url,
                (item.get("publishedAt") or date.today().isoformat())[:10],
                # The first three articles of the very first import become the featured stories
                0 if has_featured or imported >= 3 else 1,
            ),
        )
        imported += 1
    db.commit()
    return imported, None


@app.route("/admin/import-news", methods=["POST"])
@role_required("admin")
def admin_import_news():
    imported, error = import_live_news()
    return redirect(url_for("admin_dashboard", imported=imported, import_error=error))


@app.route("/contact")
def contact():
    return render_template("contact_form.html")


@app.route("/submit-message", methods=["POST"])
def submit_message():
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")
    if not (name and email and message) or len(name) > 100 or len(email) > 200 or len(message) > 2000:
        abort(400, "Please fill in all fields (message up to 2000 characters).")
    get_db().execute("INSERT INTO messages (name, email, message) VALUES (?, ?, ?)", (name, email, message))
    get_db().commit()
    return render_template(
        "confirmation.html", name=name, email=email, message=message
    )


def log_login(username, success):
    db = get_db()
    db.execute(
        "INSERT INTO login_audit (username, success, ip) VALUES (?, ?, ?)",
        (username[:50], int(success), request.remote_addr),
    )
    db.commit()


def too_many_failed_logins():
    row = get_db().execute(
        "SELECT COUNT(*) FROM login_audit WHERE success = 0 AND ip = ?"
        " AND created_at > datetime('now', ?)",
        (request.remote_addr, f"-{LOGIN_WINDOW_MINUTES} minutes"),
    ).fetchone()
    return row[0] >= MAX_FAILED_LOGINS


def start_session(user):
    """Create a fresh server-side session and return a redirect that sets its cookie."""
    # Drop any previous session so an old (possibly planted) token can't be reused
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        SESSIONS.pop(old_token, None)

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "login_time": datetime.now(),
    }

    response = redirect(url_for("dashboard"))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # not readable via document.cookie
        samesite="Lax",  # not sent on cross-site POSTs (CSRF protection)
        secure=request.is_secure,  # Secure flag whenever the app runs over HTTPS
    )
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.user is not None:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")

    if too_many_failed_logins():
        error = f"Too many failed attempts. Try again in {LOGIN_WINDOW_MINUTES} minutes."
        return render_template("login.html", error=error), 429

    user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        log_login(username, False)
        return render_template("login.html", error="Invalid username or password."), 401

    log_login(username, True)
    return start_session(user)


USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,20}")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    error = None
    if not USERNAME_PATTERN.fullmatch(username):
        error = "Username: 3-20 characters, only letters, digits and underscore."
    elif len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        error = "Password: at least 8 characters with letters and digits."
    elif password != confirm:
        error = "The passwords do not match."
    elif get_db().execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        error = "This username is already taken."
    if error:
        return render_template("register.html", error=error), 400

    # Self-registered accounts are always plain users - the role is never taken from the form
    db = get_db()
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
        (username, generate_password_hash(password)),
    )
    db.commit()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    log_login(username, True)
    return start_session(user)


@app.route("/dashboard")
@login_required
def dashboard():
    saved = get_db().execute(
        "SELECT a.* FROM bookmarks b JOIN articles a ON a.id = b.article_id"
        " WHERE b.user_id = ? ORDER BY b.created_at DESC, a.id DESC",
        (g.user["user_id"],),
    ).fetchall()
    return render_template("dashboard.html", user=g.user, active_sessions=len(SESSIONS), saved=saved)


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    db = get_db()
    # Only show who is logged in - the tokens themselves never leave the server
    sessions = sorted(SESSIONS.values(), key=lambda s: s["login_time"], reverse=True)
    return render_template(
        "admin_dashboard.html",
        user=g.user,
        imported=request.args.get("imported", type=int),
        import_error=request.args.get("import_error"),
        sessions=sessions,
        accounts=db.execute("SELECT username, role, created_at FROM users ORDER BY id").fetchall(),
        articles=db.execute("SELECT id, title, category, published, featured FROM articles"
                            " ORDER BY published DESC, id DESC").fetchall(),
        audit=db.execute("SELECT * FROM login_audit ORDER BY id DESC LIMIT 20").fetchall(),
        messages=db.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 20").fetchall(),
        audit_total=db.execute("SELECT COUNT(*) FROM login_audit").fetchone()[0],
        message_total=db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
    )


def read_article_form():
    """Validate the admin article form. Returns (values, error)."""
    form = request.form
    values = {
        "title": form.get("title", "").strip(),
        "summary": form.get("summary", "").strip(),
        "content": form.get("content", "").strip(),
        "category": form.get("category", ""),
        "source": form.get("source", "").strip(),
        "source_url": form.get("source_url", "").strip(),
        "published": form.get("published", "").strip(),
        "featured": 1 if form.get("featured") else 0,
    }
    error = None
    if not all(values[k] for k in ("title", "summary", "content", "source", "published")):
        error = "Title, summary, content, source and date are required."
    elif len(values["title"]) > 200 or len(values["summary"]) > 500 or len(values["source"]) > 80:
        error = "Title (200), summary (500) or source (80) is too long."
    elif values["category"] not in CATEGORIES:
        error = "Please choose a valid category."
    elif values["source_url"] and not values["source_url"].startswith(("http://", "https://")):
        error = "The source link must start with http:// or https://."
    else:
        try:
            date.fromisoformat(values["published"])
        except ValueError:
            error = "The date must look like YYYY-MM-DD."
    return values, error


def render_article_form(article, error=None, status=200):
    return render_template("article_form.html", article=article, categories=CATEGORIES, error=error), status


@app.route("/admin/articles/new", methods=["GET", "POST"])
@role_required("admin")
def article_new():
    if request.method == "GET":
        return render_article_form({"published": date.today().isoformat(), "featured": 0})
    values, error = read_article_form()
    if error:
        return render_article_form(values, error, 400)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO articles (title, summary, content, category, source, source_url, published, featured, author_id)"
        " VALUES (:title, :summary, :content, :category, :source, :source_url, :published, :featured, :author_id)",
        {**values, "author_id": g.user["user_id"]},
    )
    db.commit()
    return redirect(url_for("article", article_id=cursor.lastrowid))


@app.route("/admin/articles/<int:article_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def article_edit(article_id):
    db = get_db()
    existing = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if existing is None:
        abort(404)
    if request.method == "GET":
        return render_article_form(existing)
    values, error = read_article_form()
    if error:
        return render_article_form({**values, "id": article_id}, error, 400)
    db.execute(
        "UPDATE articles SET title = :title, summary = :summary, content = :content, category = :category,"
        " source = :source, source_url = :source_url, published = :published, featured = :featured"
        " WHERE id = :id",
        {**values, "id": article_id},
    )
    db.commit()
    return redirect(url_for("article", article_id=article_id))


@app.route("/admin/articles/<int:article_id>/delete", methods=["POST"])
@role_required("admin")
def article_delete(article_id):
    db = get_db()
    db.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/logout", methods=["POST"])
def logout():
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        SESSIONS.pop(token, None)
    response = redirect(url_for("login"))
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="Lax")
    return response


@app.route("/cookie_check")
def cookie_check():
    response = make_response(render_template("cookie_check.html"))
    response.set_cookie("js_visible_cookie", "I_can_be_read_by_JavaScript", samesite="Lax")
    response.set_cookie(
        "httponly_cookie", "You_cannot_see_me", httponly=True, samesite="Lax"
    )
    return response


# First start with an empty article table: fill it from the live API (ignored if the API is unreachable)
with app.app_context():
    if get_db().execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0:
        import_live_news()


if __name__ == "__main__":
    # Debug mode exposes an interactive console - only switch it on locally via FLASK_DEBUG=1
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
