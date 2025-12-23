from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 🤝 TAKİP SİSTEMİ İLİŞKİ TABLOSU (İsmini karışıklık olmasın diye değiştirdim)
followers_association = db.Table('followers_assoc',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)

    avatar = db.Column(db.String(400), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Not: followers ve following kolonlarını sildim çünkü bunları dinamik olarak 
    # db.relationship üzerinden sayacağız. Bu, 500 hatasını önleyen en kritik adımdır. ✨

    followed = db.relationship(
        'User', secondary=followers_association,
        primaryjoin=(followers_association.c.follower_id == id),
        secondaryjoin=(followers_association.c.followed_id == id),
        backref=db.backref('followers_list', lazy='dynamic'), lazy='dynamic'
    )

    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic', foreign_keys='Notification.user_id')

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password, method='pbkdf2:sha256')

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers_association.c.followed_id == user.id).count() > 0

# 💬 YORUM MODELİ
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'))

# ❤️ BEĞENİ MODELİ
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'))

# ✨ ASİL BİLDİRİM MODELİ ✨
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_username = db.Column(db.String(50), nullable=False)
    notif_type = db.Column(db.String(20), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)