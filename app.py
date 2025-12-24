from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash
from flask_login import login_user, logout_user, current_user, login_required
import os
from werkzeug.utils import secure_filename

from extensions import db, migrate, login_manager
from models.user import User, Comment, Like 
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
    return User.query.get(int(user_id))

# --------------------- ANA SAYFA VE AUTH (DÜZENLENDİ) ---------------------
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
    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Bu e-posta zaten kayıtlı!"}), 400
    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)
    return jsonify({"status": "success", "redirect": url_for("profile", username=new_user.username)})

# --------------------- PROFİL VE SOSYAL (GÜNCELLENDİ) ---------------------
@app.route("/profile/<username>")
@login_required
def profile(username):
    user_to_show = User.query.filter_by(username=username).first_or_404()
    photos = Photo.query.filter_by(owner_id=user_to_show.id).order_by(Photo.id.desc()).all()
    
    # KURUCU LİSTESİ
    kurucular = ["beril", "ecem", "cemre"]
    is_kurucu = user_to_show.username.lower() in kurucular
    
    profile_data = {
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Verzia Experience",
        # Kuruculara 1.5M tanımlıyoruz
        "followers": "1.5M" if is_kurucu else user_to_show.followers_list.count(),
        "following": user_to_show.followed.count(),
        "is_vip": is_kurucu or user_to_show.username.lower() == "bec",
        "is_kurucu": is_kurucu # HTML'de takipçi listesini kilitlemek için
    }
    
    is_following = current_user.is_following(user_to_show)
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id), is_following=is_following)

@app.route("/update_bio", methods=["POST"])
@login_required
def update_bio():
    new_bio = request.form.get("bio")
    user = User.query.get(current_user.id)
    if user:
        user.bio = new_bio
        db.session.commit()
    return redirect(url_for("profile", username=user.username))

# --------------------- AYARLAR (GÜNCELLENDİ: ŞİFRE DOĞRULAMA) ---------------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        user = User.query.get(current_user.id)
        current_password = request.form.get("current_password") # HTML'den gelen mevcut şifre
        new_username = request.form.get("username")
        new_password = request.form.get("password")

        # GÜVENLİK: Önce mevcut şifreyi kontrol et
        if not current_password or not user.check_password(current_password):
            flash("Mevcut şifren hatalı aşkım, kontrol eder misin?", "error")
            return redirect(url_for("settings"))

        # Kullanıcı adı müsait mi kontrolü
        if new_username and new_username != user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user and existing_user.id != user.id:
                flash("Bu kullanıcı adı zaten alınmış!", "error")
            else:
                user.username = new_username
        
        # Yeni şifre girildiyse güncelle
        if new_password:
            user.set_password(new_password)
            
        db.session.commit()
        flash("Değişiklikler başarıyla kaydedildi.", "success")
        return redirect(url_for("profile", username=user.username))
        
    return render_template("settings.html")

# --------------------- UPLOAD ---------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if 'photo' not in request.files: return redirect(request.url)
    file = request.files['photo']
    if file and file.filename != '':
        filename = secure_filename(f"{current_user.id}_{file.filename}")
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        new_photo = Photo(filename=filename, owner_id=current_user.id, title=request.form.get("title", "Verzia Photo"))
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

# --------------------- BEĞENİ VE YORUM ---------------------
@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first()
    if existing_like:
        db.session.delete(existing_like)
        status = 'unliked'
    else:
        new_like = Like(user_id=current_user.id, photo_id=photo_id)
        db.session.add(new_like)
        status = 'liked'
    db.session.commit()
    return jsonify({'status': status, 'like_count': len(photo.likes)})

@app.route('/comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    data = request.get_json()
    content = data.get('content')
    if not content: return jsonify({'status': 'error'}), 400
    new_comment = Comment(body=content, user_id=current_user.id, photo_id=photo_id)
    db.session.add(new_comment)
    db.session.commit()
    return jsonify({'status': 'success', 'username': current_user.username, 'content': content})

@app.route('/get_comments/<int:photo_id>')
def get_comments(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    comments = [{'username': User.query.get(c.user_id).username, 'content': c.body} for c in photo.comments]
    return jsonify(comments)

# --------------------- ARAMA MOTORU ---------------------
@app.route("/search_users")
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    users = User.query.filter(User.username.ilike(f"%{query}%")).limit(10).all()
    results = [{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users]
    return jsonify(results)

# --------------------- LİSTE GETİRME ---------------------
@app.route("/get_user_list/<username>/<type>")
@login_required
def get_user_list(username, type):
    user = User.query.filter_by(username=username).first_or_404()
    if type == 'followers':
        kurucular = ["beril", "ecem", "cemre"]
        if user.username.lower() in kurucular:
            return jsonify([])
        users = user.followers_list.all()
    else:
        users = user.followed.all()
        
    results = [{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users]
    return jsonify(results)

# --------------------- DİĞER ROTALAR ---------------------
@app.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        current_user.follow(user)
        db.session.commit()
        return jsonify({"status": "success", "followers": user.followers_list.count()})
    return jsonify({"status": "error"}), 404

@app.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        current_user.unfollow(user)
        db.session.commit()
        return jsonify({"status": "success", "followers": user.followers_list.count()})
    return jsonify({"status": "error"}), 404

@app.route("/profile/save", methods=["POST"])
@login_required
def save_profile():
    data = request.get_json()
    user = User.query.get(current_user.id)
    if "bio" in data: user.bio = data["bio"]
    if "avatar" in data: user.avatar = data["avatar"]
    db.session.commit()
    return jsonify({"status": "success"})

@app.route("/delete_photo_profile/<int:photo_id>", methods=["POST"])
@login_required
def delete_photo_profile(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.owner_id == current_user.id:
        db.session.delete(photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1", port=5000, debug=True)












