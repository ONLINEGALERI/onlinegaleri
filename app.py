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

        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).first()

        if not user:
            flash("Kullanıcı adı yanlış.", "danger")
            return redirect(url_for('login'))

        if not check_password_hash(user.password, password):
            flash("Şifre yanlış.", "danger")
            return redirect(url_for('login'))

        login_user(user)
        flash("Giriş başarılı! Hoş geldin 🎉", "success")
        return redirect(request.args.get('next') or url_for('index'))

    return render_template('login_clean.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı', 'success')
    return redirect(url_for('index'))

# --------------------- REGISTER ---------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter(
            (User.username == username) |
            (User.email == email)
        ).first()

        if existing_user:
            flash("Bu kullanıcı adı veya email zaten kayıtlı!", "danger")
            return render_template('register.html')

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Kayıt başarılı! Hoş geldin 🎉", "success")
        return redirect(url_for('index'))

    return render_template('register.html')

# --------------------- PROFILE ---------------------
@app.route('/profile')
def profile():
    username = request.args.get('username')
    server_profile = None

    if username:
        server_profile = User.query.filter_by(username=username).first()
    elif current_user.is_authenticated:
        server_profile = current_user
        username = current_user.username

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

    can_edit = current_user.is_authenticated and current_user.username == username
    return render_template('profile.html', username=username, server_profile=sp, can_edit=can_edit)

@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    data = request.form or request.get_json() or {}
    current_user.avatar = data.get('avatar', current_user.avatar)
    current_user.bio = data.get('bio', current_user.bio)
    db.session.commit()
    return jsonify({'status': 'ok'})

# --------------------- GALLERY ---------------------
@app.route('/gallery')
def gallery():
    images = os.listdir(THUMB_FOLDER) if os.path.exists(THUMB_FOLDER) else []
    return render_template('gallery.html', images=images)

# --------------------- UPLOAD ---------------------
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('photo')

        if not file or not allowed_file(file.filename):
            flash('Geçersiz dosya', 'danger')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(path)

        img = Image.open(path)
        img.thumbnail((300, 300))
        img.save(os.path.join(THUMB_FOLDER, filename))

        photo = Photo(
            title=request.form.get('title'),
            filename=filename,
            owner_id=current_user.id
        )
        db.session.add(photo)
        db.session.commit()

        return redirect(url_for('gallery'))

    return render_template('upload.html')

# --------------------- ADMIN ---------------------
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)

    users = User.query.all()
    photos = Photo.query.all()
    return render_template('admin.html', users=users, photos=photos)

@app.route('/admin/delete-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Kendi hesabını silemezsin!", "danger")
        return redirect(url_for('admin'))

    db.session.delete(user)
    db.session.commit()
    flash("Kullanıcı silindi", "success")
    return redirect(url_for('admin'))

# --------------------- FILE SERVE ---------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(THUMB_FOLDER, filename)

# --------------------- RUN ---------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)











