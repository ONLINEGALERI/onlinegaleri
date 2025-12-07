import os
import time
import uuid
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, url_for, redirect, flash

# Try to import flask-login's current_user; if not available, use a dummy
try:
    from flask_login import current_user
except Exception:
    class _Anon:
        is_authenticated = False

    current_user = _Anon()

app = Flask(__name__)
app.config.setdefault('SECRET_KEY', 'dev')
# Upload settings
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
app.config.setdefault('MAX_CONTENT_LENGTH', 8 * 1024 * 1024)  # 8 MB

# ensure upload directories exist under static/uploads
STATIC_UPLOADS = os.path.join(app.static_folder, 'uploads')
THUMBS_DIR = os.path.join(STATIC_UPLOADS, 'thumbs')
os.makedirs(STATIC_UPLOADS, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)


def _fallback_photos_for(username=None):
    # Adjust the filenames below to match your static uploads folder.
    return [
        {'id': 1, 'url': url_for('static', filename='uploads/sample1.svg'), 'title': f'{username or "Public"} - 1', 'description': ''},
        {'id': 2, 'url': url_for('static', filename='uploads/sample2.svg'), 'title': f'{username or "Public"} - 2', 'description': ''},
        {'id': 3, 'url': url_for('static', filename='uploads/sample3.svg'), 'title': f'{username or "Public"} - 3', 'description': ''},
        {'id': 4, 'url': url_for('static', filename='uploads/sample4.svg'), 'title': f'{username or "Public"} - 4', 'description': ''},
        {'id': 5, 'url': url_for('static', filename='uploads/sample5.svg'), 'title': f'{username or "Public"} - 5', 'description': ''},
        {'id': 6, 'url': url_for('static', filename='uploads/sample6.svg'), 'title': f'{username or "Public"} - 6', 'description': ''},
    ]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _scan_uploaded_photos():
    """Return list of uploaded photo dicts sorted by mtime desc.
    Each dict: id, url, title, description, likes
    """
    files = []
    try:
        for fn in os.listdir(STATIC_UPLOADS):
            if fn == 'thumbs':
                continue
            if not allowed_file(fn):
                continue
            path = os.path.join(STATIC_UPLOADS, fn)
            if not os.path.isfile(path):
                continue
            mtime = os.path.getmtime(path)
            files.append((mtime, fn))
        files.sort(reverse=True)
        out = []
        idx = 1
        for mtime, fn in files:
            out.append({
                'id': int(mtime),
                'url': url_for('static', filename=f'uploads/{fn}'),
                'title': fn,
                'description': '',
                'likes': 0,
            })
            idx += 1
        return out
    except Exception:
        return []


@app.route('/')
def index():
    # Render homepage and include gallery preview (trending / explore)
    try:
        # Prefer a dedicated trending function if available in the project
        try:
            trending = get_trending_photos()
        except Exception:
            all_photos = get_all_photos()
            # simple heuristic: reverse recent order or take top-N
            trending = list(reversed(all_photos)) if all_photos else _fallback_photos_for()
    except Exception:
        trending = _fallback_photos_for()

    # Keep limit for profile-preview logic elsewhere; homepage uses trending_photos
    return render_template('index.html', trending_photos=trending, limit=6, current_user=current_user)


@app.route('/gallery')
def gallery():
    try:
        photos = get_all_photos()
    except Exception:
        photos = _fallback_photos_for()
    return render_template('gallery.html', photos=photos, limit=6, current_user=current_user)


@app.route('/user/<username>')
def user_gallery(username):
    try:
        photos = get_photos_for_user(username) or []
    except Exception:
        photos = _fallback_photos_for(username)
    return render_template('gallery.html', photos=photos, limit=6, current_user=current_user)


@app.route('/save_photo', methods=['POST'])
def save_photo():
    data = request.get_json(silent=True) or {}
    photo_id = data.get('photo_id')
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'message': 'Giriş gerekli'}), 401
    # TODO: implement save logic
    return jsonify({'message': f'Fotoğraf {photo_id} kaydedildi.'})


@app.route('/repost', methods=['POST'])
def repost():
    data = request.get_json(silent=True) or {}
    photo_id = data.get('photo_id')
    if not getattr(current_user, 'is_authenticated', False):
        return jsonify({'message': 'Giriş gerekli'}), 401
    # TODO: implement repost logic
    return jsonify({'message': f'Fotoğraf {photo_id} tekrar paylaşıldı.'})


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'GET':
        try:
            return render_template('upload.html')
        except Exception:
            return "Upload page not found", 404

    # POST - handle file upload
    # fields: file (required), title (optional), description (optional)
    # accept both 'file' and 'photo' form field names (templates differ)
    file = request.files.get('file') or request.files.get('photo')
    title = request.form.get('title') or ''
    description = request.form.get('description') or ''
    if not file or file.filename == '':
        flash('Lütfen bir dosya seçin.')
        return redirect(request.url)
    if not allowed_file(file.filename):
        flash('Bu dosya türüne izin verilmiyor.')
        return redirect(request.url)

    filename = secure_filename(file.filename)
    # avoid collisions
    name, ext = os.path.splitext(filename)
    suffix = uuid.uuid4().hex[:8]
    filename = f"{name}-{suffix}{ext}"
    save_path = os.path.join(STATIC_UPLOADS, filename)
    try:
        file.save(save_path)
    except Exception as e:
        flash('Dosya kaydedilemedi.')
        return redirect(request.url)

    # Optionally create a thumbnail if Pillow is available
    try:
        from PIL import Image
        im = Image.open(save_path)
        im.thumbnail((400, 400))
        thumb_path = os.path.join(THUMBS_DIR, filename)
        im.save(thumb_path)
    except Exception:
        # pillow not installed or error - ignore thumb creation
        pass

    flash('Yükleme başarılı. Fotoğraf galeride görünecektir.')
    return redirect(url_for('gallery'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    try:
        return render_template('contact.html')
    except Exception:
        return "Contact page not found", 404


@app.route('/api/trending')
def api_trending():
    # params: page (1-based), per_page
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    try:
        per_page = int(request.args.get('per_page', 15))
    except Exception:
        per_page = 15

    # Build a larger list by repeating fallback photos if real data not available
    try:
        all_photos = get_trending_photos()  # if exists
    except Exception:
        try:
            all_photos = get_all_photos()
        except Exception:
            base = _fallback_photos_for()
            # create 60 mock items by cycling base
            all_photos = []
            for i in range(60):
                b = base[i % len(base)]
                all_photos.append({
                    'id': i + 1,
                    'url': b['url'],
                    'title': f"{b['title']} #{i+1}",
                    'description': b.get('description',''),
                    'likes': (i * 7) % 123  # mock like counts
                })

    # if there are real uploaded files, surface them first
    try:
        uploaded = _scan_uploaded_photos()
        if uploaded:
            # combine uploaded (most recent first) with existing list but avoid exact url duplicates
            existing_urls = {p.get('url') for p in all_photos}
            merged = []
            for u in uploaded:
                if u.get('url') not in existing_urls:
                    merged.append(u)
            all_photos = merged + all_photos
    except Exception:
        pass

    total = len(all_photos)
    start = (page - 1) * per_page
    end = start + per_page
    items = all_photos[start:end]
    return jsonify({'page': page, 'per_page': per_page, 'total': total, 'items': items})


if __name__ == '__main__':
    app.run(debug=True)


