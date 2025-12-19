from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
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

# Upload folders & allowed extensions
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
        username = request.form.get('username')
        password = request.form.get('password')
        user = None
        if username:
            user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Başarıyla giriş yapıldı', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Geçersiz kullanıcı adı veya şifre', 'danger')
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

        # Aynı kullanıcı veya email varsa hata ver
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Bu kullanıcı adı veya email zaten kayıtlı!", "danger")
            return render_template('register.html')

        # Şifreyi hashle
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Yeni kullanıcı oluştur
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        # Kullanıcıyı otomatik login et
        login_user(new_user)

        # Başarılı kayıt → flash göster ve anasayfaya yönlendir
        flash("Kayıt başarılı! Anasayfaya yönlendiriliyorsunuz...", "success")
        return redirect(url_for('index'))

    return render_template('register.html')

# --------------------- PROFILE ---------------------
@app.route('/profile')
def profile():
    username = request.args.get('username')
    server_profile = None
    if username:
        server_profile = User.query.filter_by(username=username).first()
    else:
        if current_user.is_authenticated:
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
    avatar = data.get('avatar')
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

# --------------------- GALLERY & UPLOAD ---------------------
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
                img.thumbnail((300, 300))
                img.save(os.path.join(THUMB_FOLDER, filename))
            except Exception:
                pass
            if current_user.is_authenticated:
                p = Photo(
                    title=request.form.get('title', ''),
                    description=request.form.get('description', ''),
                    filename=filename,
                    owner_id=current_user.id
                )
                db.session.add(p)
                db.session.commit()
            return redirect(url_for('gallery'))
        flash('Geçersiz dosya türü', 'danger')
    return render_template('upload.html')

# --------------------- ABOUT & CONTACT ---------------------
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
    si = SiteInfo.query.first()
    site_info = si.to_dict() if si else None
    return render_template('contact.html', site_info=site_info)

# --------------------- ADMIN ---------------------
@app.route('/admin')
@login_required
def admin():
    users = User.query.all()
    photos = Photo.query.all()
    return render_template('admin.html', users=users, photos=photos)

# --------------------- UPLOAD SERVE ---------------------
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








