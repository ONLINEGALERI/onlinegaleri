from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime
import os

# Ayarlar ve Uzantılar
from config import Config
from extensions import db, migrate, login_manager

# Modeller
from models.user import User, Comment, Like, Notification
from models.photo import Photo

# ---------------- APP KURULUMU ----------------
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("SECRET_KEY", "verzia-final-2025-special")

# ---------------- DATABASE (RENDER KESİN ÇÖZÜM) ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render ve psycopg2-binary kütüphanesi arasındaki köprüyü kuruyoruz
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Lokal çalışma için fallback
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fallback.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 60,
    "pool_size": 10,
    "max_overflow": 20
}

# Uzantıları Başlat
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Tabloları Güvenli Başlat
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"DB Error: {e}")

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

# ---------------- ROUTES ----------------

@app.route("/")
def index():
    # Giriş yapılmışsa doğrudan profile fırlat
    if current_user.is_authenticated:
        try:
            return redirect(url_for("profile", username=current_user.username))
        except:
            logout_user()
            return redirect(url_for("index"))
            
    return render_template("index.html")

# 🔥 GİRİŞ YAP (Çalışan mekanizmayı koruyarak zırhladık)
@app.route("/login", methods=["POST"])
def login():
    try:
        username_or_email = request.form.get("username")
        password = request.form.get("password")

        if not username_or_email or not password:
            return jsonify({"status": "error", "message": "Eksik bilgi!"}), 400

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            # Tarayıcıyı tam URL ile yönlendiriyoruz
            return jsonify({
                "status": "success", 
                "redirect": url_for("profile", username=user.username, _external=True)
            })

        return jsonify({"status": "error", "message": "Giriş başarısız! Bilgileri kontrol edin."}), 401
    except Exception as e:
        print(f"Login Hatası: {e}")
        return jsonify({"status": "error", "message": "Sunucu hatası oluştu."}), 500

# ÜYE OL
@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("Bu hesap zaten var!", "error")
        return redirect(url_for("index"))

    new_user = User(username=username, email=email)
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("profile", username=new_user.username))
    except Exception as e:
        db.session.rollback()
        return f"Kayıt hatası: {str(e)}", 500

# PROFİL (Sayfa adı 'profile' olarak sabitlendi)
@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()
    # En yeni fotoğraflar üstte
    photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    
    is_vip = user_to_show.username.lower() in ["bec", "beril"]
    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Verzia Experience",
        "posts": len(photos),
        "is_vip": is_vip
    }
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("photo")
    if file:
        filename = f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
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












