import os
from flask import Flask, render_template, request, session, redirect, url_for
import requests
import re
import time
import json
from flask_session import Session  # Import Flask-Session

app = Flask(__name__)

# Retrieve secret key from environment variable or use a default for development
app.secret_key = os.environ.get("SECRET_KEY", "b5c6ba00bff9f5bdaef120129a560466bce3db23116f583a042f5540f55be8b9")

# Configure session storage using the filesystem
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_FILE_DIR"] = "./flask_session"  # Where session files are stored
Session(app)  # Activate Flask-Session

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

def login(fb_cookie):
    """Log in to Machine Liker using Facebook session cookies."""
    try:
        session_req = requests.Session()
        response = session_req.get(LOGIN_URL, headers=HEADERS, cookies={"cookie": fb_cookie})

        user_id_match = re.search(r'"id":"(\d+)"', response.text)
        if user_id_match:
            return session_req  # Successfully logged in
    except:
        pass
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
    except:
        pass
    return "Reaction boost failed."

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        fb_cookie = request.form.get("fb_cookie")
        post_url = request.form.get("post_url")
        reactions = request.form.getlist("reactions")

        session_req = login(fb_cookie)
        if session_req:
            session["fb_cookie"] = fb_cookie
            session["post_url"] = post_url
            session["reactions"] = reactions
            return redirect(url_for("boost"))

        return render_template("index.html", error="Invalid Facebook session cookie!")

    return render_template("index.html")

@app.route("/boost")
def boost():
    if "fb_cookie" not in session:
        return redirect(url_for("index"))

    session_req = login(session["fb_cookie"])
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
