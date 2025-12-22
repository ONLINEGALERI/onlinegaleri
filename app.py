from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User, Comment, Like 
from models.siteinfo import SiteInfo
from models.photo import Photo

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "gizli-key"

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Klasör Yapılandırması
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
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

# --------------------- AUTH (GÜNCELLENDİ) ---------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        
        if not user or not check_password_hash(user.password, password):
            # Burası değişti: Hata olduğunda JSON dönüyoruz
            return jsonify({'status': 'error', 'message': 'Kullanıcı adı veya şifre hatalı.'}), 401
        
        login_user(user)
        # Burası değişti: Başarılıysa JSON ile yönlendirme adresi dönüyoruz
        return jsonify({'status': 'success', 'redirect': url_for('index')})
        
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
            # Kayıt hatası için de JSON desteği (İsteğe bağlı)
            return jsonify({'status': 'error', 'message': 'Kullanıcı zaten mevcut!'}), 400
            
        new_user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return jsonify({'status': 'success', 'redirect': url_for('index')})
        
    return render_template('register.html')

# --------------------- PROFILE ---------------------
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
    is_vip = (user_to_show.username.lower() == 'bec')
    
    is_following = False
    if current_user.is_authenticated and current_user.id != user_to_show.id:
        is_following = current_user.is_following(user_to_show)

    sp = {
        'username': user_to_show.username,
        'avatar': user_to_show.avatar if user_to_show.avatar else 'https://picsum.photos/seed/default/400/400',
        'bio': user_to_show.bio if user_to_show.bio else 'Henüz bir biyografi eklenmedi.',
        'followers': '2M' if is_vip else user_to_show.followers_list.count(),
        'following': '3' if is_vip else user_to_show.followed.count(),
        'posts': len(user_photos),
        'is_vip': is_vip
    }

    can_edit = current_user.is_authenticated and current_user.id == user_to_show.id
    return render_template('profile.html', server_profile=sp, can_edit=can_edit, photos=user_photos, is_following=is_following)

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

# --------------------- SEARCH ---------------------
@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    results = []
    if query:
        results = User.query.filter(User.username.icontains(query)).all()
    return render_template('search.html', results=results, query=query)

# --------------------- SOSYAL AKSİYONLAR ---------------------
@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if not user or user == current_user:
        return jsonify({'status': 'error'}), 400
    current_user.follow(user)
    db.session.commit()
    return jsonify({'status': 'success', 'followers': user.followers_list.count()})

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'status': 'error'}), 404
    current_user.unfollow(user)
    db.session.commit()
    return jsonify({'status': 'success', 'followers': user.followers_list.count()})

# --------------------- TAKİP LİSTELERİ ---------------------
@app.route('/get_followers/<username>')
@login_required
def get_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers = [{"username": u.username, "avatar": u.avatar if u.avatar else 'https://picsum.photos/seed/default/100/100'} for u in user.followers_list]
    return jsonify(followers)

@app.route('/get_following/<username>')
@login_required
def get_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following = [{"username": u.username, "avatar": u.avatar if u.avatar else 'https://picsum.photos/seed/default/100/100'} for u in user.followed]
    return jsonify(following)

# --------------------- FOTOĞRAF YÜKLEME ---------------------
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{current_user.id}_{filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        
        try:
            img = Image.open(path)
            img.thumbnail((400, 400))
            img.save(os.path.join(THUMB_FOLDER, filename))
        except:
            pass
            
        new_photo = Photo(
            title=request.form.get('title', 'Verzia Post'),
            filename=filename,
            owner_id=current_user.id
        )
        db.session.add(new_photo)
        db.session.commit()
        
    return redirect(url_for('profile', username=current_user.username))

# --------------------- SİLME VE SERVİS ---------------------
@app.route('/delete_photo_profile/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo_profile(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.owner_id != current_user.id and current_user.username.lower() != 'bec':
        abort(403)
    db.session.delete(photo)
    db.session.commit()
    return redirect(url_for('profile', username=current_user.username))

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename): return send_from_directory(THUMB_FOLDER, filename)

if __name__ == "__main__":
    with app.app_context(): 
        db.create_all()
    app.run(debug=True, port=5001)