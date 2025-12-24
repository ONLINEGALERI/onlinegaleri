from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash
from flask_login import login_user, logout_user, current_user, login_required
import os
import base64 
from werkzeug.utils import secure_filename

from extensions import db, migrate, login_manager
from models.user import User, Comment, Like, Notification 
from models.photo import Photo

app = Flask(__name__)
app.config.from_object('config.Config')
app.secret_key = os.environ.get("SECRET_KEY", "verzia-special-2025")

# UPLOAD AYARI
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static/uploads")
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

# DATABASE AYARI
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///verzia_local.db"

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --------------------- BİLDİRİM SİSTEMİ ---------------------
@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_count = current_user.notifications.filter_by(is_read=False).count()
        return dict(unread_notifications_count=unread_count)
    return dict(unread_notifications_count=0)

# --------------------- ANA SAYFA VE AUTH ---------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    user = User.query.filter((User.username == username) | (User.email == username)).first()
    if user and user.check_password(password):
        login_user(user, remember=True)
        return jsonify({"status": "success", "redirect": url_for("profile", username=user.username)})
    return jsonify({"status": "error", "message": "Bilgiler hatalı!"}), 401

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Bu kullanıcı adı zaten alınmış!"}), 400
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)
    return jsonify({"status": "success", "redirect": url_for("profile", username=new_user.username)})

# --------------------- PROFİL VE SOSYAL ---------------------
@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()
    photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    username_check = user_to_show.username.replace('İ', 'i').replace('I', 'ı').lower()
    kurucular = ["beril", "ecem", "cemre"]
    is_ana_profil = "verzia" in username_check
    is_kurucu = username_check in kurucular
    if is_ana_profil: followers_display = "2M"
    elif is_kurucu: followers_display = "1.5M"
    else: followers_display = user_to_show.followers_list.count()
    
    profile_data = {
        "id": user_to_show.id, "username": user_to_show.username, "avatar": user_to_show.avatar or "https://picsum.photos/400", 
        "bio": user_to_show.bio or "Verzia Experience", "followers": followers_display, "following": user_to_show.followed.count(), 
        "is_vip": is_kurucu or is_ana_profil, "is_kurucu": is_kurucu or is_ana_profil
    }
    is_following = current_user.is_following(user_to_show)
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id), is_following=is_following)

# --------------------- BİYOGRAFİ GÜNCELLEME (HATA ALAN KISIM) ---------------------
@app.route("/update_bio", methods=["POST"])
@login_required
def update_bio():
    new_bio = request.form.get("bio")
    user = db.session.get(User, current_user.id)
    if user:
        user.bio = new_bio
        db.session.commit()
    return redirect(url_for("profile", username=user.username))

# --------------------- RENDER ÖLÜMSÜZ UPLOAD (BASE64) ---------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if 'photo' not in request.files: return redirect(request.url)
    file = request.files['photo']
    if file and file.filename != '':
        img_data = base64.b64encode(file.read()).decode('utf-8')
        data_url = f"data:{file.mimetype};base64,{img_data}"
        new_photo = Photo(filename=data_url, owner_id=current_user.id, title="Verzia Photo")
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

# --------------------- FOTOĞRAF SİLME (YENİ EKLENDİ) ---------------------
@app.route("/delete_photo/<int:photo_id>", methods=["POST"])
@login_required
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.owner_id == current_user.id:
        db.session.delete(photo)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

# --------------------- AYARLAR ---------------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = db.session.get(User, current_user.id)
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        if not current_password or not user.check_password(current_password):
            flash("Mevcut şifren hatalı!", "error")
            return redirect(url_for("settings"))
        if new_username: user.username = new_username
        if new_password: user.set_password(new_password)
        db.session.commit()
        return redirect(url_for("profile", username=user.username))
    return render_template("settings.html", user=user)

# --------------------- ETKİLEŞİM VE LİSTELER ---------------------
@app.route('/get_post_details/<int:photo_id>')
@login_required
def get_post_details(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    is_liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first() is not None
    comments = [{"username": db.session.get(User, c.user_id).username, "text": c.body} for c in photo.comments]
    return jsonify({"likes": len(photo.likes), "is_liked": is_liked, "comments": comments})

@app.route('/like/<int:photo_id>', methods=['POST'])
@app.route('/like_post/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first()
    if existing_like:
        db.session.delete(existing_like)
        status = 'unliked'
    else:
        db.session.add(Like(user_id=current_user.id, photo_id=photo_id))
        status = 'liked'
    db.session.commit()
    return jsonify({'status': status, 'like_count': len(photo.likes)})

@app.route('/comment/<int:photo_id>', methods=['POST'])
@app.route('/add_comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    data = request.get_json()
    content = data.get('text')
    db.session.add(Comment(body=content, user_id=current_user.id, photo_id=photo_id))
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route("/get_user_list/<username>/<type>")
@login_required
def get_user_list(username, type):
    user = User.query.filter_by(username=username).first_or_404()
    ozel_uyeler = ["beril", "ecem", "cemre", "verzia"]
    username_lower = user.username.replace('İ', 'i').replace('I', 'ı').lower()
    if username_lower in ozel_uyeler and type == 'followers':
        return jsonify([])
    users = user.followers_list.all() if type == 'followers' else user.followed.all()
    return jsonify([{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users])

# --------------------- KULLANICI ARAMA (YENİ EKLENDİ) ---------------------
@app.route("/search_users")
@login_required
def search_users():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    users = User.query.filter(User.username.ilike(f"%{q}%")).limit(10).all()
    return jsonify([{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users])

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1", port=5000, debug=True)












