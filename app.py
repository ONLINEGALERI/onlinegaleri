from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html")

@app.route("/upload")
def upload():
    return render_template("upload.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)


# Dosya uzantısını kontrol et
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Galeri sayfası
@app.route('/')
@app.route('/gallery')
def gallery():
    images = os.listdir(THUMB_FOLDER)
    return render_template('gallery.html', images=images)

# Fotoğraf yükleme
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            # Küçük resim (thumbnail) oluştur
            img = Image.open(filepath)
            img.thumbnail((200, 200))
            img.save(os.path.join(THUMB_FOLDER, filename))
            return redirect(url_for('gallery'))
    return render_template('upload.html')

# İletişim formu
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        # Burada mesajı kaydedebilir veya mail gönderebilirsin
        print(f"Yeni mesaj: {name} - {email} - {message}")
        return redirect(url_for('gallery'))
    return render_template('contact.html')

# Thumbnail ve orijinal resimleri sunmak
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/thumbs/<filename>')
def thumb_file(filename):
    return send_from_directory(THUMB_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True)

