from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, flash
from flask_login import login_user, logout_user, current_user, login_required
import os
import base64 # Render için ölümsüzlük büyüsü eklendi
from werkzeug.utils import secure_filename

from extensions import db, migrate, login_manager
from models.user import User, Comment, Like, Notification # Notification eklendi
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

# --------------------- BİLDİRİM CONTEXT PROCESSOR ---------------------
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
    if User.query.filter_by(email=email).first():
        return jsonify({"status": "error", "message": "Bu e-posta zaten kayıtlı!"}), 400
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
        "id": user_to_show.id,
        "username": user_to_show.username,
        "avatar": user_to_show.avatar or "https://picsum.photos/400",
        "bio": user_to_show.bio or "Verzia Experience",
        "followers": followers_display,
        "following": user_to_show.followed.count(),
        "is_vip": is_kurucu or is_ana_profil or user_to_show.username.lower() == "bec",
        "is_kurucu": is_kurucu or is_ana_profil
    }
    
    is_following = current_user.is_following(user_to_show)
    return render_template("profile.html", server_profile=profile_data, photos=photos, can_edit=(current_user.id == user_to_show.id), is_following=is_following)

# --------------------- RENDER İÇİN ÖLÜMSÜZ UPLOAD (BASE64) ---------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if 'photo' not in request.files: return redirect(request.url)
    file = request.files['photo']
    if file and file.filename != '':
        # Render'da asla silinmemesi için dosyayı Base64 verisine çeviriyoruz
        img_data = base64.b64encode(file.read()).decode('utf-8')
        mimetype = file.mimetype
        # URL yerine veriyi veritabanına gömüyoruz
        data_url = f"data:{mimetype};base64,{img_data}"
        
        new_photo = Photo(filename=data_url, owner_id=current_user.id, title="Verzia Photo")
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for("profile", username=current_user.username))

# --------------------- POST DETAYLARI ---------------------
@app.route('/get_post_details/<int:photo_id>')
@login_required
def get_post_details(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    is_liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first() is not None
    comments = []
    for c in photo.comments:
        c_user = db.session.get(User, c.user_id)
        comments.append({"username": c_user.username, "text": c.body, "timestamp": "Şimdi"})
    return jsonify({"likes": len(photo.likes), "is_liked": is_liked, "comments": comments})

@app.route("/update_bio", methods=["POST"])
@login_required
def update_bio():
    new_bio = request.form.get("bio")
    user = db.session.get(User, current_user.id)
    if user:
        user.bio = new_bio
        db.session.commit()
    return redirect(url_for("profile", username=user.username))

@app.route('/notifications')
@login_required
def get_notifications():
    notifs = current_user.notifications.order_by(Notification.timestamp.desc()).limit(20).all()
    results = []
    for n in notifs:
        results.append({"id": n.id, "sender": n.sender_username, "type": n.notif_type, "message": n.message, "is_read": n.is_read, "timestamp": n.timestamp.strftime("%d.%m %H:%M")})
    for n in notifs: n.is_read = True
    db.session.commit()
    return jsonify(results)

@app.route('/delete_notification/<int:notif_id>', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        db.session.delete(notif)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        user = db.session.get(User, current_user.id)
        current_password = request.form.get("current_password")
        new_username = request.form.get("username")
        new_password = request.form.get("password")
        if not current_password or not user.check_password(current_password):
            flash("Mevcut şifren hatalı aşkım!", "error")
            return redirect(url_for("settings"))
        if new_username and new_username != user.username:
            user.username = new_username
        if new_password: user.set_password(new_password)
        db.session.commit()
        flash("Değişiklikler kaydedildi.", "success")
        return redirect(url_for("profile", username=user.username))
    return render_template("settings.html")

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
        new_like = Like(user_id=current_user.id, photo_id=photo_id)
        db.session.add(new_like)
        status = 'liked'
        if photo.owner_id != current_user.id:
            notif = Notification(user_id=photo.owner_id, sender_username=current_user.username, notif_type="like", photo_id=photo_id, message=f"{current_user.username} bir fotoğrafını beğendi!")
            db.session.add(notif)
    db.session.commit()
    return jsonify({'status': status, 'like_count': len(photo.likes)})

@app.route('/comment/<int:photo_id>', methods=['POST'])
@app.route('/add_comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    data = request.get_json()
    content = data.get('content') or data.get('text')
    if not content: return jsonify({'status': 'error'}), 400
    new_comment = Comment(body=content, user_id=current_user.id, photo_id=photo_id)
    db.session.add(new_comment)
    photo = Photo.query.get(photo_id)
    if photo.owner_id != current_user.id:
        notif = Notification(user_id=photo.owner_id, sender_username=current_user.username, notif_type="comment", photo_id=photo_id, message=f"{current_user.username} fotoğrafına yorum yaptı!")
        db.session.add(notif)
    db.session.commit()
    return jsonify({'status': 'success', 'username': current_user.username, 'content': content})

@app.route('/get_comments/<int:photo_id>')
def get_comments(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    comments = [{'username': db.session.get(User, c.user_id).username, 'content': c.body} for c in photo.comments]
    return jsonify(comments)

@app.route("/search_users")
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2: return jsonify([])
    users = User.query.filter(User.username.ilike(f"%{query}%")).limit(10).all()
    results = [{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users]
    return jsonify(results)

@app.route("/get_user_list/<username>/<type>")
@login_required
def get_user_list(username, type):
    user = User.query.filter_by(username=username).first_or_404()
    if type == 'followers':
        kurucular = ["beril", "ecem", "cemre", "verzia"]
        if user.username.lower() in kurucular: return jsonify([])
        users = user.followers_list.all()
    else: users = user.followed.all()
    results = [{"username": u.username, "avatar": u.avatar or "https://picsum.photos/100"} for u in users]
    return jsonify(results)

@app.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        current_user.follow(user)
        notif = Notification(user_id=user.id, sender_username=current_user.username, notif_type="follow", message=f"{current_user.username} seni takip etmeye başladı!")
        db.session.add(notif)
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

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # Eğer filename zaten bir Base64 verisiyse (data:image...) onu doğrudan döndürmeyiz,
    # ama bu rota eski dosyalar için kalmalı. Base64 olanlar doğrudan <img> tag'inde çalışacak.
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.1.1.1", port=5000, debug=True)












