from app import app, db, User, Photo  # app'i import et

with app.app_context():  # Flask uygulama context'i aç
    print("=== CRUD TESTİ BAŞLADI ===")

    # CREATE
    new_user = User(username='TestUser', email='testuser@example.com', password='1234')
    db.session.add(new_user)
    db.session.commit()
    print(f"Kullanıcı eklendi: {new_user.id} | {new_user.username} | {new_user.email}")

    # READ
    users = User.query.all()
    print("\n-- Kullanıcı Listesi --")
    for u in users:
        print(f"{u.id} | {u.username} | {u.email}")

    # UPDATE
    user_to_update = User.query.filter_by(username='TestUser').first()
    if user_to_update:
        user_to_update.email = 'updated@example.com'
        db.session.commit()
        print(f"Güncel email: {user_to_update.id} | {user_to_update.username} | {user_to_update.email}")

    # DELETE
    user_to_delete = User.query.filter_by(username='TestUser').first()
    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
        print(f"Kullanıcı silindi: {user_to_delete.username}")

    # SON LISTE
    users = User.query.all()
    print("\n-- Son Kullanıcı Listesi --")
    for u in users:
        print(f"{u.id} | {u.username} | {u.email}")

    print("\n=== CRUD TESTİ BİTTİ ===")


