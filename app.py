from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import os
import time
from datetime import datetime
from urllib.parse import urlparse
from psycopg2 import IntegrityError

app = Flask(__name__)
app.secret_key = '3a6094cbe292ff1717ec6e11401673a8b8641daf2dd8821a2fab945f8ba49906'

# Database Connection
def get_db_connection():
    """Robust Neon PostgreSQL connection handler"""
    max_retries = 5
    db_url = 'postgresql://neondb_owner:npg_A8d1ackmUwGN@ep-royal-darkness-a57zuf7k-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require'
    
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                db_url,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Database connection failed after {max_retries} attempts: {str(e)}")
            time.sleep(2 ** attempt)

# Database Query Helper Function
def execute_query(query, params=None, fetch=False):
    """Execute a SQL query and return results if needed"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        if fetch:
            result = cur.fetchall()
            return result
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

# Initialize Database
def init_db():
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
                type VARCHAR(10) NOT NULL,
                income FLOAT,
                reason VARCHAR(100)
            )
        """)
        
        execute_query("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
    except Exception as e:
        print(f"Database init error: {e}")
        raise

# Test route
@app.route('/test-db')
def test_db():
    try:
        version = execute_query("SELECT version()", fetch=True)
        return f"Connected to PostgreSQL: {version[0][0]}"
    except Exception as e:
        return f"Connection failed: {str(e)}", 500 

# Routes
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
            
            if user and user[0][1] == password:
                session['user_id'] = user[0][0]
                return redirect(url_for('home'))
            
            flash('Invalid username or password', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            user_id = execute_query(
                "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING user_id",
                (username, password),
                fetch=True
            )
            session['user_id'] = user_id[0][0]
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        except IntegrityError:
            flash('Username already exists', 'error')
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

@app.route('/check_session')
def check_session():
    return {
        'user_id': session.get('user_id'),
        'session': dict(session)
    }

@app.route('/health')
def health_check():
    try:
        execute_query("SELECT 1")
        session['test'] = 'works'
        return {
            'database': 'connected',
            'session': 'working',
            'status': 'healthy'
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
