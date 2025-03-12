import os
import json
import requests
import re
import time
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
    """Log in to Facebook using undetected ChromeDriver and get session cookies."""
    try:
        # Use undetected ChromeDriver to bypass Facebook detection
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        driver = uc.Chrome(options=options, headless=False)  # Keep headless=False for debugging
        driver.get("https://www.facebook.com/login")

        time.sleep(3)

        email_input = driver.find_element(By.ID, "email")
        password_input = driver.find_element(By.ID, "pass")

        email_input.send_keys(email)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)

        time.sleep(5)  # Wait for login

        # Take a screenshot for debugging
        driver.save_screenshot("login_debug.png")

        # Get session cookies
        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        driver.quit()

        if "c_user" in cookies and "xs" in cookies:
            print("✅ Facebook login successful!")
            return cookies
        else:
            print("❌ Error: Login failed! Check `login_debug.png` for issues.")
            return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def boost_reactions(email, password, post_url, reactions):
    """Login, get session, and send reaction request."""
    session_cookies = login_with_email(email, password)

    if not session_cookies:
        return "❌ Login failed! Check email and password."

    # Create session with cookies
    session_req = requests.Session()
    session_req.cookies.update(session_cookies)

    try:
        get_token_page = session_req.get(REACTION_URL).text
        token_match = re.search(r'name="_token" value="(.*?)"', get_token_page)

        if not token_match:
            return "❌ Failed to get token."

        token = token_match.group(1)
        data = {"url": post_url, "limit": "50", "reactions[]": reactions, "_token": token}
        response = session_req.post(REACTION_URL, data=data).text

        if "Order Submitted" in response:
            save_history(post_url, reactions)  # Save to history
            return "✅ Reactions sent successfully!"
        elif "Cooldown" in response:
            cooldown_time = int(re.search(r"please try again after (\d+) minutes", response).group(1)) * 60
            return f"⏳ Cooldown: Wait {cooldown_time} seconds."
    except Exception as e:
        print(f"❌ Boost error: {e}")
    return "❌ Reaction boost failed."

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

    result = boost_reactions(session["email"], session["password"], session["post_url"], session["reactions"])
    return render_template("boost.html", result=result)

@app.route("/history")
def history():
    """Display the history of boosted posts."""
    history_data = load_history()
    return render_template("history.html", history=history_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
