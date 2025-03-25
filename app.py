from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
from datetime import datetime
from psycopg2 import IntegrityError
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '3a6094cbe292ff1717ec6e11401673a8b8641daf2dd8821a2fab945f8ba49906')

def get_db_connection():
    """Enhanced database connection handler with Neon-specific optimizations"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            db_url = os.getenv('DATABASE_URL')
            
            # Validate and format the database URL
            if not db_url:
                raise ValueError("DATABASE_URL environment variable not set")
            
            # Parse and reconstruct URL to ensure proper formatting
            parsed = urlparse(db_url)
            
            # Force SSL for Neon and convert protocol if needed
            if 'neon.tech' in parsed.hostname:
                if db_url.startswith('postgres://'):
                    db_url = db_url.replace('postgres://', 'postgresql://', 1)
                if 'sslmode' not in db_url:
                    db_url += '?sslmode=require'
            
            conn = psycopg2.connect(
                db_url,
                connect_timeout=5,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
            time.sleep(1 + attempt)  # Exponential backoff

def execute_query(query, params=None, fetch=False):
    """Safe query execution helper"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            return cur.fetchall()
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def init_db():
    """Initialize database with proper error handling"""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password VARCHAR(200) NOT NULL
            )
        """)
        
        execute_query("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount FLOAT NOT NULL,
                type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
                income FLOAT,
                reason VARCHAR(100),
                CONSTRAINT income_constraint CHECK (
                    (type = 'income' AND income IS NOT NULL) OR
                    (type = 'expense' AND income IS NULL)
            )
        """)
        
        # Create indexes for better performance
        execute_query("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)")
        execute_query("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

# Routes (maintaining all original functionality)
@app.route('/')
def home():
    if 'user_id' not in session:
        return render_template('index.html')
    
    try:
        transactions = execute_query(
            """SELECT date, amount, type, income, reason 
               FROM transactions 
               WHERE user_id = %s 
               ORDER BY date DESC 
               LIMIT 5""",
            (session['user_id'],),
            fetch=True
        )
        return render_template('index.html', transactions=transactions)
    except Exception as e:
        flash('Error loading recent transactions', 'error')
        return render_template('index.html', transactions=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            user = execute_query(
                "SELECT user_id, password FROM users WHERE username = %s",
                (username,),
                fetch=True
            )
            
            if user and check_password_hash(user[0][1], password):
                session['user_id'] = user[0][0]
                return redirect(url_for('home'))
            flash('Invalid username or password', 'error')
        except Exception as e:
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if len(username) > 80:
            flash('Username too long (max 80 chars)', 'error')
            return redirect(url_for('register'))
            
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return redirect(url_for('register'))

        try:
            # Check username exists
            existing = execute_query(
                "SELECT user_id FROM users WHERE username = %s",
                (username,),
                fetch=True
            )
            if existing:
                flash('Username already exists', 'error')
                return redirect(url_for('register'))
            
            # Insert new user
            user_id = execute_query(
                "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING user_id",
                (username, generate_password_hash(password)),
                fetch=True
            )[0][0]
            
            # Auto-login after registration
            session['user_id'] = user_id
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/transactions', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        transaction_type = request.form['type']
        amount = float(request.form['amount'])
        income = float(request.form['income']) if transaction_type == 'income' else None
        reason = request.form.get('reason')

        execute_query(
            """INSERT INTO transactions 
               (user_id, amount, type, income, reason)
               VALUES (%s, %s, %s, %s, %s)""",
            (session['user_id'], amount, transaction_type, income, reason)
        )
        flash('Transaction added successfully!', 'success')
    except ValueError:
        flash('Invalid amount entered', 'error')
    except Exception as e:
        flash(f'Failed to add transaction: {str(e)}', 'error')
    
    return redirect(url_for('show_transactions'))

@app.route('/transactions')
def show_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        transactions = execute_query(
            """SELECT transaction_id, date, amount, type, income, reason 
               FROM transactions 
               WHERE user_id = %s 
               ORDER BY date DESC""",
            (session['user_id'],),
            fetch=True
        )
        return render_template('transactions.html', transactions=transactions)
    except Exception as e:
        flash('Failed to load transactions', 'error')
        return render_template('transactions.html', transactions=[])

@app.route('/delete/<int:transaction_id>')
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        execute_query(
            "DELETE FROM transactions WHERE transaction_id = %s AND user_id = %s",
            (transaction_id, session['user_id'])
        )
        flash('Transaction deleted successfully!', 'success')
    except Exception as e:
        flash('Failed to delete transaction', 'error')
    
    return redirect(url_for('show_transactions'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
