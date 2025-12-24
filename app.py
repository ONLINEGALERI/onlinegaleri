from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_login import login_user, logout_user, current_user, login_required
import os

from extensions import db, migrate, login_manager
from models.user import User
from models.photo import Photo

app = Flask(__name__)
app.config.from_object('config.Config')
app.secret_key = os.environ.get("SECRET_KEY", "verzia-special-2025")

# DATABASE AYARI: Lokal ve Render uyumlu
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Bilgisayarında çalışırken bu dosyayı otomatik oluşturur
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///verzia_local.db"

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("profile", username=current_user.username))
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

# YENİ EKLENEN KAYIT OLMA FONKSİYONU
@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")

    # Kullanıcı adı veya email zaten var mı kontrol et
    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "Bu kullanıcı adı zaten alınmış!"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Bu e-posta zaten kayıtlı!"}), 400

    # Yeni kullanıcı oluştur
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()

    # Kayıt olunca otomatik giriş yap
    login_user(new_user, remember=True)
    
    return jsonify({
        "status": "success", 
        "redirect": url_for("profile", username=new_user.username)
    })

@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()
    photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Verzia Experience",
        "is_vip": user_to_show.username.lower() in ["bec", "beril"]
    }
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# LOGOUT (Çıkış yapmayı da ekledim ki profilinde buton çalışsın)
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1", port=5000, debug=True)












