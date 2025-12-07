"""Automated test: create a post as admin and delete it via AJAX.
Run with: python scripts/test_admin_post_flow.py
"""
from io import BytesIO
from app import app
from extensions import db
from models.user import User
from models.post import Post
import os

ADMIN_USERNAME = 'Verzia'
ADMIN_PASSWORD = 'bec123456'


def ensure_admin(ctx):
    admin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if not admin:
        admin = User(username=ADMIN_USERNAME, email='verzia@example.local')
        admin.set_password(ADMIN_PASSWORD)
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
    else:
        # ensure is_admin True and password set (do NOT change existing password in real world)
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
    return admin


def run_test():
    with app.app_context():
        # Ensure DB tables exist
        db.create_all()
        admin = ensure_admin(app.app_context())

        # create a post directly in DB (no file needed)
        p = Post(user_id=admin.id, filename='test_auto_delete.jpg', caption='automated test post')
        db.session.add(p)
        db.session.commit()
        post_id = p.id
        print('Created post id=', post_id)

        # Verify post exists
        found = Post.query.get(post_id)
        if not found:
            print('ERROR: Post not found after creation')
            return 2

    # Use test client to login and delete via AJAX
    with app.test_client() as c:
        # login
        r = c.post('/login', data={'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD}, follow_redirects=True)
        print('Login status:', r.status_code)
        if r.status_code != 200:
            print('Login failed, abort')
            return 3
        # delete via AJAX
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        delr = c.post(f'/post/{post_id}/delete', headers=headers)
        print('Delete request status:', delr.status_code)
        try:
            j = delr.get_json()
        except Exception:
            j = None
        print('Delete response json:', j)

    # verify DB row removed
    with app.app_context():
        still = Post.query.get(post_id)
        if still:
            print('ERROR: Post still exists in DB after delete')
            return 4
        else:
            print('OK: Post removed from DB')
    return 0


if __name__ == '__main__':
    rc = run_test()
    print('EXIT', rc)
    # exit code
    import sys
    sys.exit(rc)
