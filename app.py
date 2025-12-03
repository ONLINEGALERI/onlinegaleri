from flask import Flask, render_template
from extensions import db, migrate, login_manager
from config import Config

# Blueprints
from blueprints.auth.routes import auth_bp
from blueprints.main.routes import main_bp
from blueprints.photo.routes import photo_bp
from blueprints.user.routes import user_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Extensions init
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(photo_bp, url_prefix="/photo")
    app.register_blueprint(user_bp, url_prefix="/user")

    # Default route
    @app.route("/")
    def index():
        return render_template("index.html")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

