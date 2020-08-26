import os
import requests
import urllib.parse
import random
from cs50 import SQL

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    image = []
    image.append("https://i.imgur.com/n7L4aCC.jpg")
    image.append("https://i.imgur.com/VX10AFp.jpg")
    image.append("https://i.imgur.com/41WGKef.jpg")
    image.append("https://i.imgur.com/HdVzIGk.jpg")
    image.append("https://i.imgur.com/g59H2YM.jpg")
    image.append("https://i.imgur.com/FMBggFt.jpg")
    image.append("https://i.imgur.com/9rskGXR.png")

    i = random.randrange(7)

    return render_template("apology.html", top=code, bottom=escape(message), image=image[i]), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = "pk_2418e2106f00483fbf05d05bb5109ba0"
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def current_prices():
    db = SQL("sqlite:///finance.db")
    symbols = db.execute("SELECT symbol FROM logs WHERE symbol <> 'CASH' GROUP BY symbol")

    for symbol in symbols:
        price_updated = lookup(symbol["symbol"])["price"]
        db.execute("UPDATE logs SET current_price = ? * buy_or_sell WHERE symbol = ?", price_updated, symbol["symbol"])

def valid_password(password):
    if len(password) < 6 or len(password) > 12:
        return False
    letter = False
    numeric = False
    special = True
    for letter in password:
        if letter.isalpha():
            letter = True
        elif letter.isnumeric():
            numeric = True
        elif not (letter.isalpha() or letter.isnumeric()):
            special = False
    if letter and numeric and special:
        return True
    else:
        return False


