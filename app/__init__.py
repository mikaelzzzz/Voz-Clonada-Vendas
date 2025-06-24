from flask import Flask

def create_app():
    """
    Factory function para criar a aplicação Flask
    """
    app = Flask(__name__)
    
    # Importa e registra blueprints
    from app.routes.webhook_routes import webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    
    return app 