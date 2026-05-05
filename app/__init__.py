from flask import Flask
from .config import Config
from .extensions import db, migrate

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    # Initialize Flask extensions here
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints here
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
