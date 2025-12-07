from extensions import db
from datetime import datetime

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.Text, nullable=True)
    archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('posts_rel', lazy='dynamic'))

    def to_dict(self, base_url='/'):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'url': f"{base_url}uploads/thumbs/{self.filename}",
            'caption': self.caption,
            'archived': bool(self.archived),
            'created_at': self.created_at.isoformat()
        }
