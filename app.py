from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, abort
from werkzeug.utils import secure_filename
from PIL import Image
import os

from config import Config
from extensions import db, migrate, login_manager
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User
from models.siteinfo import SiteInfo
from models.post import Post


app = Flask(__name__)
app.config.from_object(Config)

# initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)

# Basic upload folders and allowed extensions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(THUMB_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # prefer form 'next' then querystring
        next_page = request.form.get('next') or request.args.get('next')
        user = None
        if username:
            # allow login by username or email
            user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Başarıyla giriş yapıldı', 'success')
            # validate next_page - only allow relative paths
            if next_page and isinstance(next_page, str) and next_page.startswith('/'):
                return redirect(next_page)
            # otherwise redirect to the user's profile
            return redirect(url_for('profile', username=user.username))
        flash('Geçersiz kullanıcı adı veya şifre', 'danger')
    return render_template('login_clean.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış yapıldı', 'info')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        p1 = request.form.get('password1')
        p2 = request.form.get('password2')
        if not username or not email or not p1:
            flash('Tüm alanlar gerekli', 'danger')
            return redirect(url_for('register'))
        if p1 != p2:
            flash('Şifreler eşleşmiyor', 'danger')
            return redirect(url_for('register'))
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Kullanıcı adı veya email zaten kayıtlı', 'warning')
            return redirect(url_for('register'))
        u = User(username=username, email=email)
        u.set_password(p1)
        db.session.add(u)
        db.session.commit()
        flash('Kayıt başarılı. Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    # GET
    return render_template('register.html')


@app.route('/profile')
def profile():
    # Allow optional username via query string: /profile?username=cemre
    username = request.args.get('username')
    server_profile = None
    if username:
        server_profile = User.query.filter_by(username=username).first()
    else:
        if current_user.is_authenticated:
            server_profile = current_user
            username = current_user.username
    # pass a simple dict to template if server_profile exists
    sp = None
    if server_profile:
        sp = {
            'username': server_profile.username,
            'avatar': server_profile.avatar,
            'name': server_profile.username,
            'handle': f"@{server_profile.username}",
            'bio': server_profile.bio,
            'followers': server_profile.followers,
            'following': server_profile.following,
            'posts': server_profile.posts
        }
        # load posts for this user (latest first)
        posts_q = Post.query.filter_by(user_id=server_profile.id, archived=False).order_by(Post.created_at.desc()).all()
        posts = [p.to_dict(base_url=request.url_root) for p in posts_q]
    else:
        posts = []
    can_edit = False
    try:
        can_edit = current_user.is_authenticated and current_user.username == username
    except Exception:
        can_edit = False
    # is_following: whether current_user follows this server_profile (for follow button)
    is_following = False
    if server_profile and current_user.is_authenticated and current_user.id != server_profile.id:
        try:
            is_following = current_user.is_following(server_profile)
        except Exception:
            is_following = False
    return render_template('profile.html', username=username, server_profile=sp, can_edit=can_edit, is_following=is_following, posts=posts)


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    target = User.query.filter_by(username=username).first()
    if not target:
        return jsonify({'status':'error','message':'Kullanıcı bulunamadı'}), 404
    if target.id == current_user.id:
        return jsonify({'status':'error','message':'Kendinizi takip edemezsiniz'}), 400
    try:
        current_user.follow(target)
        db.session.commit()
        return jsonify({'status':'ok','followers': target.followers, 'following': current_user.following})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/profile/<username>/followers')
def profile_followers(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)
    # build list from relationship
    followers = [u for u in user.followers_rel]
    return render_template('follow_list.html', title='Takipçiler', username=username, items=followers)


@app.route('/profile/<username>/following')
def profile_following(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)
    following = [u for u in user.following_rel]
    return render_template('follow_list.html', title='Takip Edilenler', username=username, items=following)


@app.route('/profile/<username>/archive')
@login_required
def profile_archive(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)
    # only owner or admin can view archived posts
    if not (current_user.is_authenticated and (current_user.id == user.id or getattr(current_user,'is_admin',False))):
        abort(403)
    archived_posts = Post.query.filter_by(user_id=user.id, archived=True).order_by(Post.created_at.desc()).all()
    posts = [p.to_dict(base_url=request.url_root) for p in archived_posts]
    return render_template('archive_list.html', username=username, posts=posts)


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    target = User.query.filter_by(username=username).first()
    if not target:
        return jsonify({'status':'error','message':'Kullanıcı bulunamadı'}), 404
    if target.id == current_user.id:
        return jsonify({'status':'error','message':'Kendinizi takipten çıkaramazsınız'}), 400
    try:
        current_user.unfollow(target)
        db.session.commit()
        return jsonify({'status':'ok','followers': target.followers, 'following': current_user.following})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/profile/save', methods=['POST'])
@login_required
def save_profile():
    # Accept form POST from edit modal
    data = request.form or request.get_json() or {}
    avatar = data.get('avatar')
    name = data.get('name')
    handle = data.get('handle')
    bio = data.get('bio')
    # followers/following/posts counters are managed server-side (do not accept from client)

    u = current_user
    # allow clearing avatar by submitting empty string
    if 'avatar' in data:
        u.avatar = avatar or None
    if bio is not None:
        u.bio = bio
    # name/handle can be client visible but avoid changing username column here to keep uniqueness
    # (if you want to allow username change add validation endpoint)
    db.session.commit()
    return jsonify({'status':'ok'})


@app.route('/profile/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'status':'error','message':'Dosya bulunamadı'}), 400
    file = request.files['avatar']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)
        try:
            img = Image.open(filepath)
            img.thumbnail((400, 400))
            thumbpath = os.path.join(THUMB_FOLDER, filename)
            img.save(thumbpath)
        except Exception:
            pass
        # set user's avatar to the uploads route
        current_user.avatar = url_for('uploaded_file', filename=filename)
        db.session.commit()
        return jsonify({'status':'ok','avatar': current_user.avatar})
    return jsonify({'status':'error','message':'Geçersiz dosya türü'}), 400


@app.route('/gallery')
def gallery():
    try:
        images = [f for f in os.listdir(THUMB_FOLDER) if os.path.isfile(os.path.join(THUMB_FOLDER, f))]
    except Exception:
        images = []
    return render_template('gallery.html', images=images)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'photo' not in request.files:
            flash('Dosya bulunamadı', 'warning')
            return redirect(request.url)
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(filepath)
            try:
                img = Image.open(filepath)
                img.thumbnail((200, 200))
                img.save(os.path.join(THUMB_FOLDER, filename))
            except Exception:
                pass
            return redirect(url_for('gallery'))
        flash('Geçersiz dosya türü', 'danger')
    return render_template('upload.html')


@app.route('/post/upload', methods=['POST'])
@login_required
def upload_post():
    if 'photo' not in request.files:
        flash('Dosya bulunamadı', 'warning')
        return redirect(request.referrer or url_for('profile'))
    file = request.files['photo']
    caption = request.form.get('caption')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)
        try:
            img = Image.open(filepath)
            img.thumbnail((600, 600))
            img.save(os.path.join(THUMB_FOLDER, filename))
        except Exception:
            pass
        # create post
        p = Post(user_id=current_user.id, filename=filename, caption=caption)
        db.session.add(p)
        try:
            current_user.posts = (current_user.posts or 0) + 1
        except Exception:
            pass
        db.session.commit()
        flash('Gönderi yüklendi', 'success')
        return redirect(url_for('profile', username=current_user.username))
    flash('Geçersiz dosya türü', 'danger')
    return redirect(request.referrer or url_for('profile'))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    p = Post.query.get(post_id)
    if not p:
        flash('Gönderi bulunamadı', 'warning')
        return redirect(request.referrer or url_for('profile'))
    if p.user_id != current_user.id and not getattr(current_user,'is_admin',False):
        flash('Yetkiniz yok', 'danger')
        return redirect(request.referrer or url_for('profile'))
    # delete files
    try:
        os.remove(os.path.join(UPLOAD_FOLDER, p.filename))
    except Exception:
        pass
    try:
        os.remove(os.path.join(THUMB_FOLDER, p.filename))
    except Exception:
        pass
    try:
        # decrement the owner's post counter
        owner = User.query.get(p.user_id)
        db.session.delete(p)
        if owner:
            try:
                owner.posts = max(0, (owner.posts or 1) - 1)
            except Exception:
                pass
        db.session.commit()
        # If request came via AJAX, return JSON so frontend can update without redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status':'ok'})
    except Exception:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status':'error','message':'Silme işlemi başarısız oldu'}), 500
    # Non-AJAX fallback
    flash('Gönderi silindi', 'success')
    return redirect(url_for('profile', username=current_user.username))


@app.route('/post/<int:post_id>/archive', methods=['POST'])
@login_required
def archive_post(post_id):
    p = Post.query.get(post_id)
    if not p:
        return jsonify({'status':'error','message':'Gönderi bulunamadı'}), 404
    if p.user_id != current_user.id and not getattr(current_user,'is_admin',False):
        return jsonify({'status':'error','message':'Yetkiniz yok'}), 403
    try:
        p.archived = True
        owner = User.query.get(p.user_id)
        if owner:
            try:
                owner.posts = max(0, (owner.posts or 1) - 1)
            except Exception:
                pass
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/post/<int:post_id>/unarchive', methods=['POST'])
@login_required
def unarchive_post(post_id):
    p = Post.query.get(post_id)
    if not p:
        return jsonify({'status':'error','message':'Gönderi bulunamadı'}), 404
    if p.user_id != current_user.id and not getattr(current_user,'is_admin',False):
        return jsonify({'status':'error','message':'Yetkiniz yok'}), 403
    try:
        p.archived = False
        owner = User.query.get(p.user_id)
        if owner:
            try:
                owner.posts = (owner.posts or 0) + 1
            except Exception:
                pass
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/account/change-username', methods=['POST'])
@login_required
def change_username():
    new_username = request.form.get('new_username')
    password = request.form.get('password')
    if not new_username or not password:
        return jsonify({'status':'error','message':'Eksik parametre'}), 400
    # verify password
    if not current_user.check_password(password):
        return jsonify({'status':'error','message':'Parola yanlış'}), 403
    # check uniqueness
    if User.query.filter(User.username == new_username).first():
        return jsonify({'status':'error','message':'Kullanıcı adı alınmış'}), 409
    try:
        current_user.username = new_username
        db.session.commit()
        return jsonify({'status':'ok','username': new_username})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        print(f"Yeni mesaj: {name} - {email} - {message}")
        flash('Mesajınız alındı', 'success')
        return redirect(url_for('index'))
    # show stored site owner info if any
    si = SiteInfo.query.first()
    site_info = si.to_dict() if si else None
    return render_template('contact.html', site_info=site_info)


@app.route('/admin/siteinfo', methods=['GET', 'POST'])
@login_required
def edit_siteinfo():
    # Only admin users can edit site info
    if not getattr(current_user, 'is_admin', False):
        abort(403)
    si = SiteInfo.query.first()
    if request.method == 'POST':
        email = request.form.get('contact_email')
        phone = request.form.get('contact_phone')
        addr = request.form.get('contact_address')
        extra = request.form.get('extra')
        if not si:
            si = SiteInfo(contact_email=email, contact_phone=phone, contact_address=addr, extra=extra)
            db.session.add(si)
        else:
            si.contact_email = email
            si.contact_phone = phone
            si.contact_address = addr
            si.extra = extra
        db.session.commit()
        flash('Site iletişim bilgileri güncellendi', 'success')
        return redirect(url_for('contact'))

    site_info = si.to_dict() if si else None
    return render_template('admin_siteinfo.html', site_info=site_info)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(THUMB_FOLDER, filename)


if __name__ == '__main__':
    # For development: ensure database tables exist then run
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
    app.run(debug=True, host='127.0.0.1', port=5000)

