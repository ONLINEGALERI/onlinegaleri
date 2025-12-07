from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User


app = Flask(__name__)
app.config.from_object(Config)

# initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Basic upload folders and allowed extensions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(THUMB_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = None
        if username:
            # allow login by username or email
            user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Başarıyla giriş yapıldı', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Geçersiz kullanıcı adı veya şifre', 'danger')
    return render_template('login_clean.html')


@app.route('/register')
def register():
    if request.method == 'POST' or request.method == 'GET':
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            p1 = request.form.get('password1')
            p2 = request.form.get('password2')
            if not username or not email or not p1:
                flash('Tüm alanlar gerekli', 'danger')
                return redirect(url_for('register'))
            if p1 != p2:
                flash('Şifreler eşleşmiyor', 'danger')
                return redirect(url_for('register'))
            if User.query.filter((User.username == username) | (User.email == email)).first():
                flash('Kullanıcı adı veya email zaten kayıtlı', 'warning')
                return redirect(url_for('register'))
            u = User(username=username, email=email)
            u.set_password(p1)
            db.session.add(u)
            db.session.commit()
            flash('Kayıt başarılı. Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        # GET
        return render_template('register.html')


@app.route('/profile')
def profile():
    # Allow optional username via query string: /profile?username=cemre
    username = request.args.get('username')
    server_profile = None
    if username:
        server_profile = User.query.filter_by(username=username).first()
    else:
        if current_user.is_authenticated:
            server_profile = current_user
            username = current_user.username
    # pass a simple dict to template if server_profile exists
    sp = None
    if server_profile:
        sp = {
            'username': server_profile.username,
            'avatar': server_profile.avatar,
            'name': server_profile.username,
            'handle': f"@{server_profile.username}",
            'bio': server_profile.bio,
            'followers': server_profile.followers,
            'following': server_profile.following,
            'posts': server_profile.posts
        }
    can_edit = False
    try:
        can_edit = current_user.is_authenticated and current_user.username == username
    except Exception:
        can_edit = False
    return render_template('profile.html', username=username, server_profile=sp, can_edit=can_edit)


@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    # Accept form POST from edit modal
    data = request.form or request.get_json() or {}
    avatar = data.get('avatar')
    name = data.get('name')
    handle = data.get('handle')
    bio = data.get('bio')
    followers = data.get('followers')
    following = data.get('following')
    posts = data.get('posts')

    u = current_user
    if avatar: u.avatar = avatar
    if bio is not None: u.bio = bio
    try:
        u.followers = int(followers) if followers else u.followers
        u.following = int(following) if following else u.following
        u.posts = int(posts) if posts else u.posts
    except Exception:
        pass
    db.session.commit()
    return jsonify({'status':'ok'})


@app.route('/gallery')
def gallery():
    try:
        images = [f for f in os.listdir(THUMB_FOLDER) if os.path.isfile(os.path.join(THUMB_FOLDER, f))]
    except Exception:
        images = []
    return render_template('gallery.html', images=images)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'photo' not in request.files:
            flash('Dosya bulunamadı', 'warning')
            return redirect(request.url)
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(filepath)
            try:
                img = Image.open(filepath)
                img.thumbnail((200, 200))
                img.save(os.path.join(THUMB_FOLDER, filename))
            except Exception:
                pass
            return redirect(url_for('gallery'))
        flash('Geçersiz dosya türü', 'danger')
    return render_template('upload.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        print(f"Yeni mesaj: {name} - {email} - {message}")
        flash('Mesajınız alındı', 'success')
        return redirect(url_for('index'))
    return render_template('contact.html')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(THUMB_FOLDER, filename)


if __name__ == '__main__':
    # For development: ensure database tables exist then run
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
    app.run(debug=True, host='127.0.0.1', port=5000)

