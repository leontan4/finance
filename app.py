import os
import json
import ast

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

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
    user_data = db.execute("SELECT * FROM users")[session["user_id"]-1]
    user_id = user_data["id"]
    username = user_data["username"]
    print(f'We are in index {session["user_id"]}')
    print(type(session["user_id"]))

    portfolio_data = db.execute("SELECT * FROM investments WHERE user_id = ? ORDER BY value desc", user_id)
    total_investments = db.execute("SELECT SUM(value) as 'total' FROM investments WHERE user_id = ?", user_id)[0]['total']

    if total_investments is None:
        total_investments = 0

    return render_template("portfolio.html", name=username, portfolio=portfolio_data, total=total_investments)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Sometimes break because the json format is not in double quotes (""). single quote('') strings will return error
    # JSON format should be in double quotes and not in single quotes
    stock_data = request.args.get("stock_data_load")

    if request.method == 'POST':

        # Query user info from database
        user_data = db.execute("SELECT * FROM users")[session["user_id"]-1]
        user_id = user_data["id"]
        cash = user_data["cash"]

        # Gathering stock purchased
        stock_info = json.loads(stock_data)
        stockPrice = float(stock_info["price"])
        stock_symbol = stock_info["symbol"]
        numShares = float(request.form.get("numShares"))
        totalCost = stockPrice * numShares

        if cash < totalCost:
            return apology("TODO")

        # Query current portfolio associate with current user id
        portfolio = db.execute("SELECT * FROM investments WHERE user_id = ? AND symbol = ?", user_id, stock_symbol)

        if not portfolio:
            # Add new stock into portfolio
            db.execute("INSERT INTO investments (company, symbol, quantity, price, value, user_id) \
                VALUES (?, ?, ?, ?, ?, ?)", stock_info["name"], stock_info["symbol"], numShares, stockPrice, totalCost, user_id)
        else:
            # Insert stock data into investments database
            # if the stock already exist then we just update the quality and totalValue
            newShares = portfolio[0]["quantity"] + numShares
            newCost = portfolio[0]["value"] + totalCost
            db.execute("UPDATE investments SET quantity = ?, value = ? WHERE user_id = ? and symbol = ?", newShares, newCost, user_id, stock_symbol)

        # Deduct money from user table
        remainder = cash - totalCost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder, user_id)

        transaction_data = {
            "symbol": stock_symbol,
            "price": stockPrice,
            "quantity": numShares,
            "value": totalCost,
            "action": "buy",
            "user_id": user_id
        }

        return redirect(url_for('history', transaction_data=transaction_data))

    if stock_data is None:
        return redirect("/quote")

    stock=json.loads(stock_data)
    print(type(stock))
    print(stock)
    return render_template("buy.html", stock=stock)


@app.route("/history")
@login_required
def history():
    user_data = db.execute("SELECT * FROM users")[session["user_id"]-1]
    user_id = user_data["id"]
    transaction_data = request.args.get("transaction_data")

    if transaction_data is not None:
        data = ast.literal_eval(transaction_data)
        symbol = data["symbol"]
        quantity = data["quantity"]
        price = data["price"]
        value = data["value"]
        action = data["action"].title()
        user_id = data["user_id"]

        db.execute("INSERT INTO transactions (symbol, quantity, price, value, actions, user_id) VALUES(?, ?, ?, ?, ?, ?)", \
                   symbol, quantity, price, value, action, user_id)
        return redirect("/")

    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id);

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    add_stock = request.args.get("stock_data_load")
    if request.method == 'POST' or add_stock is not None:
        stock_symbol=json.loads(add_stock)["symbol"] if request.method == 'GET' else request.form.get("symbol")
        stock_data = lookup(stock_symbol)

        return render_template("quoted.html", stock=stock_data)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == 'POST':
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))
        # confirm_password = request.form.get("confirm_password")
               # if password != confirm_password:
        #     return apology("Password do not match")

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password)
        return redirect("/login")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stock_data = request.args.get("stock_data_load")

    """Sell shares of stock"""
    if request.method == 'POST':

        # Query user info from database
        user_data = db.execute("SELECT * FROM users")[session["user_id"]-1]
        user_id = user_data["id"]
        curr_cash = user_data["cash"]

        # Gathering stock purchased
        stock_info = json.loads(stock_data)
        shares_to_sell_price = float(stock_info["price"])
        stock_symbol = stock_info["symbol"]
        shares_to_sell = float(request.form.get("numShares"))
        shares_to_sell_value = shares_to_sell_price * shares_to_sell

        # Query current portfolio associate with current user id
        portfolio = db.execute("SELECT * FROM investments WHERE user_id = ? AND symbol = ?", user_id, stock_symbol)

        prev_shares_on_hand = portfolio[0]["quantity"]
        prev_stock_value_on_hand = portfolio[0]["value"]

        # Update stock investments after selling stock
        curr_shares_on_hand = prev_shares_on_hand - shares_to_sell
        curr_shares_value = prev_stock_value_on_hand - shares_to_sell_value
        db.execute("UPDATE investments SET quantity = ?, value = ? WHERE user_id = ? and symbol = ?", curr_shares_on_hand, curr_shares_value, user_id, stock_symbol)

        if curr_shares_on_hand == 0:
            db.execute("DELETE FROM investments WHERE symbol = ?", stock_symbol)

        # Update user's current cash on hand after selling stock
        updated_share_value = curr_cash + shares_to_sell_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?",  updated_share_value, user_id)


        transaction_data = {
            "symbol": stock_symbol,
            "price": shares_to_sell_price,
            "quantity": shares_to_sell,
            "value": shares_to_sell_value,
            "action": "sell",
            "user_id": user_id
        }

        return redirect(url_for('history', transaction_data=transaction_data))

    stock=json.loads(stock_data)
    return render_template("sell.html", stock=stock)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)