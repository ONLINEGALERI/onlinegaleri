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

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Klasör Yapılandırması - GÜVENLİ HALE GETİRİLDİ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')

# Klasörlerin varlığından emin oluyoruz
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------- INDEX ---------------------
@app.route('/')
def index():
    all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
    return render_template('index.html', photos=all_photos)

# --------------------- AUTH ---------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({'status': 'error', 'message': 'Kullanıcı adı veya şifre hatalı.'}), 401
        
        login_user(user)
        return jsonify({'status': 'success', 'redirect': url_for('index')})
        
    return render_template('login_clean.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ✨ ÜYELİK SONRASI JSON EKRANI SORUNU BURADA ÇÖZÜLDÜ ✨
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            return jsonify({'status': 'error', 'message': 'Kullanıcı zaten mevcut!'}), 400
            
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        # Eğer modal/AJAX üzerinden kayıt olunuyorsa JSON döner
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'redirect': url_for('index')})
        
        # Siyah ekranı engelleyen asıl yönlendirme:
        return redirect(url_for('index'))
        
    return render_template('register.html')

# --------------------- PROFILE & LİSTELEME (Bozulmadı) ---------------------
@app.route('/profile')
def profile():
    username = request.args.get('username')
    user_to_show = None
    
    if username:
        user_to_show = User.query.filter_by(username=username).first()
    elif current_user.is_authenticated:
        user_to_show = current_user
        username = current_user.username
    else:
        return redirect(url_for('login'))

    if not user_to_show:
        abort(404)

    user_photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    is_vip = user_to_show.username.lower() in ['bec', 'beril']
    is_following = False
    if current_user.is_authenticated and current_user.id != user_to_show.id:
        is_following = current_user.is_following(user_to_show)

    sp = {
        'username': user_to_show.username,
        'avatar': user_to_show.avatar or 'https://picsum.photos/seed/default/400/400',
        'bio': user_to_show.bio or 'Henüz bir biyografi eklenmedi.',
        'followers': '2M' if is_vip else user_to_show.followers_list.count(),
        'following': user_to_show.followed.count(),
        'posts': len(user_photos),
        'is_vip': is_vip
    }

    can_edit = current_user.is_authenticated and current_user.id == user_to_show.id
    return render_template('profile.html', server_profile=sp, can_edit=can_edit, photos=user_photos, is_following=is_following)

@app.route('/get_followers/<username>')
def get_followers(username):
    if username.lower() == 'bec':
        return jsonify([])
    user = User.query.filter_by(username=username).first_or_404()
    return jsonify([{"username": f.username, "avatar": f.avatar or 'https://picsum.photos/seed/default/100/100'} for f in user.followers_list.all()])

@app.route('/get_following/<username>')
def get_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following = []
    for f in user.followed.all():
        following.append({
            "username": f.username, 
            "avatar": f.avatar or 'https://picsum.photos/seed/default/100/100'
        })
    return jsonify(following)

# --------------------- DİĞER FONKSİYONLAR (Aynı Kaldı) ---------------------
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        original_filename = secure_filename(file.filename)
        filename = f"{current_user.id}_{timestamp}_{original_filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        try:
            img = Image.open(path)
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            img.thumbnail((400, 400))
            img.save(os.path.join(THUMB_FOLDER, filename))
        except: pass
        new_photo = Photo(title=request.form.get('title', 'Verzia Post'), filename=filename, owner_id=current_user.id)
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.username.lower() != 'bec': abort(403)
    users = User.query.all()
    photos = Photo.query.all()
    return render_template('admin.html', users=users, photos=photos)

@app.route('/delete_photo_admin/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo_admin_route(photo_id):
    if current_user.username.lower() != 'bec': abort(403)
    photo = Photo.query.get_or_404(photo_id)
    db.session.delete(photo)
    db.session.commit()
    return redirect(url_for('admin_panel'))

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
