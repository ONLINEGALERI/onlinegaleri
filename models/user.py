from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# association table for follower relationships
followers_table = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Profile fields
    avatar = db.Column(db.String(400), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    followers = db.Column(db.Integer, default=0)
    following = db.Column(db.Integer, default=0)
    posts = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)

    # relationship helpers (do not override integer counters)
    following_rel = db.relationship(
        'User', secondary=followers_table,
        primaryjoin=(followers_table.c.follower_id == id),
        secondaryjoin=(followers_table.c.followed_id == id),
        backref=db.backref('followers_rel', lazy='dynamic'),
        lazy='dynamic')

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    # follow management
    def follow(self, user):
        if not self.is_following(user) and user.id != self.id:
            self.following_rel.append(user)
            # update integer counters for quick display
            try:
                self.following = (self.following or 0) + 1
            except Exception:
                pass
            try:
                user.followers = (user.followers or 0) + 1
            except Exception:
                pass

    def unfollow(self, user):
        if self.is_following(user) and user.id != self.id:
            self.following_rel.remove(user)
            try:
                self.following = max(0, (self.following or 0) - 1)
            except Exception:
                pass
            try:
                user.followers = max(0, (user.followers or 0) - 1)
            except Exception:
                pass

    def is_following(self, user):
        if not user:
            return False
        return self.following_rel.filter(followers_table.c.followed_id == user.id).count() > 0
