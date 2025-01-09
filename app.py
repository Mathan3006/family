from flask import Flask, render_template, request, redirect, url_for, flash, g
import os
import pandas as pd
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# File initialization logic
USERS_FILE = "users.csv"
EXPENSES_FILE = "expenses.xlsx"

def initialize_files():
    if not os.path.exists(USERS_FILE):
        pd.DataFrame(columns=["Username", "Password"]).to_csv(USERS_FILE, index=False)

    if not os.path.exists(EXPENSES_FILE):
        pd.DataFrame(columns=["Date", "Username", "Expense", "Reason", "Income"]).to_excel(EXPENSES_FILE, index=False, engine="openpyxl")

initialize_files()

# Add before_request function here
@app.before_request
def before_request():
    """Sets the current_user globally based on the username passed."""
    g.current_user = request.args.get('username', None)

# Flask routes
@app.route('/')
def home():
    return render_template("home.html")

@app.route('/register', methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('register_user'))

        users = pd.read_csv(USERS_FILE)
        if username in users["Username"].values:
            flash("Username already exists!", "error")
            return redirect(url_for('register_user'))

        new_user = pd.DataFrame({"Username": [username], "Password": [password]})
        new_user.to_csv(USERS_FILE, mode='a', header=False, index=False)
        flash("User registered successfully!", "success")
        return redirect(url_for('login_user'))

    return render_template('register.html')

@app.route('/login', methods=["GET", "POST"])
def login_user():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        users = pd.read_csv(USERS_FILE)
        user = users[users["Username"] == username]

        if user.empty or password != str(user["Password"].iloc[0]):
            flash("Invalid username or password!", "error")
            return redirect(url_for('login_user'))

        flash(f"Welcome, {username}!", "success")
        return redirect(url_for('dashboard', username=username))

    return render_template('login.html')

@app.route('/dashboard/<username>', methods=["GET", "POST"])
def dashboard(username):
    if request.method == "POST":
        try:
            expense = float(request.form['expense'])
            reason = request.form['reason']
            income = float(request.form['income'] or 0)

            # Get the current date and time
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read the existing expenses
            expenses = pd.read_excel(EXPENSES_FILE)

            # Add the new expense to the DataFrame
            new_entry = pd.DataFrame({
                "Date": [date],
                "Username": [username],
                "Expense": [expense],
                "Reason": [reason],
                "Income": [income]
            })
            expenses = pd.concat([expenses, new_entry], ignore_index=True)

            # Save the updated DataFrame to the file
            expenses.to_excel(EXPENSES_FILE, index=False, engine="openpyxl")

            flash("Expense recorded successfully!", "success")
        except ValueError:
            flash("Invalid input! Please ensure all fields are filled correctly.", "error")
        except Exception as e:
            flash(f"An error occurred: {e}", "error")

    # Fetch expenses for the current user
    expenses = pd.read_excel(EXPENSES_FILE)
    user_expenses = expenses[expenses["Username"] == username]
    return render_template('dashboard.html', username=username, expenses=user_expenses)

@app.route('/view_expenses/<username>')
def view_expenses(username):
    expenses = pd.read_excel(EXPENSES_FILE)
    user_expenses = expenses[expenses["Username"] == username]
    return render_template('view_expenses.html', expenses=user_expenses)
@app.route('/delete_expense/<int:expense_id>', methods=["POST"])
def delete_expense(expense_id):
    try:
        # Read the expenses file
        expenses = pd.read_excel(EXPENSES_FILE)

        # Check if the ID is valid
        if 0 <= expense_id < len(expenses):
            # Drop the expense by index
            expenses = expenses.drop(expense_id).reset_index(drop=True)
            # Save the updated expenses back to the file
            expenses.to_excel(EXPENSES_FILE, index=False, engine="openpyxl")
            flash("Expense deleted successfully!", "success")
        else:
            flash("Invalid expense ID!", "error")
    except Exception as e:
        flash(f"Error deleting expense: {e}", "error")

    # Redirect back to the dashboard
    return redirect(request.referrer or url_for('dashboard', username=g.current_user))


@app.route('/logout')
def logout():
    flash("You have logged out.", "info")
    return redirect(url_for('login_user'))

# Run the app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
