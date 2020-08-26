import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, json
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, current_prices, valid_password

#export API_KEY=pk_2418e2106f00483fbf05d05bb5109ba0

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    current_prices()
    info_index = db.execute("SELECT symbol as Symbol, name as Name, SUM(shares) as Shares, MAX(current_price) as Price, SUM(shares)*MAX(current_price) as TOTAL FROM logs WHERE user_id = ? GROUP BY symbol, name HAVING sum(shares) <> 0", session["user_id"])
    cash = {'Symbol': 'CASH', "Name": "", "Shares": "", 'Price': 0, 'TOTAL': round(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"], 2)}
    info_index.append(cash)
    sum_total = 0
    for total in info_index:
        sum_total += total["TOTAL"]
        temp = total["Price"]
        total["Price"] = usd(temp)
        temp = total["TOTAL"]
        total["TOTAL"] = usd(temp)
    info_index[-1]["Price"] = ""
    return render_template("index.html", info_index = info_index, sum_total = usd(sum_total))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)
        elif lookup(request.form.get("symbol")) == None:
            return apology("invalid symbol", 400)
        try:
            shares = float(request.form.get("shares"))
        except:
            return apology("invalid number", 400)

        info = lookup(request.form.get("symbol"))
        price = info["price"] * shares
        cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])

        if price > cash:
            return apology("Can't afford", 400)

        db.execute("INSERT INTO logs ('user_id', 'symbol', 'name','shares','price', total_paid, current_price) VALUES (?, ?, ?, ?, ?, ?, ?)", session.get("user_id"),
                                      info["symbol"], info["name"], shares, info["price"], price, info["price"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash - price), session.get("user_id"))
        flash('Bought!')
        return redirect("/")

@app.route("/history")
@login_required
def history():

    info_history = db.execute("SELECT symbol as Symbol, shares as Shares, ABS(price) as Price, date as Transacted FROM logs WHERE user_id = ? GROUP BY symbol, name, date ORDER BY date", session["user_id"])

    for total in info_history:
        if total["Symbol"] == 'CASH':
            total["Symbol"] = 'CASH ADDED'
            total["Shares"] = ''
        temp = total["Price"]
        total["Price"] = usd(temp)



    return render_template("history.html", info_history = info_history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html", quoting=True, quote="nothing yet")
    else:
        if lookup(request.form.get("symbol")) == None:
            return apology("Invalid Symbol", 400)
        else:
            info = []
            info = lookup(request.form.get("symbol"))
            quote = (f"A share of {info['name']} ({info['symbol']}) costs ${str(info['price'])}.")
            return render_template("quote.html", quoting=False, quote=quote)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        if username == "" or not username.isalnum():
            return apology("must provide valid username", 400)
        elif len(db.execute("SELECT * FROM users WHERE username = :username", username = username)) != 0:
            return apology("username already exists", 400)
        elif not request.form.get("password") or not check_password_hash(password, request.form.get("confirmation")):
            return apology("invalid password or passwords don't match", 400)
        elif not valid_password(request.form.get("password")):
            return apology("Password must contain 6 to 12 characters, one letter, one numeric digit and no special digits", 400)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash_)", username = username, hash_ = password)
            session["user_id"] = db.execute("SELECT * FROM users WHERE username = :username",
                            username = username)[0]["id"]
            flash('Registered!')
            return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        stocks = []
        shares = []
        names = []
        for symbol in db.execute("SELECT symbol, sum(shares) as shares, name FROM logs WHERE user_id = ? GROUP BY symbol HAVING sum(shares) > 0 ORDER BY symbol", session["user_id"]):
            stocks.append(symbol["symbol"])
            shares.append(symbol["shares"])
            names.append(symbol["name"])
        return render_template("sell.html", stocks = stocks, shares = json.dumps(shares), names = json.dumps(names))
    else:
        try:
            shares_to_sell = float(request.form.get("shares"))
        except:
            return apology("invalid number", 400)

        info = lookup(request.form.get("symbol"))
        shares_available = db.execute("SELECT sum(shares) as shares FROM logs WHERE user_id = ? and symbol = ?", session.get("user_id"), info["symbol"])[0]["shares"]
        price = info["price"] *  shares_to_sell

        if shares_to_sell > shares_available:
            return apology("Too many shares", 400)

        cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
        db.execute("INSERT INTO logs ('user_id', 'symbol', 'name','shares','price', total_paid, current_price, buy_or_sell) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", session.get("user_id"),
                                      info["symbol"], info["name"], int(shares_to_sell)*-1, info["price"], price*-1, info["price"]*-1, -1)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash + price), session.get("user_id"))
        flash('Sold!')
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "GET":
        return render_template("password.html")
    else:
        old_password = db.execute("SELECT hash FROM users WHERE id = ?", session.get("user_id"))[0]["hash"]
        if not check_password_hash(old_password, request.form.get("old_password")):
            return apology("Old password incorrect", 400)
        elif not valid_password(request.form.get("new_password")):
            return apology("Password must contain 6 to 12 characters, one letter, one numeric digit and no special digits", 400)
        elif request.form.get("new_password") != request.form.get("confirmation"):
            return apology("Password and confirm password don't match", 400)
        else:
            db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(request.form.get("new_password")), session.get("user_id"))
            flash('Password Changed!')
            return redirect("/")

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    if request.method == "GET":
        add_cash = 0
        return render_template("cash.html")
    else:
        try:
            add_cash = float(request.form.get("cash"))
        except:
            return apology("invalid number", 400)

        if add_cash > 5000:
            return apology("trying to add too much money", 400)
        current_cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (add_cash + current_cash), session.get("user_id"))
        db.execute("INSERT INTO logs ('user_id', 'symbol', 'name','shares','price', total_paid, current_price) VALUES (?, ?, ?, ?, ?, ?, ?)", session.get("user_id"),
                                      'CASH', 'CASH', 0, add_cash, add_cash, add_cash)
        flash('Cash added!')
        return redirect("/")