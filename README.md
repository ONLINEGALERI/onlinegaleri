# Online Galeri (Basit Flask örneği) http://127.0.0.1:5000/

Bu proje, basit bir çevrimiçi galeri gösterimi için Flask tabanlı örnek uygulamadır. İçerik:

- `app.py` — Flask uygulaması ve route'lar
- `templates/` — Jinja2 şablonları (`base.html`, `index.html`, `contact.html`)
- `static/css/style.css` — temel stiller

Hızlı başlatma (Windows PowerShell):

# Online Galeri (Basit Flask örneği)

Bu proje, basit bir çevrimiçi galeri gösterimi için Flask tabanlı örnek uygulamadır.

İçerik:
- `app.py` — Flask uygulaması, rota ve basit kimlik doğrulama (kayıt/giriş)
- `templates/` — Jinja2 şablonları (`base.html`, `index.html`, `contact.html`, `login.html`, `register.html`, `dashboard.html`)
- `static/` — stil ve küçük JS (lightbox)
- `app.db` — SQLite veritabanı (kullanıcılar ve iletişim kayıtları)

Hızlı başlatma (Windows PowerShell):

```powershell
# (isteğe bağlı) sanal ortam oluşturun
python -m venv .venv; .\.venv\Scripts\Activate.ps1

# bağımlılıkları yükleyin
python -m pip install -r requirements.txt

# uygulamayı çalıştırın
python app.py
```

Tarayıcıyı açıp `http://127.0.0.1:5000/` adresine gidin.

Notlar:
- Demo görselleri placeholder olarak `picsum.photos` kullanıyor. Kendi resimleriniz varsa `app.py`'de veya şablonda güncelleyin.
- Artık iletişim formları ve kullanıcılar `app.db` (SQLite) içinde saklanır.

Kimlik doğrulama / profesyonel kullanıcılar:
- Kullanıcılar kayıt olup giriş yapabilirler. Kayıt sırasında "Profesyonel hesap" seçeneği işaretlenirse panel erişimi talep edilebilir.
- Üyelik/kimlik doğrulama basit örnek şeklindedir; prod için e-posta doğrulama ve güçlü parola politikası eklemelisiniz.

Prod / Deploy notları:
- `FLASK_SECRET` ortam değişkeni ayarlayın (prod için rastgele güçlü bir değer).
- Prod deploy yaparken `debug=True` kapatılmalı ve WSGI sunucusu (gunicorn veya waitress) kullanılmalıdır.

