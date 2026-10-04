from flask import Flask

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = "hl7-validator-lite"

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
