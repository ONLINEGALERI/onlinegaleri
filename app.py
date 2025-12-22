from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User
from models.siteinfo import SiteInfo
from models.photo import Photo

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "gizli-key"

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Upload folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(THUMB_FOLDER, exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------- INDEX ---------------------
@app.route('/')
def index():
    return render_template('index.html')

# --------------------- AUTH ---------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        if not user or not check_password_hash(user.password, password):
            flash("Giriş bilgileri hatalı.", "danger")
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login_clean.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Kullanıcı zaten mevcut!", "danger")
            return redirect(url_for('register'))
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')

# --------------------- PROFILE ---------------------
@app.route('/profile')
def profile():
    username = request.args.get('username')
    if username:
        server_profile = User.query.filter_by(username=username).first()
    elif current_user.is_authenticated:
        server_profile = current_user
        username = current_user.username
    else:
        return redirect(url_for('login'))

    if not server_profile:
        abort(404)

    is_vip = (server_profile.username.lower() == 'bec')
    
    sp = {
        'username': server_profile.username,
        'avatar': server_profile.avatar if server_profile.avatar else 'https://picsum.photos/seed/default/400/400',
        'bio': server_profile.bio if server_profile.bio else 'Henüz bir biyografi eklenmedi.',
        'followers': '2M' if is_vip else (server_profile.followers or 0),
        'following': '3' if is_vip else (server_profile.following or 0),
        'posts': '6' if is_vip else (server_profile.posts or 0),
        'is_vip': is_vip
    }

    can_edit = current_user.is_authenticated and current_user.id == server_profile.id
    return render_template('profile.html', server_profile=sp, can_edit=can_edit)

@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    data = request.get_json()
    if data:
        if 'bio' in data: current_user.bio = data.get('bio')
        if 'avatar' in data: current_user.avatar = data.get('avatar')
        db.session.commit()
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'}), 400

# --------------------- ADMIN ---------------------
@app.route('/admin')
@login_required
def admin():
    # Sadece bec admin paneline girebilir
    if current_user.username.lower() != 'bec':
        abort(403)
    return render_template('admin.html', users=User.query.all(), photos=Photo.query.all())

# KULLANICI SİLME (Hata Çözümü)
@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.username.lower() != 'bec':
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash(f"{user.username} silindi.", "success")
    return redirect(url_for('admin'))

# FOTOĞRAF SİLME (Hata Çözümü)
@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    if current_user.username.lower() != 'bec':
        abort(403)
    photo = Photo.query.get_or_404(photo_id)
    db.session.delete(photo)
    db.session.commit()
    flash("Fotoğraf silindi.", "success")
    return redirect(url_for('admin'))

# --------------------- GALLERY & UPLOAD ---------------------
@app.route('/gallery')
def gallery():
    images = os.listdir(THUMB_FOLDER) if os.path.exists(THUMB_FOLDER) else []
    return render_template('gallery.html', images=images)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('photo')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            img = Image.open(path)
            img.thumbnail((300, 300))
            img.save(os.path.join(THUMB_FOLDER, filename))
            photo = Photo(title=request.form.get('title'), filename=filename, owner_id=current_user.id)
            db.session.add(photo)
            db.session.commit()
            return redirect(url_for('gallery'))
    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename): return send_from_directory(THUMB_FOLDER, filename)

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(debug=True, port=5001)











