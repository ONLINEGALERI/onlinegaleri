from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash, session
from flask_login import login_user, logout_user, current_user, login_required
import os
import base64 
from datetime import datetime

from extensions import db, migrate, login_manager
from models.user import User, Comment, Like, Notification 
from models.photo import Photo

app = Flask(__name__)
app.config.from_object('config.Config')
app.secret_key = os.environ.get("SECRET_KEY", "verzia-special-2025")

# --------------------- DATABASE AYARI (RAILWAY UYUMLU) ---------------------
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

# --------------------- BİLDİRİM SİSTEMİ ENJEKSİYONU ---------------------
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
    
    profile_data = {
        "id": user_to_show.id, "username": user_to_show.username, "avatar": user_to_show.avatar or "https://picsum.photos/400", 
        "bio": user_to_show.bio or "Verzia Experience", 
        "followers": "2M" if is_ana_profil else ("1.5M" if is_kurucu else user_to_show.followers_list.count()), 
        "following": user_to_show.followed.count(), 
        "is_vip": is_kurucu or is_ana_profil, "is_kurucu": is_kurucu or is_ana_profil
    }
    is_following = current_user.is_following(user_to_show)
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id), is_following=is_following)

@app.route("/update_bio", methods=["POST"]) # Hatanın çözümü bu rotaydı!
@login_required
def update_bio():
    new_bio = request.form.get("bio")
    user = db.session.get(User, current_user.id)
    if user:
        user.bio = new_bio
        db.session.commit()
    return redirect(url_for("profile", username=user.username))

# --------------------- TAKİP SİSTEMİ ---------------------
@app.route("/follow/<username>", methods=['POST'])
@login_required
def toggle_follow(username):
    user_to_follow = User.query.filter_by(username=username).first_or_404()
    if user_to_follow == current_user:
        return jsonify({"status": "error", "message": "Kendinizi takip edemezsiniz."}), 400
    if current_user.is_following(user_to_follow):
        current_user.unfollow(user_to_follow)
        status = "unfollowed"
    else:
        current_user.follow(user_to_follow)
        status = "followed"
        notif = Notification(user_id=user_to_follow.id, sender_username=current_user.username, notif_type="follow", message=f"@{current_user.username} sizi takip etmeye başladı.", is_read=False)
        db.session.add(notif)
    db.session.commit()
    return jsonify({"status": status, "follower_count": user_to_follow.followers_list.count()})

# --------------------- ETKİLEŞİM (BEĞENİ & YORUM) ---------------------
@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first()
    if existing_like:
        db.session.delete(existing_like)
        status = "unliked"
    else:
        new_like = Like(user_id=current_user.id, photo_id=photo_id)
        db.session.add(new_like)
        status = "liked"
        if photo.owner_id != current_user.id:
            db.session.add(Notification(user_id=photo.owner_id, sender_username=current_user.username, notif_type="like", message=f"@{current_user.username} fotoğrafını beğendi.", is_read=False))
    db.session.commit()
    return jsonify({"status": status, "like_count": len(photo.likes)})

@app.route('/add_comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    try:
        data = request.get_json()
        comment_body = data.get('text', '').strip()
        if not comment_body: return jsonify({"status": "error"}), 400
        photo = Photo.query.get_or_404(photo_id)
        new_comment = Comment(body=comment_body, user_id=current_user.id, photo_id=photo_id)
        db.session.add(new_comment)
        if photo.owner_id != current_user.id:
            db.session.add(Notification(user_id=photo.owner_id, sender_username=current_user.username, notif_type="comment", message=f"@{current_user.username} fotoğrafına yorum yaptı.", is_read=False))
        db.session.commit()
        return jsonify({'status': 'success', 'username': current_user.username, 'text': comment_body})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error'}), 500

@app.route('/get_post_details/<int:photo_id>')
@login_required
def get_post_details(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    is_liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first() is not None
    return jsonify({
        "likes": len(photo.likes),
        "is_liked": is_liked,
        "comments": [{"id": c.id, "username": User.query.get(c.user_id).username, "text": c.body, "can_delete": (c.user_id == current_user.id or photo.owner_id == current_user.id)} for c in photo.comments]
    })

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    photo = Photo.query.get(comment.photo_id)
    if comment.user_id == current_user.id or photo.owner_id == current_user.id:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

# --------------------- ADMIN & AYARLAR ---------------------
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    current_username = current_user.username.replace('İ', 'i').replace('I', 'ı').lower()
    if "verzia" not in current_username: return redirect(url_for("profile", username=current_user.username))
    all_users = User.query.order_by(User.id.desc()).all()
    all_photos = Photo.query.order_by(Photo.id.desc()).all()
    return render_template("admin.html", users=all_users, photos=all_photos)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        if request.form.get("username"): current_user.username = request.form.get("username")
        if request.form.get("password"): current_user.set_password(request.form.get("password"))
        db.session.commit()
        return redirect(url_for("profile", username=current_user.username))
    return render_template("settings.html", user=current_user)

# --------------------- FOTOĞRAF İŞLEMLERİ ---------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get('photo')
    if file:
        img_data = base64.b64encode(file.read()).decode('utf-8')
        new_photo = Photo(filename=f"data:{file.mimetype};base64,{img_data}", owner_id=current_user.id, title="Verzia Moment")
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.owner_id != current_user.id and "verzia" not in current_user.username.lower(): return jsonify({"status": "error"}), 403
    db.session.delete(photo)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route("/logout")
def logout():
    logout_user(); return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)










