from extensions import db
from datetime import datetime

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    filename = db.Column(db.String(100), nullable=False)
    
    # ✨ AI kodlarını tamamen temizledik, stabiliteye döndük!
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('User', backref=db.backref('photos', lazy=True))

    # --- SADECE BU 2 SATIRI EKLEDİK (HATALARI KÖKTEN ÇÖZER) ---
    # Beğeni sayısının gözükmesi ve yorumların listelenmesi için gerekli bağlantılar:
    comments = db.relationship('Comment', backref='photo', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='photo', lazy=True, cascade="all, delete-orphan")