<<<<<<< HEAD
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
    files = []
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        if name == 'thumbs':
            continue
        if allowed_file(name):
            files.append(name)
    files.sort(reverse=True)
    current_year = datetime.now().year
    return render_template('index.html', images=files, current_year=current_year)

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
            destination = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(destination)

            # Thumbnail oluştur
            thumb_path = os.path.join(THUMB_FOLDER, filename)
            try:
                img = Image.open(destination)
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
    files = []
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        if name == 'thumbs':
            continue
        if allowed_file(name):
            files.append(name)
    files.sort(reverse=True)
    return render_template('gallery.html', files=files)

# ----------------------------------
# Fotoğraf gösterimi
# ----------------------------------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/thumbs/<path:filename>')
def thumbnail(filename):
    return send_from_directory(THUMB_FOLDER, filename)

@app.route('/photo/<path:filename>')
def photo(filename):
    return render_template('photo.html', name=filename)

# ----------------------------------
# Uygulamayı başlat
# ----------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)

=======
from flask import Flask, render_template
from extensions import db, migrate, login_manager
from config import Config

# Blueprints
from blueprints.auth.routes import auth_bp
from blueprints.main.routes import main_bp
from blueprints.photo.routes import photo_bp
from blueprints.user.routes import user_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Extensions init
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(photo_bp, url_prefix="/photo")
    app.register_blueprint(user_bp, url_prefix="/user")

    # Default route
    @app.route("/")
    def index():
        return render_template("index.html")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

>>>>>>> beril
