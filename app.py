from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User, Comment, Like, Notification
from models.siteinfo import SiteInfo
from models.photo import Photo

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "gizli-key"

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Klasör Yapılandırması
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
os.makedirs(THUMB_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------- INDEX ---------------------
@app.route('/')
def index():
    all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
    return render_template('index.html', photos=all_photos)

# --------------------- AUTH ---------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({'status': 'error', 'message': 'Kullanıcı adı veya şifre hatalı.'}), 401
        
        login_user(user)
        return jsonify({'status': 'success', 'redirect': url_for('index')})
        
    return render_template('login_clean.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            return jsonify({'status': 'error', 'message': 'Kullanıcı zaten mevcut!'}), 400
            
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return jsonify({'status': 'success', 'redirect': url_for('index')})
        
    return render_template('register.html')

# --------------------- PROFILE ---------------------
@app.route('/profile')
def profile():
    username = request.args.get('username')
    user_to_show = None
    
    if username:
        user_to_show = User.query.filter_by(username=username).first()
    elif current_user.is_authenticated:
        user_to_show = current_user
        username = current_user.username
    else:
        return redirect(url_for('login'))

    if not user_to_show:
        abort(404)

    user_photos = Photo.query.filter_by(
        owner_id=user_to_show.id
    ).order_by(Photo.id.desc()).all()
    
    is_vip = user_to_show.username.lower() in ['bec', 'beril']
    
    is_following = False
    if current_user.is_authenticated and current_user.id != user_to_show.id:
        is_following = current_user.is_following(user_to_show)

    sp = {
        'username': user_to_show.username,
        'avatar': user_to_show.avatar or 'https://picsum.photos/seed/default/400/400',
        'bio': user_to_show.bio or 'Henüz bir biyografi eklenmedi.',
        'followers': '2M' if is_vip else user_to_show.followers_list.count(),
        'following': user_to_show.followed.count(),
        'posts': len(user_photos),
        'is_vip': is_vip
    }

    can_edit = current_user.is_authenticated and current_user.id == user_to_show.id
    return render_template(
        'profile.html',
        server_profile=sp,
        can_edit=can_edit,
        photos=user_photos,
        is_following=is_following
    )

# --------------------- SEARCH ---------------------
@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    results = []
    if query:
        results = User.query.filter(User.username.icontains(query)).all()
    return render_template('search.html', results=results, query=query)

# --------------------- NOTIFICATIONS ---------------------
@app.route('/notifications')
@login_required
def get_notifications():
    notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.timestamp.desc()).limit(20).all()

    return jsonify([{
        'id': n.id,
        'sender': n.sender_username,
        'type': n.notif_type,
        'message': n.message,
        'is_read': n.is_read,
        'photo_id': n.photo_id,
        'time': n.timestamp.strftime('%H:%M')
    } for n in notifs])

@app.route('/notifications/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})

@app.route('/notifications/mark-as-read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({Notification.is_read: True})
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/notifications/delete/<int:notif_id>', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        abort(403)
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'status': 'success'})

# --------------------- SOCIAL ---------------------
@app.route('/like/<int:photo_id>', methods=['POST'])
@login_required
def like_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    existing = Like.query.filter_by(
        user_id=current_user.id,
        photo_id=photo_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({
            'status': 'unliked',
            'like_count': Like.query.filter_by(photo_id=photo_id).count()
        })
    
    new_like = Like(user_id=current_user.id, photo_id=photo_id)
    db.session.add(new_like)

    if photo.owner_id != current_user.id:
        notif = Notification(
            user_id=photo.owner_id,
            sender_username=current_user.username,
            notif_type='like',
            photo_id=photo.id,
            message="bir fotoğrafını beğendi."
        )
        db.session.add(notif)

    db.session.commit()
    return jsonify({
        'status': 'liked',
        'like_count': Like.query.filter_by(photo_id=photo_id).count()
    })

@app.route('/comment/<int:photo_id>', methods=['POST'])
@login_required
def add_comment(photo_id):
    data = request.get_json()
    comment_body = data.get('content')

    if not comment_body:
        return jsonify({'status': 'error'}), 400

    photo = Photo.query.get_or_404(photo_id)
    new_comment = Comment(
        body=comment_body,
        user_id=current_user.id,
        photo_id=photo_id
    )
    db.session.add(new_comment)

    if photo.owner_id != current_user.id:
        preview = comment_body[:20] + '...' if len(comment_body) > 20 else comment_body
        notif = Notification(
            user_id=photo.owner_id,
            sender_username=current_user.username,
            notif_type='comment',
            photo_id=photo.id,
            message=f"fotoğrafına yorum yaptı: {preview}"
        )
        db.session.add(notif)

    db.session.commit()
    return jsonify({
        'status': 'success',
        'comment_id': new_comment.id,
        'username': current_user.username,
        'content': comment_body
    })

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if not user or user == current_user:
        return jsonify({'status': 'error'}), 400

    current_user.follow(user)
    notif = Notification(
        user_id=user.id,
        sender_username=current_user.username,
        notif_type='follow',
        message="seni takip etmeye başladı."
    )
    db.session.add(notif)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{current_user.id}_{filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        try:
            img = Image.open(path)
            img.thumbnail((400, 400))
            img.save(os.path.join(THUMB_FOLDER, filename))
        except:
            pass

        new_photo = Photo(
            title=request.form.get('title', 'Verzia Post'),
            filename=filename,
            owner_id=current_user.id
        )
        db.session.add(new_photo)
        db.session.commit()

    return redirect(url_for('profile', username=current_user.username))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    data = request.get_json()
    if data:
        if 'bio' in data:
            current_user.bio = data.get('bio')
        if 'avatar' in data:
            current_user.avatar = data.get('avatar')
        db.session.commit()
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'}), 400

@app.route('/get_comments/<int:photo_id>')
def get_comments(photo_id):
    comments = Comment.query.filter_by(
        photo_id=photo_id
    ).order_by(Comment.timestamp.asc()).all()

    return jsonify([{
        'id': c.id,
        'username': User.query.get(c.user_id).username,
        'content': c.body,
        'can_delete': (
            current_user.is_authenticated and
            (c.user_id == current_user.id or current_user.username.lower() == 'bec')
        )
    } for c in comments])

# --------------------- RENDER UYUMLU ÇALIŞTIRMA ---------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
