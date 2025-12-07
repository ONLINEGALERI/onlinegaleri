from app import app, db
from sqlalchemy import inspect, text
from models.user import User

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    target = None
    for t in ['user', 'users']:
        if t in tables:
            target = t
            break

    if not target:
        print('No user table found, available:', tables)
    else:
        cols = [c['name'] for c in inspector.get_columns(target)]
        print('Columns in', target, cols)
        if 'is_admin' not in cols:
            try:
                db.session.execute(text(f"ALTER TABLE {target} ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
                db.session.commit()
                print('Added is_admin column')
            except Exception as e:
                print('Failed to add is_admin column:', e)

    username = 'Verzia'
    pw = 'bec123456'
    existing = User.query.filter_by(username=username).first()
    if existing:
        try:
            existing.is_admin = True
            db.session.commit()
            print('Existing user set as admin')
        except Exception as e:
            print('Error setting is_admin on existing user:', e)
    else:
        u = User(username=username, email=f'{username.lower()}@example.com')
        u.set_password(pw)
        u.is_admin = True
        db.session.add(u)
        db.session.commit()
        print('Created admin user', username)
