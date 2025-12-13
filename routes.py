from flask import render_template, redirect, url_for, request, flash
from app import app
from flask_login import current_user, login_required

@app.route('/')
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/about')
def about():
    return render_template('about.html', current_user=current_user)

@app.route('/login')
def login():
    return "Login sayfası burada olacak"

@app.route('/logout')
@login_required
def logout():
    return "Çıkış yapıldı"
