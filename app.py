from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'shareplate-secret-key-2024'

DB_PATH = 'shareplate.db'
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        bio TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        security_answer TEXT DEFAULT '',
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
    try:
        c.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
    except: pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
    except: pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN security_answer TEXT DEFAULT ''")
    except: pass
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db()
    foods = conn.execute(
        '''SELECT f.*, u.name as donor_name
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
        security_answer = request.form.get('security_answer', '')
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute(
                'INSERT INTO users (name, email, password, location, role, security_answer) VALUES (?,?,?,?,?,?)',
                (name, email, hashed, location, role, security_answer)
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
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f"uploads/{filename}"
        conn = get_db()
        conn.execute(
            '''INSERT INTO food (food_name, category, quantity, location, expiry, contact, notes, donor_id, image_url)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (request.form['food_name'], request.form['category'],
             request.form['quantity'], request.form['location'],
             request.form['expiry'], request.form['contact'],
             request.form.get('notes', ''), session['user_id'], image_url)
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
    location = request.args.get('location', '')
    query = '''SELECT f.*, u.name as donor_name
               FROM food f JOIN users u ON f.donor_id = u.id
               WHERE f.status = "available"'''
    params = []
    if category:
        query += ' AND f.category=?'
        params.append(category)
    if search:
        query += ' AND (f.food_name LIKE ? OR f.notes LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    if location:
        query += ' AND f.location LIKE ?'
        params.append(f'%{location}%')
    query += ' ORDER BY f.created_at DESC'
    foods = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('available.html', foods=foods, category=category, search=search, location=location)

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
    food = conn.execute('SELECT * FROM food WHERE id=? AND donor_id=?',
                        (food_id, session['user_id'])).fetchone()
    if food and food['image_url']:
        try:
            os.remove(os.path.join('static', food['image_url']))
        except: pass
    conn.execute('DELETE FROM food WHERE id=? AND donor_id=?', (food_id, session['user_id']))
    conn.execute('DELETE FROM requests WHERE food_id=?', (food_id,))
    conn.commit()
    conn.close()
    flash('Listing removed.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        bio = request.form.get('bio', '')
        phone = request.form.get('phone', '')
        conn.execute(
            'UPDATE users SET name=?, location=?, bio=?, phone=? WHERE id=?',
            (name, location, bio, phone, uid)
        )
        conn.commit()
        session['user_name'] = name
        flash('Profile updated! ✅', 'success')
    user = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    total_donations = conn.execute('SELECT COUNT(*) FROM food WHERE donor_id=?', (uid,)).fetchone()[0]
    total_claims = conn.execute('SELECT COUNT(*) FROM requests WHERE receiver_id=?', (uid,)).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM food WHERE donor_id=? AND status='completed'", (uid,)).fetchone()[0]
    conn.close()
    return render_template('profile.html', user=user,
                           total_donations=total_donations,
                           total_claims=total_claims,
                           completed=completed)

ADMIN_EMAIL = 'admin@shareplate.com'

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    foods = conn.execute('''SELECT f.*, u.name as donor_name
                            FROM food f JOIN users u ON f.donor_id=u.id
                            ORDER BY f.created_at DESC''').fetchall()
    stats = {
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_food': conn.execute("SELECT COUNT(*) FROM food").fetchone()[0],
        'available': conn.execute("SELECT COUNT(*) FROM food WHERE status='available'").fetchone()[0],
        'completed': conn.execute("SELECT COUNT(*) FROM food WHERE status='completed'").fetchone()[0],
        'total_claims': conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
    }
    conn.close()
    return render_template('admin.html', users=users, foods=foods, stats=stats)

@app.route('/admin/delete-user/<int:uid>', methods=['POST'])
def admin_delete_user(uid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    conn.execute('DELETE FROM users WHERE id=?', (uid,))
    conn.execute('DELETE FROM food WHERE donor_id=?', (uid,))
    conn.execute('DELETE FROM requests WHERE receiver_id=?', (uid,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/delete-food/<int:fid>', methods=['POST'])
def admin_delete_food(fid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    conn.execute('DELETE FROM food WHERE id=?', (fid,))
    conn.execute('DELETE FROM requests WHERE food_id=?', (fid,))
    conn.commit()
    conn.close()
    flash('Food listing deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        try:
            email = request.form.get('email', '')
            security_answer = request.form.get('security_answer', '').strip().lower()
            new_password = request.form.get('new_password', '')
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if user:
                stored_answer = (user['security_answer'] or '').strip().lower()
                if stored_answer == security_answer:
                    hashed = generate_password_hash(new_password)
                    conn.execute('UPDATE users SET password=? WHERE email=?', (hashed, email))
                    conn.commit()
                    conn.close()
                    flash('Password reset successful! Please login.', 'success')
                    return redirect(url_for('login'))
                conn.close()
                flash('Security answer is incorrect.', 'danger')
            else:
                conn.close()
                flash('Email not found.', 'danger')
        except Exception:
            flash('Something went wrong. Please try again.', 'danger')
    return render_template('forgot_password.html')

@app.route('/reset-db')
def reset_db():
    if os.path.exists('shareplate.db'):
        os.remove('shareplate.db')
    init_db()
    return 'Database reset successfully! <a href="/">Go Home</a>'

if __name__ == '__main__':
    init_db()
    app.run(debug=True)