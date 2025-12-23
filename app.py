from flask import (
    Flask, render_template, request, redirect,
    url_for, send_from_directory, flash, jsonify
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    login_user, logout_user,
    current_user, login_required
)
from datetime import datetime
import os

from config import Config
from extensions import db, migrate, login_manager
from models.user import User
from models.photo import Photo

# ---------------- APP ----------------
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# ---------------- DATABASE ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# URL Temizliği ve v3 Sürücüsü Zorlaması
if "?" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 🔥 EN KRİTİK NOKTA: SSL Sertifika Kontrolünü Devre Dışı Bırakma
# Bu ayar Render'daki o inatçı SSL hatasını geçmemizi sağlar.
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "sslmode": "no-verify", # Sertifika doğrulamayı atla (Render hataları için)
    },
    "pool_pre_ping": True,
    "pool_recycle": 30,
    "pool_timeout": 60,
}

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Tabloları Otomatik Oluştur
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Tablo oluşturma hatası: {e}")

# ---------------- ROUTES ----------------

@app.route("/")
def index():
    try:
        photos = Photo.query.order_by(Photo.id.desc()).all()
        return render_template("index.html", photos=photos)
    except Exception as e:
        # Hata devam ederse hatayı ekranda açıkça görelim
        return f"Bağlantı Kurulamadı. Detay: {str(e)}", 500

@app.route("/login", methods=["POST"])
def login():
    username_or_email = request.form.get("username")
    password = request.form.get("password")
    user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({"status": "success", "redirect": url_for("profile", username=user.username)})
    return jsonify({"status": "error", "message": "Hatalı giriş"}), 401

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("Kullanıcı zaten mevcut", "error")
        return redirect(url_for("index"))
    
    user = User(username=username, email=email, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return redirect(url_for("profile", username=user.username))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()
    photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "",
        "followers": "0", "following": "0", "posts": len(photos), "is_vip": False
    }
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id))

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("photo")
    if file:
        filename = f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        photo = Photo(title="Post", filename=filename, owner_id=current_user.id)
        db.session.add(photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)












