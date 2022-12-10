import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get all the stocks and the shares of each stock the user owns
    rows = db.execute("SELECT symbol, total_shares FROM (SELECT symbol, SUM(shares) AS total_shares FROM (SELECT user_id, symbol, shares FROM purchases WHERE user_id = ?) GROUP BY symbol) WHERE total_shares > 0", session["user_id"])

    # Additional properties that we need for each stock
    # We will create a dict and also add properties from DB and from lookup
    # The new dict will be stored in stocks
    stocks = []

    # Total value of all the stocks the user is holding currently
    total_stock_value = 0

    # For each row
    for row in rows:
        stock_data = lookup(row["symbol"])
        stock = {
            "symbol": row["symbol"],
            "name": stock_data["name"],
            "shares": row["total_shares"],
            "price": stock_data["price"],
            "total": (stock_data["price"]) * (row["total_shares"])
        }
        stocks.append(stock)
        total_stock_value += stock["shares"] * stock["price"]

    # Get the current cash of the user
    rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    available_cash = rows[0]["cash"]

    # Render the template and populate the table with stocks, total_stock_value and
    # available_cash
    return render_template("index.html", stocks=stocks, total=total_stock_value, cash=available_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Symbol is blank
        symbol = request.form.get("symbol")
        if not symbol or len(symbol) == 0:
            return apology("Symbol is blank", 400)

        # Symbol doesn't exist
        try:
            stock = lookup(symbol)
        except:
            return apology("Invalid Symbol", 400)

        if not stock:
            return apology("Symbol doesn't exist", 400)

        # Shares is blank
        shares = request.form.get("shares")
        if not shares:
            return apology("Number of shares is blank", 400)

        # Shares is fractional
        #if type(shares) is not int:
        #    return apology("Shares is not int", 400)

        # Shares is zero or negative
        try:
            shares = int(shares)
        except:
            return apology("Not an int", 400)
        if shares < 1:
            return apology("Please provide a positive input", 400)

        # Already have the stock value from previous lookup

        # Get the available cash for the current user making the request
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = rows[0]["cash"]

        # TODO create indexs done
        # TODO insert appropriate values in the db
        # user_id from session
        # symbol from stock["symbol"]
        # price from (shares * stock["price"])
        # date_of_purchase current date time, DB will do it automatically

        # Check if the user can buy the amount of shares
        total_cost = stock["price"] * shares
        if total_cost > available_cash:
            return apology("Not enough cash!", 400)

        # Purchase the stock essentialy means storing the info into DB
        #db.execute("INSERT INTO purchases (user_id, symbol, price) VALUES (?, ?, ?)", session["user_id"], stock["symbol"], total_cost)
        # WRONG DB SCHEMA PURCHASES NEED TO STORE NUMBER OF SHARES ALSO
        # DROP THE TABLE AND DO IT AGAIN

        # Deduct the amount of cash from the user
        db.execute("UPDATE users SET cash = ? WHERE id = ? ", (available_cash - total_cost), session["user_id"])

        # Make the purchase
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", session["user_id"], stock["symbol"], shares, stock["price"])

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Get the data
    rows = db.execute("SELECT symbol, shares, price, transacted FROM purchases WHERE user_id = ?", session["user_id"])

    return render_template("history.html", rows=rows)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    """Get stock quote."""
    if request.method == "POST":

        # Validate symbol
        symbol = request.form.get("symbol")
        if not symbol or len(symbol) == 0:
            return apology("Symbol is blank", 400)

        # Get the stock info from symbol
        try:
            stock = lookup(symbol)
        except:
            return apology("Invalid stock symbol", 400)
        if not stock:
            return apology("Invalid stock symbol", 400)

        # Pass the dict to the template
        return render_template("quoted.html", stock=stock)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":

        # Validate username
        username = request.form.get("username")
        if not username or len(username) == 0:
            return apology("Username is blank", 400)

        # Already exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("Username already exists", 400)

        # Validate password
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not password or len(password) == 0:
            return apology("Password is blank", 400)
        if not confirmation or len(confirmation) == 0:
            return apology("Confirm password is blank", 400)

        # Passwords don't match
        if password != confirmation:
            return apology("Passwords do not match")

        # Save the user in db
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))

        # Redirect the user to login page
        return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    #stocks = ["GOOG", "AAPL", "MSFT", "NFLX"]

    rows = db.execute("SELECT symbol FROM (SELECT symbol, total_shares FROM (SELECT symbol, SUM(shares) AS total_shares FROM (SELECT user_id, symbol, shares FROM purchases WHERE user_id = ?) GROUP BY symbol) WHERE total_shares > 0)", session["user_id"])

    stocks = []
    for row in rows:
        stocks.append(row["symbol"])

    if request.method == "POST":
        # Check for stock symbol
        symbol = request.form.get("symbol")
        # Is blank ?
        if not symbol:
            return apology("Symbol is blank", 400)

        # Check for shares
        shares = request.form.get("shares", 400)

        # Check if it's int
        try:
            shares = int(shares)
        except:
            return apology("Not an int", 400)

        # Is blank ?
        if not shares:
            return apology("Shares is blank", 400)

        # Check if shares is positive
        if shares <= 0:
            return apology("Number of shares must be positive", 400)

        # We know that the stock symbol is present
        # But we don't know if it's a valid one
        # So we query DB
        # We get the results
        # So we compare and found that it's currently there but
        # What if the user is very fast and actually makes a transaction
        # in the mean time ?
        # Race condition

        # Check how many shares of the given symbol the user actually owns
        rows = db.execute("SELECT SUM(shares) AS available_shares FROM (SELECT symbol, shares FROM (SELECT symbol, shares FROM purchases WHERE user_id = ?) WHERE symbol = ?)", session["user_id"], symbol)
        # rows will actually be a single row
        available_shares = rows[0]["available_shares"]

        # Check if the user owns any stock of the given symbol
        if available_shares < 1:
            return apology("You don't own this stock", 400)

        # Check if the user has at least the number of shares of the stock
        # he wants to sell
        if shares > available_shares:
            return apology("You don't have that many", 400)

        # It's time to sell the stock

        # Get the stock's current price
        try:
            stock = lookup(symbol)
        except:
            return apology("Invalid symbol", 400)

        total_price = stock["price"] * shares

        # Get the user's balance
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = rows[0]["cash"]

        # Add the cash to the user's account
        db.execute("UPDATE users SET cash = ? WHERE id = ? ", (available_cash + total_price), session["user_id"])

        # Insert the record into the DB
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", session["user_id"], stock["symbol"], (shares * -1), stock["price"])

        return redirect("/")
    else:
        return render_template("sell.html", stocks=stocks)
