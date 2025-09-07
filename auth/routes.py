# auth/routes.py
from flask import request, render_template, redirect, url_for, flash,current_app
from urllib.parse import urlparse, urljoin
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from datetime import timedelta
from models import db, User


@auth_bp.get("/login")
def login_get():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return render_template("auth/login.html")


def _safe_redirect(target: str | None, default_endpoint: str = "home"):
    """Redirige solo a URLs locales válidas; evita open-redirects."""
    if not target:
        return redirect(url_for(default_endpoint))
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    same_host = ref_url.netloc == test_url.netloc
    if test_url.scheme in ("http", "https") and same_host:
        return redirect(test_url.geturl())
    return redirect(url_for(default_endpoint))


@auth_bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    remember = bool(request.form.get("remember"))  # respeta el checkbox

    # Validación mínima
    if not username or not password:
        flash("Ingrese usuario y contraseña.", "warning")
        return redirect(url_for("auth.login_get"))

    # Búsqueda case-insensitive
    user = User.query.filter(User.username.ilike(username)).first()

    # Autenticación
    if not user or not user.is_active or not user.check_password(password):
        current_app.logger.info("Login fallido para usuario=%r", username)
        flash("Usuario o contraseña incorrectos.", "warning")
        return redirect(url_for("auth.login_get"))

    # Duración del 'remember me' (configurable)
    duration = current_app.config.get("REMEMBER_COOKIE_DURATION", timedelta(days=30))

    # Inicia sesión
    login_user(user, remember=remember, duration=duration, fresh=True)

    # Redirección segura
    next_url = request.args.get("next")
    return _safe_redirect(next_url, default_endpoint="home")


@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_get"))
