def register_routes(app):
    from app.routes.auth import auth_bp
    from app.routes.data import data_bp
    from app.routes.ui import ui_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(ui_bp)