# convenios/__init__.py
from flask import Blueprint

# ÚNICO blueprint del módulo
convenios_bp = Blueprint("convenios", __name__, url_prefix="/convenios")

# Importa las rutas para que se registren sobre este blueprint
from . import routes  # noqa: E402,F401
