from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 🤝 TAKİP SİSTEMİ İLİŞKİ TABLOSU
# Üyelerin birbirini takip edebilmesi için gerekli ara tablo
followers_table = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # 🔐 ADMIN YETKİSİ
    is_admin = db.Column(db.Boolean, default=False)

    # Profile fields (Senin orijinal alanların - HİÇ DOKUNULMADI)
    avatar = db.Column(db.String(400), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    followers = db.Column(db.Integer, default=0)
    following = db.Column(db.Integer, default=0)
    posts = db.Column(db.Integer, default=0)

    # 📈 TAKİP İLİŞKİLERİ (Dinamik sayım için)
    followed = db.relationship(
        'User', secondary=followers_table,
        primaryjoin=(followers_table.c.follower_id == id),
        secondaryjoin=(followers_table.c.followed_id == id),
        backref=db.backref('followers_list', lazy='dynamic'), lazy='dynamic'
    )

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password, method='pbkdf2:sha256')

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    # Takip etme yardımcı fonksiyonları
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers_table.c.followed_id == user.id).count() > 0

# 💬 YORUM MODELİ (app.py artık bu sınıfı bulabilecek)
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'))

# ❤️ BEĞENİ MODELİ (app.py artık bu sınıfı bulabilecek)
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'))