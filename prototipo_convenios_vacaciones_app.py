import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import LoginManager, login_required

# Blueprints
from auth import auth_bp
from convenios import convenios_bp  # <- ahora el paquete convenios expone el BP
from prestamos import prestamos_bp

# Modelos y utils
from models import db, User
from utils import (
    normalize_db_url,
    fecha_literal,
    fecha_firma_literal,
    numero_a_letras,
)

# =========================================================
# APP GLOBAL
# =========================================================
app = Flask(__name__)

# Helpers Jinja globales
app.jinja_env.globals.update(
    fecha_literal=fecha_literal,
    fecha_firma_literal=fecha_firma_literal,
    numero_a_letras=numero_a_letras,
)


def _seed_admin_if_empty():
    """Crea un admin inicial si la tabla 'users' está vacía (usa username)."""
    if User.query.count() == 0:
        username = os.getenv("ADMIN_USERNAME", "admin")
        pwd = os.getenv("ADMIN_PASSWORD", "Admin$1234")
        admin = User(username=username, is_active=True)
        admin.set_password(pwd)
        db.session.add(admin)
        db.session.commit()
        print(f"[SEED] Usuario administrador creado: {username}")


# =========================================================
# FACTORY
# =========================================================
def create_app():
    load_dotenv()

    if app.config.get("_INIT_DONE"):
        return app

    # ---------- Config ----------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    raw_url = os.getenv("DATABASE_URL", "sqlite:///database.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_db_url(raw_url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ---------- Remember cookie ----------
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(
        days=int(os.getenv("REMEMBER_DAYS", 30))
    )
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    # En producción con HTTPS:
    # app.config["REMEMBER_COOKIE_SECURE"] = True

    # ---------- DB ----------
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _seed_admin_if_empty()

    # ---------- Login ----------
    login_manager = LoginManager()
    login_manager.login_view = "auth.login_get"
    login_manager.login_message = "Debes iniciar sesión para acceder."
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # ---------- Blueprints ----------
    app.register_blueprint(auth_bp, url_prefix="/")
    app.register_blueprint(convenios_bp)  # /convenios/...
    app.register_blueprint(prestamos_bp)

    # ---------- Rutas base ----------
    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    @app.get("/", endpoint="home")
    @login_required
    def home():
        return render_template("home.html")

    @app.get("/__routes")
    def __routes():
        lines = []
        for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
            methods = ",".join(
                sorted(m for m in r.methods if m in {"GET", "POST", "PUT", "DELETE"})
            )
            lines.append(f"{r.rule:40s}  =>  {r.endpoint}  [{methods}]")
        return "<pre>" + "\n".join(lines) + "</pre>"

    app.config["_INIT_DONE"] = True
    return app


if __name__ == "__main__":
    create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=True,
        use_reloader=False,
    )
