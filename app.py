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

# ---------------- DATABASE (RENDER + PSYCOPG v3 + SSL) ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# 🔥 psycopg v3 ve PostgreSQL uyumu
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Render SSL zorunluluğu için URL parametresi
if "sslmode" not in DATABASE_URL:
    if "?" in DATABASE_URL:
        DATABASE_URL += "&sslmode=require"
    else:
        DATABASE_URL += "?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 🔥 KRİTİK AYAR: SSL ve Bağlantı Kopmalarını Engelleyen Motor Ayarları
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "sslmode": "require",
    },
    "pool_pre_ping": True,  # Bağlantı koptuysa otomatik yeniden bağlanır
    "pool_recycle": 300,    # 5 dakikada bir bağlantıyı tazeler
}

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# ---------------- UPLOAD ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# ---------------- LOGIN MANAGER ----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    photos = Photo.query.order_by(Photo.id.desc()).all()
    return render_template("index.html", photos=photos)

# ---------- LOGIN (AJAX) ----------
@app.route("/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return jsonify({
            "status": "success",
            "redirect": url_for("profile", username=current_user.username)
        })

    username_or_email = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter(
        (User.username == username_or_email) |
        (User.email == username_or_email)
    ).first()

    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({
            "status": "success",
            "redirect": url_for("profile", username=user.username)
        })

    return jsonify({
        "status": "error",
        "message": "Kullanıcı adı veya şifre hatalı"
    }), 401

# ---------- REGISTER ----------
@app.route("/register", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("profile", username=current_user.username))

    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")

    if User.query.filter(
        (User.username == username) |
        (User.email == email)
    ).first():
        flash("Kullanıcı zaten mevcut", "error")
        return redirect(url_for("index"))

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    login_user(user)
    return redirect(url_for("profile", username=user.username))

# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# ---------- PROFILE ----------
@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()

    photos = Photo.query.filter_by(
        owner_id=user_to_show.id
    ).order_by(Photo.id.desc()).all()

    is_vip = user_to_show.username.lower() in ["bec", "beril"]

    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Henüz bir biyografi yok.",
        "followers": "2M" if is_vip else user_to_show.followers_list.count(),
        "following": user_to_show.followed.count(),
        "posts": len(photos),
        "is_vip": is_vip
    }

    return render_template(
        "profile.html",
        server_profile=profile_data,
        photos=photos,
        can_edit=(current_user.id == user_to_show.id)
    )

# ---------- UPLOAD ----------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("photo")

    if file and allowed_file(file.filename):
        filename = (
            f"{current_user.id}_"
            f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_"
            f"{secure_filename(file.filename)}"
        )

        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        photo = Photo(
            title="Verzia Post",
            filename=filename,
            owner_id=current_user.id
        )

        db.session.add(photo)
        db.session.commit()

    return redirect(url_for("profile", username=current_user.username))

# ---------- FILE SERVE ----------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- RUN (LOCAL ONLY) ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)













