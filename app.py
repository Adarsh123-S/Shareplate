from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'shareplate-secret-key-2024'

DB_PATH = 'shareplate.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        location TEXT,
        role TEXT DEFAULT 'both',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS food (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_name TEXT NOT NULL,
        category TEXT,
        quantity TEXT NOT NULL,
        location TEXT NOT NULL,
        expiry TEXT NOT NULL,
        contact TEXT,
        notes TEXT,
        status TEXT DEFAULT 'available',
        donor_id INTEGER,
        image_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (donor_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER,
        receiver_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (food_id) REFERENCES food(id),
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    foods = conn.execute(
        '''SELECT f.*, u.name as donor_name, u.location as donor_location
           FROM food f JOIN users u ON f.donor_id = u.id
           WHERE f.status = "available"
           ORDER BY f.created_at DESC LIMIT 6'''
    ).fetchall()
    stats = {
        'total_food': conn.execute("SELECT COUNT(*) FROM food").fetchone()[0],
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'completed': conn.execute("SELECT COUNT(*) FROM food WHERE status='completed'").fetchone()[0],
    }
    conn.close()
    return render_template('index.html', foods=foods, stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        location = request.form['location']
        role = request.form['role']
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute(
                'INSERT INTO users (name, email, password, location, role) VALUES (?,?,?,?,?)',
                (name, email, hashed, location, role)
            )
            conn.commit()
            conn.close()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = get_db()
    my_donations = conn.execute(
        'SELECT * FROM food WHERE donor_id=? ORDER BY created_at DESC', (uid,)
    ).fetchall()
    my_claims = conn.execute(
        '''SELECT r.*, f.food_name, f.location, f.expiry, u.name as donor_name
           FROM requests r
           JOIN food f ON r.food_id = f.id
           JOIN users u ON f.donor_id = u.id
           WHERE r.receiver_id=? ORDER BY r.created_at DESC''', (uid,)
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', my_donations=my_donations, my_claims=my_claims)

@app.route('/add-food', methods=['GET', 'POST'])
def add_food():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute(
            '''INSERT INTO food (food_name, category, quantity, location, expiry, contact, notes, donor_id)
               VALUES (?,?,?,?,?,?,?,?)''',
            (request.form['food_name'], request.form['category'],
             request.form['quantity'], request.form['location'],
             request.form['expiry'], request.form['contact'],
             request.form.get('notes', ''), session['user_id'])
        )
        conn.commit()
        conn.close()
        flash('Food listed successfully! 🎉', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_food.html')

@app.route('/available')
def available():
    conn = get_db()
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    query = '''SELECT f.*, u.name as donor_name
               FROM food f JOIN users u ON f.donor_id = u.id
               WHERE f.status = "available"'''
    params = []
    if category:
        query += ' AND f.category=?'
        params.append(category)
    if search:
        query += ' AND (f.food_name LIKE ? OR f.location LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    query += ' ORDER BY f.created_at DESC'
    foods = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('available.html', foods=foods, category=category, search=search)

@app.route('/claim/<int:food_id>', methods=['POST'])
def claim_food(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = get_db()
    food = conn.execute('SELECT * FROM food WHERE id=?', (food_id,)).fetchone()
    if not food or food['status'] != 'available':
        flash('This food is no longer available.', 'warning')
        conn.close()
        return redirect(url_for('available'))
    if food['donor_id'] == uid:
        flash("You can't claim your own donation.", 'warning')
        conn.close()
        return redirect(url_for('available'))
    existing = conn.execute(
        'SELECT * FROM requests WHERE food_id=? AND receiver_id=?', (food_id, uid)
    ).fetchone()
    if existing:
        flash('You already claimed this food.', 'info')
        conn.close()
        return redirect(url_for('available'))
    conn.execute('INSERT INTO requests (food_id, receiver_id) VALUES (?,?)', (food_id, uid))
    conn.execute('UPDATE food SET status="requested" WHERE id=?', (food_id,))
    conn.commit()
    conn.close()
    flash('Food claimed! Contact the donor to arrange pickup. 🙌', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update-status/<int:food_id>/<status>')
def update_status(food_id, status):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    allowed = ['available', 'requested', 'collected', 'completed']
    if status not in allowed:
        flash('Invalid status.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db()
    food = conn.execute('SELECT * FROM food WHERE id=? AND donor_id=?',
                        (food_id, session['user_id'])).fetchone()
    if not food:
        flash('Not authorized.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    conn.execute('UPDATE food SET status=? WHERE id=?', (status, food_id))
    conn.commit()
    conn.close()
    flash(f'Status updated to {status}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-food/<int:food_id>', methods=['POST'])
def delete_food(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM food WHERE id=? AND donor_id=?', (food_id, session['user_id']))
    conn.execute('DELETE FROM requests WHERE food_id=?', (food_id,))
    conn.commit()
    conn.close()
    flash('Listing removed.', 'info')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
