from flask import Flask, render_template, request, redirect, url_for, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
import sqlite3
import os
import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'app.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_professional INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            message TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


class User(UserMixin):
    def __init__(self, id, username, email, password, is_professional=0):
        self.id = str(id)
        self.username = username
        self.email = email
        self.password = password
        self.is_professional = bool(is_professional)

    @staticmethod
    def get(user_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['password'], row['is_professional'])
        return None


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def home():
    # Sample gallery images (using picsum placeholders). Each item has a title and description.
    images = [
        {
            'url': f'https://picsum.photos/seed/{i}/1200/800',
            'thumb': f'https://picsum.photos/seed/{i}/600/400',
            'title': f'Çalışma #{i}',
            'desc': 'Sanat eseri açıklaması veya fotoğraf notu.'
        }
        for i in range(1, 13)
    ]
    current_year = datetime.date.today().year
    return render_template('index.html', images=images, current_year=current_year)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        # Basic validation
        if not name or not email or not message:
            flash('Lütfen tüm alanları doldurun.', 'error')
            return redirect(url_for('contact'))

        try:
            conn = get_db()
            conn.execute('INSERT INTO contacts (name,email,message,created_at) VALUES (?,?,?,?)',
                         (name, email, message, datetime.datetime.utcnow().isoformat()))
            conn.commit()
            flash('Teşekkürler! Mesajınız alındı.', 'success')
        except Exception as e:
            print('Error saving contact:', e)
            flash('Mesajınız kaydedilirken bir hata oldu. Lütfen tekrar deneyin.', 'error')

        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_prof = 1 if request.form.get('is_professional') == 'on' else 0

        if not username or not email or not password:
            flash('Lütfen tüm alanları doldurun.', 'error')
            return redirect(url_for('register'))

        pw_hash = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username,email,password,is_professional) VALUES (?,?,?,?)',
                         (username, email, pw_hash, is_prof))
            conn.commit()
            flash('Kayıt başarılı. Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Bu kullanıcı adı veya e-posta zaten kullanılıyor.', 'error')
            return redirect(url_for('register'))
        except Exception as e:
            print('Register error:', e)
            flash('Kayıt sırasında hata oluştu.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE username=? OR email=?', (username, username)).fetchone()
        if row and check_password_hash(row['password'], password):
            user = User(row['id'], row['username'], row['email'], row['password'], row['is_professional'])
            login_user(user)
            flash('Başarıyla giriş yapıldı.', 'success')
            next_page = request.args.get('next') or url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Kullanıcı adı/e-posta veya parola hatalı.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı.', 'success')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Only professionals see extra tools (simple example)
    return render_template('dashboard.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)