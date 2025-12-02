import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime

# ----------------------------------
# Temel ayarlar
# ----------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
THUMB_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbs')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'dev-secret'

# ----------------------------------
# Yardımcı fonksiyon
# ----------------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------------------
# Anasayfa
# ----------------------------------
@app.route('/')
def home():
    images = [f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f)]
    images.sort(reverse=True)
    current_year = datetime.now().year
    return render_template('index.html', images=images, current_year=current_year)

# ----------------------------------
# Fotoğraf yükleme
# ----------------------------------
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Dosya seçilmedi')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Dosya seçilmedi')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            # Thumbnail oluştur
            thumb_path = os.path.join(THUMB_FOLDER, filename)
            try:
                img = Image.open(filepath)
                img.thumbnail((300, 300))
                img.save(thumb_path)
            except Exception:
                app.logger.exception('Thumbnail oluşturulamadı: %s', filename)

            return redirect(url_for('gallery'))
        flash('Geçersiz dosya türü')
        return redirect(request.url)
    return render_template('upload.html')

# ----------------------------------
# Galeri
# ----------------------------------
@app.route('/gallery')
def gallery():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f) and f != 'thumbs']
    files.sort(reverse=True)
    return render_template('gallery.html', files=files)

# ----------------------------------
# Tek fotoğraf gösterimi
# ----------------------------------
@app.route('/photo/<filename>')
def photo(filename):
    return render_template('photo.html', name=filename)

# ----------------------------------
# Fotoğraf ve thumbnail servisleri
# ----------------------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/thumbs/<filename>')
def thumbnail(filename):
    return send_from_directory(THUMB_FOLDER, filename)

# ----------------------------------
# Uygulamayı başlat
# ----------------------------------
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # Render uyumlu port
    app.run(host='0.0.0.0', port=port, debug=True)

