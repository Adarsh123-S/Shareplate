from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import cloudinary
import cloudinary.uploader
from datetime import datetime
import psycopg2
import psycopg2.extras
from flask_dance.contrib.google import make_google_blueprint, google

app = Flask(__name__)
app.secret_key = 'shareplate-secret-key-2024'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

DATABASE_URL = os.environ.get('DATABASE_URL')

# Google OAuth
google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    scope=['profile', 'email']
)
app.register_blueprint(google_bp, url_prefix='/google')

# ── TEMPORARY DEBUG ROUTE — remove after checking env vars ──
@app.route('/debug-env')
def debug_env():
    cid = os.environ.get('GOOGLE_CLIENT_ID', '')
    secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    return {
        'client_id_length': len(cid),
        'client_id_starts_with': cid[:10],
        'client_id_ends_with': cid[-10:],
        'secret_length': len(secret),
        'secret_starts_with': secret[:6],
        'secret_ends_with': secret[-4:],
    }
# ── END DEBUG ROUTE ──

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        location TEXT,
        role TEXT DEFAULT 'both',
        bio TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        security_answer TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS food (
        id SERIAL PRIMARY KEY,
        food_name TEXT NOT NULL,
        category TEXT,
        quantity TEXT NOT NULL,
        location TEXT NOT NULL,
        expiry TEXT NOT NULL,
        contact TEXT,
        notes TEXT,
        status TEXT DEFAULT 'available',
        donor_id INTEGER REFERENCES users(id),
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        id SERIAL PRIMARY KEY,
        food_id INTEGER REFERENCES food(id),
        receiver_id INTEGER REFERENCES users(id),
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        food_id INTEGER REFERENCES food(id),
        user_id INTEGER REFERENCES users(id),
        rating INTEGER,
        review TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        food_id INTEGER REFERENCES food(id),
        sender_id INTEGER REFERENCES users(id),
        receiver_id INTEGER REFERENCES users(id),
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_notification(user_id, message):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO notifications (user_id, message) VALUES (%s,%s)', (user_id, message))
        conn.commit()
        conn.close()
    except: pass

def fetchall(cursor):
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def fetchone(cursor):
    cols = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None

@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT f.*, u.name as donor_name,
               COALESCE(AVG(r.rating), 0) as avg_rating,
               COUNT(r.id) as rating_count
               FROM food f JOIN users u ON f.donor_id = u.id
               LEFT JOIN ratings r ON f.id = r.food_id
               WHERE f.status = 'available'
               GROUP BY f.id, u.name
               ORDER BY f.created_at DESC LIMIT 6''')
    foods = fetchall(c)
    c.execute("SELECT COUNT(*) FROM food")
    total_food = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE status='completed'")
    completed = c.fetchone()[0]
    stats = {'total_food': total_food, 'total_users': total_users, 'completed': completed}
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
            c = conn.cursor()
            c.execute(
                'INSERT INTO users (name, email, password, location, role, security_answer) VALUES (%s,%s,%s,%s,%s,%s)',
                (name, email, hashed, location, role, security_answer)
            )
            conn.commit()
            conn.close()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Email already registered.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email=%s', (email,))
        user = fetchone(c)
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/google/login')
def google_login():
    return redirect(url_for('google.login'))

@app.route('/google/callback')
def google_callback():
    if not google.authorized:
        flash('Google login failed.', 'danger')
        return redirect(url_for('login'))
    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Failed to get user info from Google.', 'danger')
            return redirect(url_for('login'))
        info = resp.json()
        email = info['email']
        name = info.get('name', email)
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email=%s', (email,))
        user = fetchone(c)
        if not user:
            c.execute(
                'INSERT INTO users (name, email, password, location, role, security_answer) VALUES (%s,%s,%s,%s,%s,%s)',
                (name, email, generate_password_hash('google_oauth_user'), '', 'both', '')
            )
            conn.commit()
            c.execute('SELECT * FROM users WHERE email=%s', (email,))
            user = fetchone(c)
        conn.close()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        flash(f'Welcome, {user["name"]}! 🎉', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash('Google login failed. Please try again.', 'danger')
        return redirect(url_for('login'))

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
    c = conn.cursor()
    c.execute('SELECT * FROM food WHERE donor_id=%s ORDER BY created_at DESC', (uid,))
    my_donations = fetchall(c)
    c.execute('''SELECT r.*, f.food_name, f.location, f.expiry, u.name as donor_name
               FROM requests r
               JOIN food f ON r.food_id = f.id
               JOIN users u ON f.donor_id = u.id
               WHERE r.receiver_id=%s ORDER BY r.created_at DESC''', (uid,))
    my_claims = fetchall(c)
    c.execute('SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 10', (uid,))
    notifications = fetchall(c)
    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=0', (uid,))
    unread_count = c.fetchone()[0]
    conn.close()
    return render_template('dashboard.html', my_donations=my_donations,
                           my_claims=my_claims, notifications=notifications,
                           unread_count=unread_count)

@app.route('/mark-notifications-read')
def mark_notifications_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE notifications SET is_read=1 WHERE user_id=%s', (session['user_id'],))
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
        c = conn.cursor()
        c.execute(
            '''INSERT INTO food (food_name, category, quantity, location, expiry, contact, notes, donor_id, image_url)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
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
    c = conn.cursor()
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
               WHERE f.status = 'available' '''
    params = []
    if category:
        query += ' AND f.category=%s'
        params.append(category)
    if search:
        query += ' AND (f.food_name ILIKE %s OR f.notes ILIKE %s OR f.location ILIKE %s)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if location:
        query += ' AND f.location ILIKE %s'
        params.append(f'%{location}%')
    query += ' GROUP BY f.id, u.name'
    if min_rating:
        query += f' HAVING COALESCE(AVG(r.rating), 0) >= {min_rating}'
    if sort == 'rating':
        query += ' ORDER BY avg_rating DESC'
    elif sort == 'expiry':
        query += ' ORDER BY f.expiry ASC'
    else:
        query += ' ORDER BY f.created_at DESC'
    c.execute(query, params)
    foods = fetchall(c)
    recommendations = []
    if session.get('user_id'):
        c.execute('''SELECT f.*, u.name as donor_name,
                   COALESCE(AVG(r.rating), 0) as avg_rating
                   FROM food f JOIN users u ON f.donor_id = u.id
                   LEFT JOIN ratings r ON f.id = r.food_id
                   WHERE f.status = 'available' AND f.donor_id != %s
                   GROUP BY f.id, u.name
                   ORDER BY avg_rating DESC, f.created_at DESC LIMIT 3''',
                  (session['user_id'],))
        recommendations = fetchall(c)
    conn.close()
    return render_template('available.html', foods=foods, category=category,
                           search=search, location=location,
                           min_rating=min_rating, sort=sort,
                           recommendations=recommendations)

@app.route('/food/<int:food_id>')
def food_detail(food_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT f.*, u.name as donor_name, u.email as donor_email, u.phone as donor_phone
               FROM food f JOIN users u ON f.donor_id = u.id
               WHERE f.id=%s''', (food_id,))
    food = fetchone(c)
    if not food:
        flash('Food not found.', 'danger')
        conn.close()
        return redirect(url_for('available'))
    c.execute('''SELECT r.*, u.name as reviewer_name
               FROM ratings r JOIN users u ON r.user_id = u.id
               WHERE r.food_id=%s ORDER BY r.created_at DESC''', (food_id,))
    reviews = fetchall(c)
    c.execute('SELECT COALESCE(AVG(rating), 0) FROM ratings WHERE food_id=%s', (food_id,))
    avg_rating = c.fetchone()[0]
    c.execute('''SELECT m.*, u.name as sender_name
               FROM messages m JOIN users u ON m.sender_id = u.id
               WHERE m.food_id=%s ORDER BY m.created_at ASC''', (food_id,))
    messages = fetchall(c)
    conn.close()
    return render_template('food_detail.html', food=food, reviews=reviews,
                           avg_rating=avg_rating, messages=messages,
                           google_maps_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''))

@app.route('/rate/<int:food_id>', methods=['POST'])
def rate_food(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    rating = request.form.get('rating', 5)
    review = request.form.get('review', '')
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM ratings WHERE food_id=%s AND user_id=%s', (food_id, uid))
    existing = c.fetchone()
    if existing:
        c.execute('UPDATE ratings SET rating=%s, review=%s WHERE food_id=%s AND user_id=%s',
                  (rating, review, food_id, uid))
    else:
        c.execute('INSERT INTO ratings (food_id, user_id, rating, review) VALUES (%s,%s,%s,%s)',
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
    c = conn.cursor()
    c.execute('SELECT * FROM food WHERE id=%s', (food_id,))
    food = fetchone(c)
    if food:
        receiver_id = food['donor_id'] if uid != food['donor_id'] else None
        if receiver_id:
            c.execute('INSERT INTO messages (food_id, sender_id, receiver_id, message) VALUES (%s,%s,%s,%s)',
                      (food_id, uid, receiver_id, message))
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
    c = conn.cursor()
    c.execute('SELECT * FROM food WHERE id=%s', (food_id,))
    food = fetchone(c)
    if not food or food['status'] != 'available':
        flash('This food is no longer available.', 'warning')
        conn.close()
        return redirect(url_for('available'))
    if food['donor_id'] == uid:
        flash("You can't claim your own donation.", 'warning')
        conn.close()
        return redirect(url_for('available'))
    c.execute('SELECT * FROM requests WHERE food_id=%s AND receiver_id=%s', (food_id, uid))
    if c.fetchone():
        flash('You already claimed this food.', 'info')
        conn.close()
        return redirect(url_for('available'))
    c.execute('INSERT INTO requests (food_id, receiver_id) VALUES (%s,%s)', (food_id, uid))
    c.execute("UPDATE food SET status='requested' WHERE id=%s", (food_id,))
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
    c = conn.cursor()
    c.execute('SELECT * FROM food WHERE id=%s AND donor_id=%s', (food_id, session['user_id']))
    if not c.fetchone():
        flash('Not authorized.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    c.execute('UPDATE food SET status=%s WHERE id=%s', (status, food_id))
    conn.commit()
    conn.close()
    flash(f'Status updated to {status}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-food/<int:food_id>', methods=['POST'])
def delete_food(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM requests WHERE food_id=%s', (food_id,))
    c.execute('DELETE FROM food WHERE id=%s AND donor_id=%s', (food_id, session['user_id']))
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
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        bio = request.form.get('bio', '')
        phone = request.form.get('phone', '')
        c.execute('UPDATE users SET name=%s, location=%s, bio=%s, phone=%s WHERE id=%s',
                  (name, location, bio, phone, uid))
        conn.commit()
        session['user_name'] = name
        flash('Profile updated! ✅', 'success')
    c.execute('SELECT * FROM users WHERE id=%s', (uid,))
    user = fetchone(c)
    c.execute('SELECT COUNT(*) FROM food WHERE donor_id=%s', (uid,))
    total_donations = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM requests WHERE receiver_id=%s', (uid,))
    total_claims = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE donor_id=%s AND status='completed'", (uid,))
    completed = c.fetchone()[0]
    conn.close()
    return render_template('profile.html', user=user,
                           total_donations=total_donations,
                           total_claims=total_claims,
                           completed=completed)

@app.route('/leaderboard')
def leaderboard():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT u.name, u.location,
               COUNT(f.id) as total,
               SUM(CASE WHEN f.status='completed' THEN 1 ELSE 0 END) as completed
               FROM users u
               LEFT JOIN food f ON u.id = f.donor_id
               GROUP BY u.id, u.name, u.location
               ORDER BY total DESC LIMIT 20''')
    donors = fetchall(c)
    conn.close()
    return render_template('leaderboard.html', donors=donors)

@app.route('/analytics')
def analytics():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM food"); total_food = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE status='completed'"); completed = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE status='available'"); available = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM requests"); total_claims = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ratings"); total_ratings = c.fetchone()[0]
    stats = {'total_food': total_food, 'total_users': total_users,
             'completed': completed, 'available': available,
             'total_claims': total_claims, 'total_ratings': total_ratings}
    c.execute('''SELECT category, COUNT(*) as count FROM food
               WHERE category IS NOT NULL
               GROUP BY category ORDER BY count DESC''')
    categories = [{'category': row[0], 'count': row[1]} for row in c.fetchall()]
    c.execute('''SELECT f.*, u.name as donor_name FROM food f
               JOIN users u ON f.donor_id = u.id
               ORDER BY f.created_at DESC LIMIT 10''')
    recent_foods = fetchall(c)
    conn.close()
    return render_template('analytics.html', stats=stats,
                           categories=categories, recent_foods=recent_foods)

ADMIN_EMAIL = 'admin@shareplate.com'

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id=%s', (session['user_id'],))
    user = fetchone(c)
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    c.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = fetchall(c)
    c.execute('''SELECT f.*, u.name as donor_name FROM food f
               JOIN users u ON f.donor_id=u.id ORDER BY f.created_at DESC''')
    foods = fetchall(c)
    c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food"); total_food = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE status='available'"); avail = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM food WHERE status='completed'"); comp = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM requests"); total_claims = c.fetchone()[0]
    stats = {'total_users': total_users, 'total_food': total_food,
             'available': avail, 'completed': comp, 'total_claims': total_claims}
    conn.close()
    return render_template('admin.html', users=users, foods=foods, stats=stats)

@app.route('/admin/delete-user/<int:uid>', methods=['POST'])
def admin_delete_user(uid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id=%s', (session['user_id'],))
    user = fetchone(c)
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    c.execute('DELETE FROM requests WHERE receiver_id=%s', (uid,))
    c.execute('DELETE FROM food WHERE donor_id=%s', (uid,))
    c.execute('DELETE FROM users WHERE id=%s', (uid,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/delete-food/<int:fid>', methods=['POST'])
def admin_delete_food(fid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id=%s', (session['user_id'],))
    user = fetchone(c)
    if user['email'] != ADMIN_EMAIL:
        flash('Access denied.', 'danger')
        conn.close()
        return redirect(url_for('index'))
    c.execute('DELETE FROM requests WHERE food_id=%s', (fid,))
    c.execute('DELETE FROM food WHERE id=%s', (fid,))
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
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email=%s', (email,))
            user = fetchone(c)
            if user:
                stored_answer = (user['security_answer'] or '').strip().lower()
                if stored_answer == security_answer:
                    hashed = generate_password_hash(new_password)
                    c.execute('UPDATE users SET password=%s WHERE email=%s', (hashed, email))
                    conn.commit()
                    conn.close()
                    flash('Password reset successful! Please login.', 'success')
                    return redirect(url_for('login'))
                conn.close()
                flash('Security answer is incorrect.', 'danger')
            else:
                conn.close()
                flash('Email not found.', 'danger')
        except Exception as e:
            flash('Something went wrong.', 'danger')
    return render_template('forgot_password.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)