from flask import Blueprint


prestamos_bp = Blueprint(
    "prestamos", __name__, template_folder="templates", static_folder="static"
)


# Al importar rutas aquí, se registran los endpoints
from . import routes # noqa: E402,F401