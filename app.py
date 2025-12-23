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

# ---------------- DATABASE (EXTERNAL URL UYUMLU) ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL bulunamadı!")

# Temizlik: URL sonundaki parametreleri temizle, kod kendisi ekleyecek
if "?" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

# Dialect düzeltme
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 🔥 Render External Bağlantı İçin En Stabil Ayarlar
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "sslmode": "require",
    },
    "pool_pre_ping": True,
    "pool_recycle": 30,  # Bağlantıyı çok sık tazele
    "pool_timeout": 30,
}

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Tablo oluşturma
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"DB Error: {e}")

# ---------------- ROUTES (ÖZET) ----------------
@app.route("/")
def index():
    try:
        photos = Photo.query.order_by(Photo.id.desc()).all()
        return render_template("index.html", photos=photos)
    except Exception as e:
        return f"Bağlantı hatası (Yenileyin): {str(e)}", 500

# LOGIN / REGISTER / PROFILE / UPLOAD (Mevcut kodların aynısı...)
# ... (Önceki attığım app.py'daki route kısımlarını buraya dahil edebilirsin)
# ...

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
    is_vip = user_to_show.username.lower() in ["bec", "beril"]
    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Henüz bir biyografi yok.",
        "followers": "2M" if is_vip else "0",
        "following": "0",
        "posts": len(photos),
        "is_vip": is_vip
    }
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id))

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("photo")
    if file:
        filename = f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        photo = Photo(title="Verzia Post", filename=filename, owner_id=current_user.id)
        db.session.add(photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)












