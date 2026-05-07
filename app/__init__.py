import logging
from flask import Flask
from app.config import settings
from app.extensions import db, jwt, cors, limiter

def create_app():
    # Setup logging — semua logger.exception() dari routes akan muncul di console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Menentukan direktori templates dan static ke folder root
    import os
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app = Flask(__name__, 
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))
    
    # JWT Config
    app.config["JWT_SECRET_KEY"] = settings.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 900      # 15 menit
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 604800  # 7 hari
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config["JWT_COOKIE_SECURE"] = False           # True di production (HTTPS)
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False     # Matikan CSRF untuk MVP/dev
    
    # Init Extensions
    cors.init_app(app, origins=settings.CORS_ORIGINS)
    jwt.init_app(app)
    limiter.init_app(app)
    
    # Register Blueprints
    from app.routes import register_routes
    register_routes(app)

    # Pastikan MongoDB indexes terbuat saat startup
    with app.app_context():
        from app.routes.data import ensure_indexes
        ensure_indexes()
    
    # Health Check Route (minimal)
    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "inventory-finance-tracker"}, 200
    
    return app