from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import cloudinary
import cloudinary.uploader
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'shareplate-secret-key-2024'

DB_PATH = 'shareplate.db'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        review TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (food_id) REFERENCES food(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        food_id INTEGER,
        sender_id INTEGER,
        receiver_id INTEGER,
        message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (food_id) REFERENCES food(id),
        FOREIGN KEY (sender_id) REFERENCES users(id),
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

init_db()

def add_notification(user_id, message):
    try:
        conn = get_db()
        conn.execute('INSERT INTO notifications (user_id, message) VALUES (?,?)', (user_id, message))
        conn.commit()
        conn.close()
    except: pass

@app.route('/')
def index():
    conn = get_db()
    foods = conn.execute(
        '''SELECT f.*, u.name as donor_name,
           COALESCE(AVG(r.rating), 0) as avg_rating,
           COUNT(r.id) as rating_count
           FROM food f JOIN users u ON f.donor_id = u.id
           LEFT JOIN ratings r ON f.id = r.food_id
           WHERE f.status = "available"
           GROUP BY f.id
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
    notifications = conn.execute(
        'SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 10', (uid,)
    ).fetchall()
    unread_count = conn.execute(
        'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (uid,)
    ).fetchone()[0]
    conn.close()
    return render_template('dashboard.html', my_donations=my_donations,
                           my_claims=my_claims, notifications=notifications,
                           unread_count=unread_count)

@app.route('/mark-notifications-read')
def mark_notifications_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (session['user_id'],))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/add-food', methods=['GET', 'POST'])
def add_food():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                try:
                    upload_result = cloudinary.uploader.upload(
                        file, folder='shareplate',
                        transformation=[{'width': 800, 'height': 600, 'crop': 'fill'}]
                    )
                    image_url = upload_result['secure_url']
                except:
                    flash('Image upload failed, listing without image.', 'warning')
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
    min_rating = request.args.get('min_rating', '')
    sort = request.args.get('sort', 'newest')
    query = '''SELECT f.*, u.name as donor_name,
               COALESCE(AVG(r.rating), 0) as avg_rating,
               COUNT(r.id) as rating_count
               FROM food f JOIN users u ON f.donor_id = u.id
               LEFT JOIN ratings r ON f.id = r.food_id
               WHERE f.status = "available"'''
    params = []
    if category:
        query += ' AND f.category=?'
        params.append(category)
    if search:
        query += ' AND (f.food_name LIKE ? OR f.notes LIKE ? OR f.location LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if location:
        query += ' AND f.location LIKE ?'
        params.append(f'%{location}%')
    query += ' GROUP BY f.id'
    if min_rating:
        query += f' HAVING avg_rating >= {min_rating}'
    if sort == 'rating':
        query += ' ORDER BY avg_rating DESC'
    elif sort == 'expiry':
        query += ' ORDER BY f.expiry ASC'
    else:
        query += ' ORDER BY f.created_at DESC'
    foods = conn.execute(query, params).fetchall()
    recommendations = []
    if session.get('user_id'):
        recommendations = conn.execute(
            '''SELECT f.*, u.name as donor_name,
               COALESCE(AVG(r.rating), 0) as avg_rating
               FROM food f JOIN users u ON f.donor_id = u.id
               LEFT JOIN ratings r ON f.id = r.food_id
               WHERE f.status = "available" AND f.donor_id != ?
               GROUP BY f.id
               ORDER BY avg_rating DESC, f.created_at DESC LIMIT 3''',
            (session['user_id'],)
        ).fetchall()
    conn.close()
    return render_template('available.html', foods=foods, category=category,
                           search=search, location=location,
                           min_rating=min_rating, sort=sort,
                           recommendations=recommendations)

@app.route('/food/<int:food_id>')
def food_detail(food_id):
    conn = get_db()
    food = conn.execute(
        '''SELECT f.*, u.name as donor_name, u.email as donor_email, u.phone as donor_phone
           FROM food f JOIN users u ON f.donor_id = u.id
           WHERE f.id=?''', (food_id,)
    ).fetchone()
    if not food:
        flash('Food not found.', 'danger')
        conn.close()
        return redirect(url_for('available'))
    reviews = conn.execute(
        '''SELECT r.*, u.name as reviewer_name
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.food_id=? ORDER BY r.created_at DESC''', (food_id,)
    ).fetchall()
    avg_rating = conn.execute(
        'SELECT COALESCE(AVG(rating), 0) FROM ratings WHERE food_id=?', (food_id,)
    ).fetchone()[0]
    messages = conn.execute(
        '''SELECT m.*, u.name as sender_name
           FROM messages m JOIN users u ON m.sender_id = u.id
           WHERE m.food_id=? ORDER BY m.created_at ASC''', (food_id,)
    ).fetchall()
    conn.close()
    return render_template('food_detail.html', food=food, reviews=reviews,
                           avg_rating=avg_rating, messages=messages)

@app.route('/rate/<int:food_id>', methods=['POST'])
def rate_food(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    rating = request.form.get('rating', 5)
    review = request.form.get('review', '')
    conn = get_db()
    existing = conn.execute(
        'SELECT * FROM ratings WHERE food_id=? AND user_id=?', (food_id, uid)
    ).fetchone()
    if existing:
        conn.execute('UPDATE ratings SET rating=?, review=? WHERE food_id=? AND user_id=?',
                     (rating, review, food_id, uid))
    else:
        conn.execute('INSERT INTO ratings (food_id, user_id, rating, review) VALUES (?,?,?,?)',
                     (food_id, uid, rating, review))
    conn.commit()
    conn.close()
    flash('Rating submitted! ⭐', 'success')
    return redirect(url_for('food_detail', food_id=food_id))

@app.route('/send-message/<int:food_id>', methods=['POST'])
def send_message(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    message = request.form.get('message', '').strip()
    if not message:
        flash('Message cannot be empty.', 'warning')
        return redirect(url_for('food_detail', food_id=food_id))
    conn = get_db()
    food = conn.execute('SELECT * FROM food WHERE id=?', (food_id,)).fetchone()
    if food:
        receiver_id = food['donor_id'] if uid != food['donor_id'] else None
        if receiver_id:
            conn.execute(
                'INSERT INTO messages (food_id, sender_id, receiver_id, message) VALUES (?,?,?,?)',
                (food_id, uid, receiver_id, message)
            )
            add_notification(receiver_id, f'New message about "{food["food_name"]}"')
            conn.commit()
            flash('Message sent! 💬', 'success')
    conn.close()
    return redirect(url_for('food_detail', food_id=food_id))

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
    add_notification(food['donor_id'], f'Someone claimed your "{food["food_name"]}" listing!')
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

@app.route('/leaderboard')
def leaderboard():
    conn = get_db()
    donors = conn.execute(
        '''SELECT u.name, u.location,
           COUNT(f.id) as total,
           SUM(CASE WHEN f.status='completed' THEN 1 ELSE 0 END) as completed
           FROM users u
           LEFT JOIN food f ON u.id = f.donor_id
           GROUP BY u.id
           ORDER BY total DESC LIMIT 20'''
    ).fetchall()
    conn.close()
    return render_template('leaderboard.html', donors=donors)

@app.route('/analytics')
def analytics():
    conn = get_db()
    stats = {
        'total_food': conn.execute("SELECT COUNT(*) FROM food").fetchone()[0],
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'completed': conn.execute("SELECT COUNT(*) FROM food WHERE status='completed'").fetchone()[0],
        'available': conn.execute("SELECT COUNT(*) FROM food WHERE status='available'").fetchone()[0],
        'total_claims': conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
        'total_ratings': conn.execute("SELECT COUNT(*) FROM ratings").fetchone()[0],
    }
    categories = [dict(row) for row in conn.execute(
        '''SELECT category, COUNT(*) as count FROM food
           WHERE category IS NOT NULL
           GROUP BY category ORDER BY count DESC'''
    ).fetchall()]
    recent_foods = conn.execute(
        '''SELECT f.*, u.name as donor_name FROM food f
           JOIN users u ON f.donor_id = u.id
           ORDER BY f.created_at DESC LIMIT 10'''
    ).fetchall()
    conn.close()
    return render_template('analytics.html', stats=stats,
                           categories=categories, recent_foods=recent_foods)

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
            flash('Something went wrong.', 'danger')
    return render_template('forgot_password.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)