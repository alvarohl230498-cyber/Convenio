from flask import Blueprint

# El paquete expone el blueprint
convenios_bp = Blueprint(
    "convenios",
    __name__,
    url_prefix="/convenios"
)

# Importa las rutas para que se registren en el BP
from . import routes  # noqa: E402,F401