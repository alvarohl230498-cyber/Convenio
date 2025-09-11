import io
from datetime import datetime, date, timedelta
from io import BytesIO

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    flash,
    abort,
    jsonify,
    Response,
)
from flask_login import login_required
from . import convenios_bp

from models import db, Empleado, PeriodoVacacional, MovimientoVacacional, Convenio
from utils import (
    fecha_literal,
    fecha_firma_literal,
    periodo_from_ingreso,
    verbo_por_bloque,
    sumar_dias,
    calcular_dias_truncos,
    validar_solicitud,
    partir_rango_por_bolsas,
)

# =============================
# Filtros y context processors
# =============================


@convenios_bp.app_template_filter("num_es")
def num_es(n):
    n = int(n or 0)
    mapa = {
        0: "cero",
        1: "uno",
        2: "dos",
        3: "tres",
        4: "cuatro",
        5: "cinco",
        6: "seis",
        7: "siete",
        8: "ocho",
        9: "nueve",
        10: "diez",
        11: "once",
        12: "doce",
        13: "trece",
        14: "catorce",
        15: "quince",
        16: "dieciséis",
        17: "diecisiete",
        18: "dieciocho",
        19: "diecinueve",
        20: "veinte",
        21: "veintiuno",
        22: "veintidós",
        23: "veintitrés",
        24: "veinticuatro",
        25: "veinticinco",
        26: "veintiséis",
        27: "veintisiete",
        28: "veintiocho",
        29: "veintinueve",
        30: "treinta",
        31: "treinta y uno",
        32: "treinta y dos",
        33: "treinta y tres",
        34: "treinta y cuatro",
        35: "treinta y cinco",
        36: "treinta y seis",
        37: "treinta y siete",
        38: "treinta y ocho",
        39: "treinta y nueve",
        40: "cuarenta",
        41: "cuarenta y uno",
        42: "cuarenta y dos",
        43: "cuarenta y tres",
        44: "cuarenta y cuatro",
        45: "cuarenta y cinco",
        46: "cuarenta y seis",
        47: "cuarenta y siete",
        48: "cuarenta y ocho",
        49: "cuarenta y nueve",
        50: "cincuenta",
        51: "cincuenta y uno",
        52: "cincuenta y dos",
        53: "cincuenta y tres",
        54: "cincuenta y cuatro",
        55: "cincuenta y cinco",
        56: "cincuenta y seis",
        57: "cincuenta y siete",
        58: "cincuenta y ocho",
        59: "cincuenta y nueve",
        60: "sesenta",
    }
    return mapa.get(n, str(n))


@convenios_bp.app_template_filter("fecha_pe")
def fecha_pe(value):
    """Devuelve dd/mm/aaaa. Soporta date, datetime o string ISO."""
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


@convenios_bp.app_context_processor
def inject_empresa():
    return {
        "empresa": {
            "razon_social": "CONTRANS S.A.C.",
            "ruc": "20392952455",
            "rep_nombre": "FRANCISCO JOSE GONZALEZ HURTADO",
            "rep_dni": "40106879",
            "direccion": "Avenida A N.° 204 – Ex Fundo Oquendo (Alt. Km 8.5 de Av. Néstor Gambetta – Callao)",
            "lugar_firma": "Lima",
        }
    }


# =============================
# Navegación / Listas
# =============================


# /convenios/  -> Lista de EMPLEADOS
@convenios_bp.get("", endpoint="index")
@convenios_bp.get("/", endpoint="index-slash")
@login_required
def convenios_index():
    # Orden seguro (usa la primera columna disponible)
    order_col = None
    for candidate in ("fecha_solicitud", "created_at", "id"):
        order_col = getattr(Convenio, candidate, None)
        if order_col is not None:
            break
    convenios = (
        Convenio.query.order_by(order_col.desc()).all()
        if order_col
        else Convenio.query.all()
    )
    return render_template("convenios_list.html", convenios=convenios)


# (Opcional) soporte legacy si alguien entra a /convenios/lista -> redirige a /convenios
@convenios_bp.get("/lista", endpoint="list_legacy")
@login_required
def convenios_list_legacy():
    return redirect(url_for("convenios.index"))


# =========================================================
# 2) /convenios/empleados  -> LISTA DE EMPLEADOS
# =========================================================
@convenios_bp.get("/empleados", endpoint="employees")
@convenios_bp.get("/empleados/", endpoint="employees-slash")
@login_required
def empleados_index():
    empleados = Empleado.query.order_by(Empleado.nombre).all()
    return render_template("index.html", empleados=empleados)

# Alias de compatibilidad (por si alguna plantilla antigua lo usa)
@convenios_bp.get("/empleados/list", endpoint="list_employees")
@login_required
def list_employees_alias():
    return redirect(url_for("convenios.employees"))


# =============================
# CRUD Empleado (en BP)
# =============================


# Alta empleado
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
        return redirect(url_for("convenios.index"))
    return render_template("new_employee.html")


# Ver empleado
@convenios_bp.get("/empleados/<int:empleado_id>", endpoint="view_employee")
@login_required
def view_employee(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    periodos = sorted(
        e.periodos, key=lambda x: (x.fecha_inicio or date.min), reverse=True
    )
    movimientos = (
        MovimientoVacacional.query.filter_by(id_empleado=empleado_id)
        .order_by(MovimientoVacacional.fecha.desc())
        .all()
    )
    return render_template(
        "empleado.html", empleado=e, periodos=periodos, movimientos=movimientos
    )


# Eliminar empleado
@convenios_bp.post("/employee/<int:empleado_id>/delete", endpoint="delete_employee")
@login_required
def delete_employee(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    db.session.delete(e)
    db.session.commit()
    flash("Colaborador eliminado correctamente.")
    return redirect(url_for("convenios.index"))


# =============================
# Periodos y Movimientos
# =============================


# Editar periodo
@convenios_bp.post("/period/<int:periodo_id>/edit", endpoint="edit_period")
@login_required
def edit_period(periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    p.periodo = request.form["periodo"].strip()
    p.fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d").date()
    p.fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d").date()
    p.dias_periodo = int(request.form.get("dias_periodo", 30))
    p.dias_tomados = int(request.form.get("dias_tomados", 0))
    p.dias_pendientes = int(request.form.get("dias_pendientes", 0))
    p.dias_truncos = int(request.form.get("dias_truncos", 0))
    db.session.commit()
    flash("Periodo vacacional actualizado correctamente.")
    return redirect(url_for("convenios.view_employee", empleado_id=p.id_empleado))


# Alta de periodo
@convenios_bp.post("/employee/<int:empleado_id>/period/new", endpoint="new_period")
@login_required
def new_period(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    periodo = request.form["periodo"].strip()  # "2024-2025"
    dias = int(request.form.get("dias_periodo", 30))

    try:
        anio_inicio, anio_fin = map(int, periodo.split("-"))
    except ValueError:
        flash("Formato de periodo inválido. Debe ser AAAA-AAAA.")
        return redirect(url_for("convenios.view_employee", empleado_id=e.id))

    fecha_inicio = e.fecha_ingreso.replace(year=anio_inicio)
    fecha_fin = fecha_inicio.replace(year=anio_fin) - timedelta(days=1)

    p = PeriodoVacacional(
        id_empleado=e.id,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        dias_periodo=dias,
        dias_tomados=0,
        dias_pendientes=0,
        dias_truncos=0,
    )

    db.session.add(p)
    db.session.flush()

    # Calcula truncos/pendientes al crear
    hoy = date.today()
    dias_ganados = calcular_dias_truncos(e.fecha_ingreso, hoy, fecha_inicio, fecha_fin)
    if dias_ganados >= dias:
        p.dias_pendientes = dias
        p.dias_truncos = 0
    else:
        p.dias_pendientes = 0
        p.dias_truncos = dias_ganados

    # Movimiento ALTA
    mov_alta = MovimientoVacacional(
        id_empleado=e.id,
        id_periodo=p.id,
        tipo=periodo,
        fecha=date.today(),
        dias=dias,
        saldo_resultante=p.dias_pendientes,
    )
    db.session.add(mov_alta)

    db.session.commit()
    flash("Periodo vacacional agregado y movimiento ALTA registrado.")
    return redirect(url_for("convenios.view_employee", empleado_id=e.id))


# Eliminar Periodo
@convenios_bp.post("/period/<int:periodo_id>/delete", endpoint="delete_period")
@login_required
def delete_period(periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    empleado_id = p.id_empleado
    db.session.delete(p)
    db.session.commit()
    flash("Periodo vacacional eliminado correctamente.")
    return redirect(url_for("convenios.view_employee", empleado_id=empleado_id))


# Ajuste manual de saldo del periodo
@convenios_bp.post(
    "/employee/<int:empleado_id>/period/<int:periodo_id>/ajuste",
    endpoint="ajustar_periodo",
)
@login_required
def ajustar_periodo(empleado_id, periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    e = Empleado.query.get_or_404(empleado_id)
    delta = int(request.form.get("delta_dias", 0))  # puede ser negativo
    p.dias_pendientes = max(0, (p.dias_pendientes or 0) + delta)
    if delta < 0:
        p.dias_tomados = (p.dias_tomados or 0) + abs(delta)
    mov = MovimientoVacacional(
        id_empleado=e.id,
        id_periodo=p.id,
        tipo="AJUSTE",
        fecha=date.today(),
        dias=delta,
    )
    db.session.add(mov)
    db.session.commit()
    flash("Ajuste aplicado.")
    return redirect(url_for("convenios.view_employee", empleado_id=e.id))


# Eliminar movimiento
@convenios_bp.post("/movimiento/<int:id>/delete", endpoint="delete_movimiento")
@login_required
def delete_movimiento(id):
    mov = MovimientoVacacional.query.get_or_404(id)
    periodo = PeriodoVacacional.query.get(mov.id_periodo)

    db.session.delete(mov)
    db.session.commit()

    if periodo:
        movimientos_restantes = MovimientoVacacional.query.filter_by(
            id_periodo=periodo.id
        ).all()

        dias_tomados = 0
        dias_pendientes = periodo.dias_periodo
        dias_truncos = 0

        for m in movimientos_restantes:
            if m.tipo in ("GOCE", "SOLICITUD_VACACIONES"):
                dias_tomados += abs(m.dias)
                dias_pendientes -= abs(m.dias)
            elif m.tipo == "AJUSTE":
                dias_pendientes += m.dias
            elif m.tipo == "TRUNCO":
                dias_truncos += abs(m.dias)
            elif m.tipo.startswith("Periodo vacacional"):
                dias_pendientes = m.dias  # Resetea a días iniciales del periodo

        periodo.dias_tomados = max(dias_tomados, 0)
        periodo.dias_pendientes = max(dias_pendientes, 0)
        periodo.dias_truncos = max(dias_truncos, 0)
        db.session.commit()

    flash("Movimiento eliminado y totales recalculados correctamente.")
    return redirect(url_for("convenios.view_employee", empleado_id=mov.id_empleado))


# Editar movimiento
@convenios_bp.post("/movimiento/<int:id>/edit", endpoint="edit_movimiento")
@login_required
def edit_movimiento(id):
    mov = MovimientoVacacional.query.get_or_404(id)
    inicio = request.form.get("fecha_inicio")
    fin = request.form.get("fecha_fin")
    if inicio:
        mov.fecha_inicio = datetime.strptime(inicio, "%Y-%m-%d").date()
    if fin:
        mov.fecha_fin = datetime.strptime(fin, "%Y-%m-%d").date()
    db.session.commit()
    flash("Movimiento actualizado correctamente.")
    return redirect(url_for("convenios.view_employee", empleado_id=mov.id_empleado))


# =============================
# JSON utilitario (datos para convenio)
# =============================


@convenios_bp.get(
    "/empleado/<int:empleado_id>/convenio/acumulacion/datos", endpoint="convenio_datos"
)
@login_required
def convenio_datos(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    p1_str, p1_inicio, p1_fin = periodo_from_ingreso(e.fecha_ingreso, 1)
    p2_str, p2_inicio, p2_fin = periodo_from_ingreso(e.fecha_ingreso, 2)
    return jsonify(
        {
            "empleado": {
                "id": e.id,
                "nombre": f"{e.nombre}",
                "dni": e.dni,
                "cargo": e.cargo,
                "direccion": e.direccion,
            },
            "periodos": {
                "p1": {
                    "periodo": p1_str,
                    "inicio": p1_inicio.isoformat(),
                    "fin": p1_fin.isoformat(),
                },
                "p2": {
                    "periodo": p2_str,
                    "inicio": p2_inicio.isoformat(),
                    "fin": p2_fin.isoformat(),
                },
            },
        }
    )


# =============================
# Solicitud de Vacaciones (con lógica de Convenio)
# =============================


@convenios_bp.post(
    "/employee/<int:empleado_id>/vacaciones/solicitar", endpoint="solicitar_vacaciones"
)
@login_required
def solicitar_vacaciones(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    inicio = datetime.strptime(request.form["inicio"], "%Y-%m-%d").date()
    fin = datetime.strptime(request.form["fin"], "%Y-%m-%d").date()
    obs = request.form.get("obs", "")
    confirmar = request.form.get("confirmar", "no")

    periodo_id = int(request.form["periodo_id"])
    periodo = PeriodoVacacional.query.get_or_404(periodo_id)

    dias = (fin - inicio).days + 1

    # Validación con periodo forzado (seleccionado)
    decision = validar_solicitud(e, inicio, fin, periodo_forzado=periodo)

    # Caso: requiere convenio y no se confirmó
    if decision["require_convenio"] and confirmar != "si":
        return render_template(
            "empleado.html",
            empleado=e,
            periodos=sorted(
                e.periodos, key=lambda x: (x.fecha_inicio or date.min), reverse=True
            ),
            movimientos=(
                MovimientoVacacional.query.filter_by(id_empleado=e.id)
                .order_by(MovimientoVacacional.fecha.desc())
                .all()
            ),
            require_convenio=True,
            motivo_convenio=decision["motivo"],
            fecha_inicio=inicio,
            fecha_fin=fin,
            obs=obs,
        )

    # Caso CONVENIO confirmado → bolsas P1 y P2 + fechas que “viajan”
    if decision["require_convenio"] and confirmar == "si":
        p1_db = decision.get("periodo_base")  # P1
        p2_db = decision.get("periodo_acumulado")  # P2 (puede ser None)

        p1_pend = max(0, p1_db.dias_pendientes or 0) if p1_db else 0
        p2_pend = max(0, p2_db.dias_pendientes or 0) if p2_db else 0

        dias_p1 = min(dias, p1_pend)
        dias_p2 = min(max(0, dias - dias_p1), p2_pend)

        if (dias_p1 + dias_p2) < dias:
            flash(
                "No hay suficientes días entre P1 y P2 para cubrir la solicitud.",
                "danger",
            )
            return redirect(url_for("convenios.view_employee", empleado_id=e.id))

        (p1_ini, p1_fin), (p2_ini, p2_fin) = partir_rango_por_bolsas(
            inicio, dias_p1, dias_p2
        )

        conv = Convenio(
            id_empleado=e.id,
            fecha_solicitud=date.today(),
            descripcion=f'{decision["motivo"]} Obs: {obs}',
            dias_acumulados=dias,
            estado_firma="Pendiente",
            periodo1=p1_db.periodo if p1_db else None,
            detalle_periodo1=(
                f"{p1_db.fecha_inicio} al {p1_db.fecha_fin}" if p1_db else None
            ),
            periodo2=p2_db.periodo if p2_db else None,
            detalle_periodo2=(
                f"{p2_db.fecha_inicio} al {p2_db.fecha_fin}" if p2_db else None
            ),
            dias_segundo=p2_db.dias_pendientes if p2_db else 0,
        )
        db.session.add(conv)
        db.session.flush()

        if p1_db and dias_p1 > 0:
            p1_db.dias_pendientes = max(0, (p1_db.dias_pendientes or 0) - dias_p1)
            p1_db.dias_tomados = (p1_db.dias_tomados or 0) + dias_p1
            db.session.add(
                MovimientoVacacional(
                    id_empleado=e.id,
                    id_periodo=p1_db.id,
                    id_convenio=conv.id,
                    tipo="CONVENIO",
                    fecha=date.today(),
                    dias=dias_p1,
                    saldo_resultante=p1_db.dias_pendientes,
                    fecha_inicio=p1_ini,
                    fecha_fin=p1_fin,
                )
            )

        if p2_db and dias_p2 > 0:
            p2_db.dias_pendientes = max(0, (p2_db.dias_pendientes or 0) - dias_p2)
            p2_db.dias_tomados = (p2_db.dias_tomados or 0) + dias_p2
            db.session.add(
                MovimientoVacacional(
                    id_empleado=e.id,
                    id_periodo=p2_db.id,
                    id_convenio=conv.id,
                    tipo="CONVENIO",
                    fecha=date.today(),
                    dias=dias_p2,
                    saldo_resultante=p2_db.dias_pendientes,
                    fecha_inicio=p2_ini,
                    fecha_fin=p2_fin,
                )
            )

        db.session.commit()
        flash("Convenio creado y prorrateado por bolsas (P1 primero, luego P2).")
        return redirect(url_for("convenios.view_employee", empleado_id=e.id))

    # Caso: NO requiere convenio → registrar solicitud normal
    if not decision["require_convenio"]:
        if periodo.dias_pendientes < dias:
            flash(f"No hay suficientes días en el periodo {periodo.periodo}.", "danger")
            return redirect(url_for("convenios.view_employee", empleado_id=e.id))

        periodo.dias_pendientes -= dias
        periodo.dias_tomados += dias

        mov_solicitud = MovimientoVacacional(
            id_empleado=e.id,
            id_periodo=periodo.id,
            tipo="SOLICITUD_VACACIONES",
            fecha=date.today(),
            dias=dias,
            saldo_resultante=periodo.dias_pendientes,
            fecha_inicio=inicio,
            fecha_fin=fin,
        )
        db.session.add(mov_solicitud)
        db.session.commit()
        flash("Solicitud de vacaciones registrada y días descontados.")

    return redirect(url_for("convenios.view_employee", empleado_id=e.id))


# =============================
# PDFs de Convenio
# =============================


@convenios_bp.get("/generar_convenio/<int:id>", endpoint="generar_convenio")
@login_required
def generar_convenio(id):
    from weasyprint import HTML

    convenio = db.session.get(Convenio, id)
    html_content = render_template("convenio.html", convenio=convenio)
    pdf = HTML(string=html_content).write_pdf()
    return Response(pdf, mimetype="application/pdf")


@convenios_bp.post(
    "/empleado/<int:empleado_id>/convenio/acumulacion/pdf",
    endpoint="generar_convenio_acumulacion_pdf",
)
@login_required
def generar_convenio_acumulacion_pdf(empleado_id: int):
    from weasyprint import HTML

    e = Empleado.query.get_or_404(empleado_id)

    try:
        firma = datetime.strptime(request.form["fecha_firma"], "%Y-%m-%d").date()
    except Exception:
        abort(400, description="fecha_firma inválida")

    p1_str, p1_inicio, p1_fin = periodo_from_ingreso(e.fecha_ingreso, 1)
    p2_str, p2_inicio, p2_fin = periodo_from_ingreso(e.fecha_ingreso, 2)

    movs_p1 = (
        db.session.query(MovimientoVacacional)
        .join(
            PeriodoVacacional, MovimientoVacacional.id_periodo == PeriodoVacacional.id
        )
        .filter(
            MovimientoVacacional.id_empleado == e.id,
            PeriodoVacacional.periodo == p1_str,
            MovimientoVacacional.tipo != "CONVENIO",
        )
        .order_by(MovimientoVacacional.fecha_inicio.asc())
        .all()
    )

    bloques_p1 = []
    for m in movs_p1:
        ini, fin = m.fecha_inicio, m.fecha_fin
        if not (ini and fin):
            continue
        dias_bloque = int(abs(m.dias) if m.dias is not None else (fin - ini).days + 1)
        bloques_p1.append(
            {
                "dias": dias_bloque,
                "periodo": p1_str,
                "inicio": ini,
                "fin": fin,
                "verbo": verbo_por_bloque(ini, fin, firma),
            }
        )

    total_p1_bloques = sumar_dias(bloques_p1)

    p1_db = PeriodoVacacional.query.filter_by(id_empleado=e.id, periodo=p1_str).first()
    dias_periodo_p1 = p1_db.dias_periodo if (p1_db and p1_db.dias_periodo) else 30

    remanentes_por_convenio = 0
    if p1_db:
        remanentes_por_convenio = (
            db.session.query(
                db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0)
            )
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,
                MovimientoVacacional.tipo == "CONVENIO",
            )
            .scalar()
        ) or 0

    remanentes_por_diferencia = 0
    if p1_db:
        tomados_no_convenio = (
            db.session.query(
                db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0)
            )
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,
                MovimientoVacacional.tipo.in_(("GOCE", "SOLICITUD_VACACIONES")),
            )
            .scalar()
        ) or 0
        if not tomados_no_convenio:
            tomados_no_convenio = int(abs(p1_db.dias_tomados or 0)) or total_p1_bloques
        remanentes_por_diferencia = max(
            0, min(30, dias_periodo_p1) - int(tomados_no_convenio)
        )

    remanentes_p1 = (
        int(remanentes_por_convenio)
        if remanentes_por_convenio
        else int(remanentes_por_diferencia)
    )

    dias_p2_completo = 30
    total_p2 = remanentes_p1 + dias_p2_completo

    ventana_p1_hasta = p1_fin.replace(year=p1_fin.year + 2)
    ventana_p2_desde = p2_inicio.replace(year=p2_inicio.year + 1)
    ventana_p2_hasta = p2_fin.replace(year=p2_fin.year + 1)

    empresa = {
        "razon_social": "CONTRANS S.A.C.",
        "ruc": "20392952455",
        "rep_nombre": "FRANCISCO JOSE GONZALEZ HURTADO",
        "rep_dni": "40106879",
        "direccion": "Avenida A N.° 204 – Ex Fundo Oquendo (Alt. Km 8.5 de Av. Néstor Gambetta – Callao, Provincia Constitucional del Callao)",
        "lugar_firma": "Lima",
    }

    html = render_template(
        "convenio_pdf.html",
        empresa=empresa,
        empleado=e,
        p1={
            "periodo": p1_str,
            "inicio": p1_inicio,
            "fin": p1_fin,
            "bloques": bloques_p1,
            "total": total_p1_bloques,
        },
        p2={
            "periodo": p2_str,
            "inicio": p2_inicio,
            "fin": p2_fin,
            "remanentes_p1": remanentes_p1,
            "dias_p2": dias_p2_completo,
            "total": total_p2,
            "ventana_p1_hasta": ventana_p1_hasta,
            "ventana_p2_desde": ventana_p2_desde,
            "ventana_p2_hasta": ventana_p2_hasta,
        },
        firma={"fecha": firma, "fecha_larga": fecha_firma_literal(firma)},
    )

    from weasyprint import HTML as _HTML

    pdf_io = io.BytesIO()
    _HTML(string=html, base_url=request.host_url).write_pdf(pdf_io)
    pdf_io.seek(0)

    safe_nombre = (e.nombre or "Empleado").replace(" ", "_")
    filename = f"Convenio_Acumulacion_{safe_nombre}_{firma.isoformat()}.pdf"
    return send_file(
        pdf_io, mimetype="application/pdf", as_attachment=True, download_name=filename
    )


@convenios_bp.get("/convenio/<int:convenio_id>/pdf", endpoint="convenio_pdf")
@login_required
def convenio_pdf(convenio_id):
    from weasyprint import HTML

    conv = Convenio.query.get_or_404(convenio_id)
    e = conv.empleado

    periodos = sorted(e.periodos, key=lambda x: (x.fecha_inicio or date.min))
    if len(periodos) < 2:
        abort(400, description="El empleado no tiene al menos dos periodos.")
    p1_db = periodos[-2]
    p2_db = periodos[-1]

    movs_p1_hist = (
        MovimientoVacacional.query.filter(
            MovimientoVacacional.id_empleado == e.id,
            MovimientoVacacional.id_periodo == p1_db.id,
            MovimientoVacacional.tipo.in_(("GOCE", "SOLICITUD_VACACIONES")),
        )
        .order_by(MovimientoVacacional.fecha_inicio.asc())
        .all()
    )

    bloques_p1 = []
    for m in movs_p1_hist:
        ini, fin = m.fecha_inicio, m.fecha_fin
        if not (ini and fin):
            continue
        dias_bloque = (fin - ini).days + 1 if m.dias is None else abs(int(m.dias))
        bloques_p1.append(
            {
                "dias": dias_bloque,
                "periodo": p1_db.periodo,
                "inicio": ini,
                "fin": fin,
                "verbo": verbo_por_bloque(ini, fin, conv.fecha_firma or date.today()),
            }
        )
    total_p1_bloques = sumar_dias(bloques_p1)

    remanentes_p1_de_este_convenio = sum(
        abs(m.dias or 0)
        for m in conv.movimientos
        if m.tipo == "CONVENIO" and m.id_periodo == p1_db.id
    )
    if remanentes_p1_de_este_convenio:
        remanentes_p1 = remanentes_p1_de_este_convenio
    else:
        remanentes_p1 = int(p1_db.dias_pendientes or 0)
        if remanentes_p1 == 0:
            gozados_nc = sum(abs(m.dias or 0) for m in movs_p1_hist)
            dias_periodo = int(p1_db.dias_periodo or 30)
            remanentes_p1 = max(0, dias_periodo - gozados_nc)

    dias_p2 = 30
    total_acum = remanentes_p1 + dias_p2

    ventana_p1_hasta = p1_db.fecha_fin.replace(year=p1_db.fecha_fin.year + 2)
    ventana_p2_desde = p2_db.fecha_inicio.replace(year=p2_db.fecha_inicio.year + 1)
    ventana_p2_hasta = p2_db.fecha_fin.replace(year=p2_db.fecha_fin.year + 1)

    html = render_template(
        "convenio_pdf.html",
        empresa={
            "razon_social": "CONTRANS S.A.C.",
            "ruc": "20392952455",
            "rep_nombre": "FRANCISCO JOSE GONZALEZ HURTADO",
            "rep_dni": "40106879",
            "direccion": "Avenida A N.° 204 – Ex Fundo Oquendo (Alt. Km 8.5 de Av. Néstor Gambetta – Callao)",
            "lugar_firma": "Lima",
        },
        empleado=e,
        p1={
            "periodo": p1_db.periodo,
            "inicio": p1_db.fecha_inicio,
            "fin": p1_db.fecha_fin,
            "bloques": bloques_p1,
            "total": total_p1_bloques,
        },
        p2={
            "periodo": p2_db.periodo,
            "inicio": p2_db.fecha_inicio,
            "fin": p2_db.fecha_fin,
            "remanentes_p1": remanentes_p1,
            "dias_p2": dias_p2,
            "total": total_acum,
            "ventana_p1_hasta": ventana_p1_hasta,
            "ventana_p2_desde": ventana_p2_desde,
            "ventana_p2_hasta": ventana_p2_hasta,
        },
        firma={"fecha_larga": fecha_literal(conv.fecha_firma or date.today())},
    )

    pdf = HTML(string=html, base_url=request.host_url).write_pdf()
    return send_file(
        BytesIO(pdf),
        download_name=f"convenio_{conv.id}.pdf",
        as_attachment=True,
        mimetype="application/pdf",
    )


@convenios_bp.route(
    "/descargar_convenio_pdf/<int:convenio_id>",
    methods=["GET", "POST"],
    endpoint="descargar_convenio_pdf",
)
@login_required
def descargar_convenio_pdf(convenio_id):
    from weasyprint import HTML

    conv = Convenio.query.get_or_404(convenio_id)
    e = conv.empleado

    raw_ff = request.values.get("fecha_firma")
    if raw_ff:
        try:
            firma = datetime.strptime(raw_ff, "%Y-%m-%d").date()
        except ValueError:
            abort(400, description="fecha_firma inválida")
        conv.fecha_firma = firma
        db.session.add(conv)
        db.session.commit()
    else:
        firma = conv.fecha_firma or date.today()

    periodos = sorted(e.periodos, key=lambda x: (x.fecha_inicio or date.min))
    if len(periodos) < 2:
        abort(400, description="El empleado no tiene al menos dos periodos.")
    p1_db = periodos[-2]
    p2_db = periodos[-1]

    movs_p1_hist = (
        MovimientoVacacional.query.filter(
            MovimientoVacacional.id_empleado == e.id,
            MovimientoVacacional.id_periodo == p1_db.id,
            MovimientoVacacional.tipo.in_(("GOCE", "SOLICITUD_VACACIONES")),
        )
        .order_by(MovimientoVacacional.fecha_inicio.asc())
        .all()
    )
    bloques_p1 = []
    for m in movs_p1_hist:
        ini, fin = m.fecha_inicio, m.fecha_fin
        if not (ini and fin):
            continue
        dias_bloque = (fin - ini).days + 1 if m.dias is None else abs(int(m.dias))
        bloques_p1.append(
            {
                "dias": dias_bloque,
                "periodo": p1_db.periodo,
                "inicio": ini,
                "fin": fin,
                "verbo": verbo_por_bloque(ini, fin, firma),
            }
        )
    total_p1_bloques = sumar_dias(bloques_p1)

    remanentes_p1_de_este_convenio = sum(
        abs(m.dias or 0)
        for m in conv.movimientos
        if m.tipo == "CONVENIO" and m.id_periodo == p1_db.id
    )
    if remanentes_p1_de_este_convenio:
        remanentes_p1 = remanentes_p1_de_este_convenio
    else:
        remanentes_p1 = int(p1_db.dias_pendientes or 0)
        if remanentes_p1 == 0:
            gozados_nc = sum(abs(m.dias or 0) for m in movs_p1_hist)
            dias_periodo = int(p1_db.dias_periodo or 30)
            remanentes_p1 = max(0, dias_periodo - gozados_nc)

    dias_p2 = 30
    total_acum = remanentes_p1 + dias_p2

    ventana_p1_hasta = p1_db.fecha_fin.replace(year=p1_db.fecha_fin.year + 2)
    ventana_p2_desde = p2_db.fecha_inicio.replace(year=p2_db.fecha_inicio.year + 1)
    ventana_p2_hasta = p2_db.fecha_fin.replace(year=p2_db.fecha_fin.year + 1)

    html = render_template(
        "convenio_pdf.html",
        empresa={
            "razon_social": "CONTRANS S.A.C.",
            "ruc": "20392952455",
            "rep_nombre": "FRANCISCO JOSE GONZALEZ HURTADO",
            "rep_dni": "40106879",
            "direccion": "Avenida A N.° 204 – Ex Fundo Oquendo (Alt. Km 8.5 de Av. Néstor Gambetta – Callao)",
            "lugar_firma": "Lima",
        },
        empleado=e,
        p1={
            "periodo": p1_db.periodo,
            "inicio": p1_db.fecha_inicio,
            "fin": p1_db.fecha_fin,
            "bloques": bloques_p1,
            "total": total_p1_bloques,
        },
        p2={
            "periodo": p2_db.periodo,
            "inicio": p2_db.fecha_inicio,
            "fin": p2_db.fecha_fin,
            "remanentes_p1": remanentes_p1,
            "dias_p2": dias_p2,
            "total": total_acum,
            "ventana_p1_hasta": ventana_p1_hasta,
            "ventana_p2_desde": ventana_p2_desde,
            "ventana_p2_hasta": ventana_p2_hasta,
        },
        firma={"fecha": firma, "fecha_larga": fecha_firma_literal(firma)},
    )

    pdf = HTML(string=html, base_url=request.host_url).write_pdf()
    response = send_file(
        BytesIO(pdf),
        as_attachment=True,
        download_name=f"convenio_{conv.id}_{firma.isoformat()}.pdf",
        mimetype="application/pdf",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
