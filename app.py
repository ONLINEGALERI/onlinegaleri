from flask import (
    Flask, render_template, request, redirect,
    url_for, send_from_directory, flash, jsonify, abort
)
from werkzeug.utils import secure_filename
from flask_login import (
    login_user, logout_user, current_user, login_required
)
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from models.user import User
from models.siteinfo import SiteInfo
from models.post import Post


app = Flask(__name__)
app.config.from_object(Config)

# -------------------- EXTENSIONS --------------------
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------- UPLOAD CONFIG --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------- ROUTES --------------------

@app.route('/')
def index():
    return render_template('index.html')


# -------------------- AUTH --------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Giriş başarılı', 'success')
            return redirect(url_for('profile', username=user.username))

        flash('Hatalı kullanıcı adı veya şifre', 'danger')

    return render_template('login_clean.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı', 'info')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        p1 = request.form.get('password1')
        p2 = request.form.get('password2')

        if not username or not email or not p1:
            flash('Tüm alanlar zorunlu', 'danger')
            return redirect(url_for('register'))

        if p1 != p2:
            flash('Şifreler uyuşmuyor', 'danger')
            return redirect(url_for('register'))

        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            flash('Kullanıcı zaten kayıtlı', 'warning')
            return redirect(url_for('register'))

        u = User(username=username, email=email)
        u.set_password(p1)
        db.session.add(u)
        db.session.commit()

        flash('Kayıt başarılı', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# -------------------- PROFILE --------------------

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    posts = Post.query.filter_by(
        user_id=user.id, archived=False
    ).order_by(Post.created_at.desc()).all()

    return render_template(
        'profile.html',
        server_profile=user,
        posts=[p.to_dict(base_url=request.url_root) for p in posts],
        can_edit=current_user.is_authenticated and current_user.id == user.id
    )


# -------------------- POSTS --------------------

@app.route('/post/upload', methods=['POST'])
@login_required
def upload_post():
    file = request.files.get('photo')
    caption = request.form.get('caption')

    if not file or file.filename == '':
        flash('Dosya seçilmedi', 'danger')
        return redirect(request.referrer)

    if not allowed_file(file.filename):
        flash('Geçersiz dosya türü', 'danger')
        return redirect(request.referrer)

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        img = Image.open(filepath)
        img.thumbnail((600, 600))
        img.save(os.path.join(THUMB_FOLDER, filename))
    except Exception:
        pass

    post = Post(
        user_id=current_user.id,
        filename=filename,
        caption=caption
    )
    db.session.add(post)
    db.session.commit()

    flash('Fotoğraf yüklendi', 'success')
    return redirect(url_for('profile', username=current_user.username))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.user_id != current_user.id:
        abort(403)

    try:
        os.remove(os.path.join(UPLOAD_FOLDER, post.filename))
        os.remove(os.path.join(THUMB_FOLDER, post.filename))
    except Exception:
        pass

    db.session.delete(post)
    db.session.commit()

    flash('Gönderi silindi', 'success')
    return redirect(url_for('profile', username=current_user.username))


# -------------------- GALLERY --------------------

@app.route('/gallery')
def gallery():
    try:
        images = os.listdir(THUMB_FOLDER)
    except Exception:
        images = []
    return render_template('gallery.html', images=images)


@app.route('/about')
def about():
    return render_template('about.html')


# -------------------- CONTACT --------------------

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Mesajınız alındı', 'success')
        return redirect(url_for('index'))

    site_info = SiteInfo.query.first()
    return render_template('contact.html', site_info=site_info)


# -------------------- FILE SERVE --------------------

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(THUMB_FOLDER, filename)


# -------------------- RUN --------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
