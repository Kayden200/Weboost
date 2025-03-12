import os
import json
import requests
import re
import time
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session  # Import Flask-Session

app = Flask(__name__)

# Retrieve secret key from environment variable or use a default for development
app.secret_key = os.environ.get("SECRET_KEY", "b5c6ba00bff9f5bdaef120129a560466bce3db23116f583a042f5540f55be8b9")

# Configure session storage using the filesystem
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_FILE_DIR"] = "./flask_session"
Session(app)

# Machine Liker URLs
BASE_URL = "https://machineliker.net"
LOGIN_URL = f"{BASE_URL}/login"
REACTION_URL = f"{BASE_URL}/auto-reactions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A037F) AppleWebKit/537.36"
}

HISTORY_FILE = "history.json"

def save_history(post_url, reactions):
    """Save boosted post details to history."""
    history_data = load_history()
    history_data.append({
        "post_url": post_url,
        "reactions": reactions,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    with open(HISTORY_FILE, "w") as f:
        json.dump(history_data, f, indent=4)

def load_history():
    """Load history from JSON file."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def login_with_email(email, password):
    """Log in to Facebook using email and password, then get session cookies."""
    try:
        login_url = "https://www.facebook.com/login/device-based/regular/login/"
        session_req = requests.Session()

        # Get initial login page (to fetch any required tokens)
        response = session_req.get(login_url, headers=HEADERS)
        lsd_token = re.search(r'name="lsd" value="(.*?)"', response.text)

        if not lsd_token:
            print("❌ Error: Failed to get login token.")
            return None
        
        lsd_token = lsd_token.group(1)

        # Prepare login data
        data = {
            "email": email,
            "pass": password,
            "lsd": lsd_token,
            "login": "Log In"
        }

        # Send login request
        response = session_req.post(login_url, headers=HEADERS, data=data)

        # Check if login was successful
        if "c_user" in session_req.cookies and "xs" in session_req.cookies:
            print("✅ Facebook login successful!")
            return session_req  # Successfully logged in
        else:
            print("❌ Error: Invalid email or password.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    return None  # Login failed

def boost_reactions(session_req, post_url, reactions):
    """Send reaction request to Machine Liker."""
    try:
        get_token_page = session_req.get(REACTION_URL).text
        token_match = re.search(r'name="_token" value="(.*?)"', get_token_page)

        if not token_match:
            return "Failed to get token"

        token = token_match.group(1)
        data = {"url": post_url, "limit": "50", "reactions[]": reactions, "_token": token}
        response = session_req.post(REACTION_URL, data=data).text

        if "Order Submitted" in response:
            save_history(post_url, reactions)  # Save to history
            return "Reactions sent successfully!"
        elif "Cooldown" in response:
            cooldown_time = int(re.search(r"please try again after (\d+) minutes", response).group(1)) * 60
            return f"Cooldown: Wait {cooldown_time} seconds."
    except Exception as e:
        print(f"Boost error: {e}")
    return "Reaction boost failed."

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        post_url = request.form.get("post_url")
        reactions = request.form.getlist("reactions")

        session_req = login_with_email(email, password)
        if session_req:
            session["email"] = email
            session["password"] = password
            session["post_url"] = post_url
            session["reactions"] = reactions
            return redirect(url_for("boost"))

        return render_template("index.html", error="Invalid email or password!")

    return render_template("index.html")

@app.route("/boost")
def boost():
    if "email" not in session or "password" not in session:
        return redirect(url_for("index"))

    session_req = login_with_email(session["email"], session["password"])
    if not session_req:
        return render_template("index.html", error="Session expired, please log in again.")

    result = boost_reactions(session_req, session["post_url"], session["reactions"])
    return render_template("boost.html", result=result)

@app.route("/history")
def history():
    """Display the history of boosted posts."""
    history_data = load_history()
    return render_template("history.html", history=history_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
