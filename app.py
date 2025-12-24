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
    
    # LUXURY BIO UPDATE - JİLET GİBİ EKLEDİM AŞKIM
    luxury_bio = "Sıradanlığın ötesinde, ışığın ve estetiğin en asil buluşma noktası. Verzia; derin bir asaletin altının büyüleyici parıltısıyla harmanlandığı, dijital dünyanın pırlanta dokunuşlu sergi salonudur. Burada her kare zarafetle mühürlenir, her detay ihtişamla nefes alır. Sadece en özel anılarınızı değil, ruhunuzun ışıltısını da bu altın standartlarda ölümsüzleştirin."
    
    profile_data = {
        "id": user_to_show.id, "username": user_to_show.username, "avatar": user_to_show.avatar or "https://picsum.photos/400", 
        "bio": user_to_show.bio or luxury_bio, 
        "followers": "2M" if is_ana_profil else ("1.5M" if is_kurucu else user_to_show.followers_list.count()), 
        "following": user_to_show.followed.count(), 
        "is_vip": is_kurucu or is_ana_profil, "is_kurucu": is_kurucu or is_ana_profil
    }
    is_following = current_user.is_following(user_to_show)
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id), is_following=is_following)

@app.route("/update_bio", methods=["POST"])
@login_required
def update_bio():
    new_bio = request.form.get("bio")
    user = db.session.get(User, current_user.id)
    if user:
        user.bio = new_bio
        db.session.commit()
    return redirect(url_for("profile", username=user.username))

# --------------------- FOTOĞRAF VE AVATAR UPLOAD (BASE64) ---------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get('photo')
    if file:
        img_data = base64.b64encode(file.read()).decode('utf-8')
        db.session.add(Photo(filename=f"data:{file.mimetype};base64,{img_data}", owner_id=current_user.id))
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

@app.route("/update_avatar", methods=["POST"])
@login_required
def update_avatar():
    file = request.files.get('avatar')
    if file:
        img_data = base64.b64encode(file.read()).decode('utf-8')
        current_user.avatar = f"data:{file.mimetype};base64,{img_data}"
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# --------------------- BİLDİRİM ROTALARI (MÜHÜRLENDİ) ---------------------
@app.route("/notifications")
@login_required
def get_notifications():
    try:
        notifications = current_user.notifications.order_by(Notification.id.desc()).limit(15).all()
        data = []
        for n in notifications:
            data.append({
                "id": n.id,
                "sender": n.sender_username if hasattr(n, 'sender_username') else "Verzia",
                "message": n.message,
                "timestamp": n.timestamp.strftime("%d.%m %H:%M") if hasattr(n, 'timestamp') else "",
                "is_read": n.is_read
            })
        current_user.notifications.filter_by(is_read=False).update({"is_read": True})
        db.session.commit()
        return jsonify(data)
    except Exception as e:
        return jsonify([])

@app.route("/delete_notification/<int:notif_id>", methods=["POST"])
@login_required
def delete_notification(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.user_id == current_user.id:
        db.session.delete(n)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

# --------------------- DİĞER SOSYAL ROTALAR ---------------------
@app.route("/search_users")
@login_required
def search_users():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    users = User.query.filter(User.username.ilike(f"%{q}%")).limit(10).all()
    return jsonify([{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users])

@app.route('/get_post_details/<int:photo_id>')
@login_required
def get_post_details(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    is_liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first() is not None
    comment_data = [{"id": c.id, "username": db.session.get(User, c.user_id).username, "text": c.body, "can_delete": (c.user_id == current_user.id or photo.owner_id == current_user.id)} for c in photo.comments]
    return jsonify({"likes": len(photo.likes), "is_liked": is_liked, "comments": comment_data})

@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first()
    if existing_like: db.session.delete(existing_like)
    else: db.session.add(Like(user_id=current_user.id, photo_id=photo_id))
    db.session.commit()
    return jsonify({'status': 'liked' if not existing_like else 'unliked', 'like_count': len(photo.likes)})

@app.route('/comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    data = request.get_json()
    db.session.add(Comment(body=data.get('text'), user_id=current_user.id, photo_id=photo_id))
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route("/get_user_list/<username>/<type>")
@login_required
def get_user_list(username, type):
    user = User.query.filter_by(username=username).first_or_404()
    if user.username.lower() in ["beril", "ecem", "cemre", "verzia"] and type == 'followers': return jsonify([])
    users = user.followers_list.all() if type == 'followers' else user.followed.all()
    return jsonify([{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users])

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        cp = request.form.get("current_password")
        if not current_user.check_password(cp):
            flash("Mevcut şifre hatalı!", "error")
            return redirect(url_for("settings"))
        if request.form.get("username"): current_user.username = request.form.get("username")
        if request.form.get("password"): current_user.set_password(request.form.get("password"))
        db.session.commit()
        return redirect(url_for("profile", username=current_user.username))
    return render_template("settings.html", user=current_user)

@app.route("/logout")
def logout():
    logout_user(); return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    # PORT ÇAKIŞMASINI ÖNLEMEK İÇİN 5001 YAPTIM AŞKIM
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)












