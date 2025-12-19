from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User
from models.siteinfo import SiteInfo
from models.photo import Photo  # Fotoğraf modeli

app = Flask(__name__)
app.config.from_object(Config)

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

# --------------------- INDEX & API ---------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/photos')
def api_photos():
    try:
        files = [f for f in os.listdir(THUMB_FOLDER) if os.path.isfile(os.path.join(THUMB_FOLDER, f))]
        if files:
            urls = [url_for('thumb_file', filename=f) for f in files]
        else:
            urls = [
                "https://picsum.photos/200/250?random=101",
                "https://picsum.photos/200/200?random=102",
                "https://picsum.photos/200/230?random=103",
                "https://picsum.photos/200/210?random=104",
                "https://picsum.photos/200/220?random=105",
                "https://picsum.photos/200/240?random=106"
            ]
    except Exception:
        urls = []
    return jsonify(urls)

# --------------------- AUTH ---------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = None
        if username:
            user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and user.check_password(password):
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

@app.route('/register', methods=['GET', 'POST'])
def register():
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
    # Sadece giriş yapmış kullanıcılar erişebilir
    users = User.query.all()
    photos = Photo.query.all()
    return render_template('admin.html', users=users, photos=photos)

# Kullanıcı CRUD
@app.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
def add_user_form():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash('Kullanıcı zaten var', 'warning')
            return redirect(url_for('add_user_form'))
        u = User(username=username, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('Kullanıcı eklendi', 'success')
        return redirect(url_for('admin'))
    return render_template('add_user.html')

@app.route('/admin/user/update/<int:user_id>', methods=['GET', 'POST'])
@login_required
def update_user_form(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        password = request.form.get('password')
        if password:
            user.set_password(password)
        db.session.commit()
        flash('Kullanıcı güncellendi', 'success')
        return redirect(url_for('admin'))
    return render_template('update_user.html', user=user)

@app.route('/admin/user/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Kullanıcı silindi', 'success')
    return redirect(url_for('admin'))

# Fotoğraf CRUD
@app.route('/admin/photo/add', methods=['GET', 'POST'])
@login_required
def add_photo_form():
    users = User.query.all()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        filename = request.form.get('filename')
        owner_id = request.form.get('user_id')
        p = Photo(title=title, description=description, filename=filename, owner_id=owner_id)
        db.session.add(p)
        db.session.commit()
        flash('Fotoğraf eklendi', 'success')
        return redirect(url_for('admin'))
    return render_template('add_photo.html', users=users)

@app.route('/admin/photo/update/<int:photo_id>', methods=['GET', 'POST'])
@login_required
def update_photo_form(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    users = User.query.all()
    if request.method == 'POST':
        photo.title = request.form.get('title')
        photo.description = request.form.get('description')
        photo.filename = request.form.get('filename')
        photo.owner_id = request.form.get('user_id')
        db.session.commit()
        flash('Fotoğraf güncellendi', 'success')
        return redirect(url_for('admin'))
    return render_template('update_photo.html', photo=photo, users=users)

@app.route('/admin/photo/delete/<int:photo_id>')
@login_required
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    db.session.delete(photo)
    db.session.commit()
    flash('Fotoğraf silindi', 'success')
    return redirect(url_for('admin'))

# --------------------- SITEINFO ---------------------
@app.route('/admin/siteinfo', methods=['GET', 'POST'])
@login_required
def edit_siteinfo():
    si = SiteInfo.query.first()
    if request.method == 'POST':
        email = request.form.get('contact_email')
        phone = request.form.get('contact_phone')
        addr = request.form.get('contact_address')
        extra = request.form.get('extra')
        if not si:
            si = SiteInfo(contact_email=email, contact_phone=phone, contact_address=addr, extra=extra)
            db.session.add(si)
        else:
            si.contact_email = email
            si.contact_phone = phone
            si.contact_address = addr
            si.extra = extra
        db.session.commit()
        flash('Site iletişim bilgileri güncellendi', 'success')
        return redirect(url_for('contact'))
    site_info = si.to_dict() if si else None
    return render_template('admin_siteinfo.html', site_info=site_info)

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
        try:
            db.create_all()
        except Exception:
            pass
    app.run(debug=True, port=5001)








