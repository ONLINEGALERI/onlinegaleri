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

# 1. Veritabanı ve Klasör Yolları
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 2. Uzantıları Başlat
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# 🚀 3. RENDER İÇİN KRİTİK: Otomatik Tablo Oluşturma
with app.app_context():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db.create_all()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------- ROTALAR ---------------------

@app.route('/')
def index():
    try:
        all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
    except:
        all_photos = []
    return render_template('index.html', photos=all_photos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile', username=current_user.username))

    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = User.query.filter((User.username == u) | (User.email == u)).first()
        
        if user and check_password_hash(user.password, p):
            login_user(user)
            return redirect(url_for('profile', username=user.username))
        
        flash('Kullanıcı adı veya şifre hatalı.', 'error')
        return redirect(url_for('login'))
    
    return render_template('login_clean.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile', username=current_user.username))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Kullanıcı zaten mevcut!', 'error')
            return redirect(url_for('register'))
            
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('profile', username=new_user.username))
        
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

# ✨ SİLME FONKSİYONU: Profile.html'deki silme butonu için gerekli
@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo_profile(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.owner_id == current_user.id:
        db.session.delete(photo)
        db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

# ✨ TAKİP FONKSİYONLARI: JS fetch istekleri için gerekli
@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.follow(user)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.unfollow(user)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/get_followers/<username>')
def get_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    return jsonify([{"username": f.username, "avatar": f.avatar} for f in user.followers_list.all()])

@app.route('/get_following/<username>')
def get_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    return jsonify([{"username": f.username, "avatar": f.avatar} for f in user.followed.all()])

@app.route('/search')
def search():
    q = request.args.get('query', '')
    users = User.query.filter(User.username.ilike(f'%{q}%')).all() if q else []
    return render_template('search.html', users=users, query=q)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
