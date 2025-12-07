from extensions import db


class SiteInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_email = db.Column(db.String(200), nullable=True)
    contact_phone = db.Column(db.String(100), nullable=True)
    contact_address = db.Column(db.String(400), nullable=True)
    extra = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'contact_address': self.contact_address,
            'extra': self.extra
        }
