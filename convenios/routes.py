# convenios/routes.py
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import Empleado, db

convenios_bp = Blueprint("convenios", __name__, url_prefix="/convenios")

# Index: redirige SIEMPRE al listado de empleados (tu UI principal)
@convenios_bp.get("/", endpoint="index")
@login_required
def index_convenios():
    return redirect(url_for("convenios.list_employees"))

# LISTA DE EMPLEADOS (el endpoint que usan tus HTML)
@convenios_bp.get("/empleados", endpoint="list_employees")
@login_required
def list_employees():
    empleados = Empleado.query.order_by(Empleado.nombre).all()
    # Tu tabla vive en templates/convenios_list.html y espera `empleados`
    return render_template("convenios_list.html", empleados=empleados, convenios=[])

# NUEVO EMPLEADO (GET/POST)
@convenios_bp.route("/nuevo", methods=["GET", "POST"], endpoint="new_employee")
@login_required
def new_employee():
    if request.method == "POST":
        dni = (request.form.get("dni") or "").strip()
        nombre = (request.form.get("nombre") or "").strip()
        cargo = (request.form.get("cargo") or "").strip() or None
        direccion = (request.form.get("direccion") or "").strip() or None
        fecha_raw = (request.form.get("fecha_ingreso") or "").strip() or None

        if not dni or not nombre:
            flash("DNI y Nombre son obligatorios.", "warning")
            return render_template("new_employee.html")

        if Empleado.query.filter_by(dni=dni).first():
            flash(f"Ya existe un colaborador con DNI {dni}.", "warning")
            return render_template("new_employee.html")

        emp = Empleado(dni=dni, nombre=nombre, cargo=cargo, direccion=direccion)

        if fecha_raw:
            try:
                y, m, d = [int(x) for x in fecha_raw.split("-")]
                emp.fecha_ingreso = date(y, m, d)
            except Exception:
                flash("La fecha de ingreso no tiene un formato válido (aaaa-mm-dd).", "warning")

        db.session.add(emp)
        db.session.commit()
        flash("Colaborador creado correctamente.", "success")
        # IMPORTANTE: redirige al endpoint que usa tu navbar/botón
        return redirect(url_for("convenios.list_employees"))

    return render_template("new_employee.html")

# DETALLE EMPLEADO (usado por botón Ver)
@convenios_bp.get("/empleados/<int:empleado_id>", endpoint="view_employee")
@login_required
def view_employee(empleado_id):
    empleado = Empleado.query.get_or_404(empleado_id)
    return render_template("empleado.html", empleado=empleado)
