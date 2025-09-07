from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from models import Empleado, db

convenios_bp = Blueprint("convenios", __name__, url_prefix="/convenios")


# /convenios/  -> Lista de EMPLEADOS (index del módulo)
@convenios_bp.get("/", endpoint="index")
@convenios_bp.get("") 
@login_required
def empleados_index():
    empleados = Empleado.query.order_by(Empleado.nombre).all()
    return render_template("index.html", empleados=empleados)


# /convenios/lista  -> Lista de CONVENIOS (otra vista diferente)
@convenios_bp.get("/lista", endpoint="list")
@login_required
def convenios_list():
    convenios = []  # TODO: trae tus convenios reales
    return render_template("convenios_list.html", convenios=convenios)


# ✅ ALIAS para compatibilidad con las plantillas antiguas
@convenios_bp.get("/empleados", endpoint="list_employees")
@login_required
def list_employees_alias():
    return empleados_index()

# /convenios/nuevo  -> Alta de empleado
@convenios_bp.route("/nuevo", methods=["GET", "POST"], endpoint="new_employee")
@login_required
def new_employee():
    if request.method == "POST":
        dni = (request.form.get("dni") or "").strip()
        nombre = (request.form.get("nombre") or "").strip()
        if not dni or not nombre:
            flash("DNI y Nombre son obligatorios.", "warning")
            return render_template("new_employee.html")
        if Empleado.query.filter_by(dni=dni).first():
            flash(f"Ya existe un colaborador con DNI {dni}.", "warning")
            return render_template("new_employee.html")
        emp = Empleado(
            dni=dni,
            nombre=nombre,
            cargo=(request.form.get("cargo") or "").strip() or None,
            direccion=(request.form.get("direccion") or "").strip() or None,
        )
        # fecha_ingreso opcional
        fecha_raw = (request.form.get("fecha_ingreso") or "").strip()
        if fecha_raw:
            try:
                y, m, d = [int(x) for x in fecha_raw.split("-")]
                from datetime import date as _date

                emp.fecha_ingreso = _date(y, m, d)
            except Exception:
                flash("La fecha de ingreso no es válida (aaaa-mm-dd).", "warning")
        db.session.add(emp)
        db.session.commit()
        flash("Colaborador creado correctamente.", "success")
        return redirect(url_for("convenios.index"))  # vuelve a la lista de EMPLEADOS
    return render_template("new_employee.html")


# /convenios/empleados/<id>  -> Detalle de empleado
@convenios_bp.get("/empleados/<int:empleado_id>", endpoint="view_employee")
@login_required
def view_employee(empleado_id):
    emp = Empleado.query.get_or_404(empleado_id)
    return render_template("empleado.html", empleado=emp)
