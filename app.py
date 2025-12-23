from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import os
from datetime import datetime

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User, Comment, Like, Notification
from models.siteinfo import SiteInfo
from models.photo import Photo

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "gizli-key"

# Veritabanı yapılandırmasını garantiye alalım
# Render'da SQLite dosyasının doğru yere yazılması için:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Klasör Yapılandırması
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')

# Render'da klasörlerin oluştuğundan emin ol
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------- ROTALAR (DEĞİŞMEDİ) ---------------------
@app.route('/')
def index():
    all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
    return render_template('index.html', photos=all_photos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = User.query.filter((User.username == u) | (User.email == u)).first()
        if user and check_password_hash(user.password, p):
            login_user(user)
            return jsonify({'status': 'success', 'redirect': url_for('index')})
        return jsonify({'status': 'error', 'message': 'Hatalı giriş!'}), 401
    return render_template('login_clean.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            return jsonify({'status': 'error', 'message': 'Kullanıcı mevcut!'}), 400
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return jsonify({'status': 'success', 'redirect': url_for('index')})
    return render_template('register.html')

@app.route('/profile')
def profile():
    username = request.args.get('username')
    user_to_show = User.query.filter_by(username=username).first() if username else current_user
    if not user_to_show or (not username and not current_user.is_authenticated):
        return redirect(url_for('login'))

    user_photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    is_vip = user_to_show.username.lower() in ['bec', 'beril']
    
    is_following = False
    if current_user.is_authenticated and current_user.id != user_to_show.id:
        try: is_following = current_user.is_following(user_to_show)
        except: is_following = False

    sp = {
        'username': user_to_show.username,
        'avatar': user_to_show.avatar or 'https://picsum.photos/seed/default/400/400',
        'bio': user_to_show.bio or 'Henüz bir biyografi eklenmedi.',
        'followers': '2M' if is_vip else user_to_show.followers_list.count(),
        'following': user_to_show.followed.count(),
        'posts': len(user_photos),
        'is_vip': is_vip
    }
    return render_template('profile.html', server_profile=sp, can_edit=(current_user==user_to_show), photos=user_photos, is_following=is_following)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        filename = f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_photo = Photo(title="Verzia Post", filename=filename, owner_id=current_user.id)
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

# 🔍 BuildError'ları önlemek için eksik rotalar
@app.route('/search')
def search():
    q = request.args.get('query', '')
    users = User.query.filter(User.username.ilike(f'%{q}%')).all() if q else []
    return render_template('search.html', users=users, query=q)

@app.route('/notifications/unread-count')
@login_required
def unread_notif_count():
    return jsonify({'count': 0})

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == "__main__":
    with app.app_context():
        # Veritabanını oluşturmadan önce mevcut olanı temizlemek gerekebilir 
        # ama SQLite kullanıyorsan create_all() yeterlidir.
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
