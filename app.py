from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
from datetime import datetime
from psycopg2 import IntegrityError

app = Flask(__name__)
app.secret_key = '3a6094cbe292ff1717ec6e11401673a8b8641daf2dd8821a2fab945f8ba49906'

def get_db_connection():
    """Safe database connection handler"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://'),
                connect_timeout=5
            )
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
            time.sleep(1)

# Initialize Database
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create users table with user_id as primary key
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password VARCHAR(200) NOT NULL
            )
        """)
        
        # Create transactions table with your specified columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount FLOAT NOT NULL,
                type VARCHAR(10) NOT NULL,
                income FLOAT,
                reason VARCHAR(100)
            )
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

# Routes
@app.route('/')
def home():
    if 'user_id' not in session:
        return render_template('index.html')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT date, amount, type, income, reason 
            FROM transactions 
            WHERE user_id = %s 
            ORDER BY date DESC 
            LIMIT 5
        """, (session['user_id'],))
        transactions = cur.fetchall()
        return render_template('index.html', transactions=transactions)
    except Exception as e:
        flash('Error loading recent transactions', 'error')
        return render_template('index.html', transactions=[])
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, password FROM users WHERE username = %s",
                (username,)
            )
            user = cur.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                return redirect(url_for('home'))
            flash('Invalid username or password', 'error')
        except Exception as e:
            flash('Login failed. Please try again.', 'error')
        finally:
            if 'cur' in locals(): cur.close()
            if 'conn' in locals(): conn.close()
    
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
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check username exists
            cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                flash('Username already exists', 'error')
                return redirect(url_for('register'))
            
            # Insert new user
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING user_id",
                (username, generate_password_hash(password))
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Auto-login after registration
            session['user_id'] = user_id
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
            if 'conn' in locals(): conn.rollback()
        finally:
            if 'cur' in locals(): cur.close()
            if 'conn' in locals(): conn.close()
    
    return render_template('register.html')

@app.route('/transactions', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    cur = None
    
    try:
        # Required fields
        transaction_type = request.form['type']
        amount = float(request.form['amount'])
        
        # Conditional fields
        income = float(request.form['income']) if transaction_type == 'income' else None
        reason = request.form.get('reason')

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO transactions 
            (user_id, amount, type, income, reason)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], amount, transaction_type, income, reason))
        
        conn.commit()
        flash('Transaction added successfully!', 'success')
        
    except ValueError:
        flash('Invalid amount entered', 'error')
    except Exception as e:
        flash(f'Failed to add transaction: {str(e)}', 'error')
        if conn: conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()
    
    return redirect(url_for('show_transactions'))

@app.route('/transactions')
def show_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT date, amount, type, income, reason 
            FROM transactions 
            WHERE user_id = %s 
            ORDER BY date DESC
        """, (session['user_id'],))
        transactions = cur.fetchall()
        return render_template('transactions.html', transactions=transactions)
    except Exception as e:
        flash('Failed to load transactions', 'error')
        return render_template('transactions.html', transactions=[])
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@app.route('/delete/<int:transaction_id>')
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM transactions WHERE transaction_id = %s AND user_id = %s",
            (transaction_id, session['user_id'])
        )
        conn.commit()
        flash('Transaction deleted successfully!', 'success')
    except Exception as e:
        flash('Failed to delete transaction', 'error')
        if 'conn' in locals(): conn.rollback()
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
    
    return redirect(url_for('show_transactions'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)