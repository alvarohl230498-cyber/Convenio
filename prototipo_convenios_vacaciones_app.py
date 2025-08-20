import os
import io
from datetime import datetime, date, timedelta
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, send_file, flash,make_response, Blueprint, abort,jsonify
from flask_sqlalchemy import SQLAlchemy
from calendar import monthrange
from reportlab.pdfgen import canvas
import locale
from urllib.parse import urlparse
from models import db, Convenio  # tu import normal de SQLAlchemy
from utils import normalize_db_url  # lo que ya usas




app = Flask(__name__)

# Configuración de la ruta de la base de datos
db_path = os.path.join(app.instance_path, "database.db")

# Asegurar que la carpeta instance existe
os.makedirs(app.instance_path, exist_ok=True)

app.secret_key = 'dev-key-rrhh-prototipo-weasy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bp_convenios = Blueprint("convenios", __name__)

# -------------------- MODELOS --------------------
class Empleado(db.Model):
    __tablename__ = 'empleado'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(8), nullable=False, unique=True)
    cargo = db.Column(db.String(100))
    fecha_ingreso = db.Column(db.Date)
    direccion = db.Column(db.String(200))

    periodos = db.relationship("PeriodoVacacional", back_populates="empleado", cascade="all, delete-orphan")
    convenios = db.relationship("Convenio", back_populates="empleado", cascade="all, delete-orphan")


class PeriodoVacacional(db.Model):
    __tablename__ = 'periodo_vacacional'
    id = db.Column(db.Integer, primary_key=True)
    id_empleado = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)
    periodo = db.Column(db.String(9), nullable=False)
    dias_periodo = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)
    
    dias_pendientes = db.Column(db.Integer, default=0)
    dias_tomados = db.Column(db.Integer, default=0)
    dias_truncos = db.Column(db.Integer, default=0)

    empleado = db.relationship("Empleado", back_populates="periodos")
    movimientos = db.relationship("MovimientoVacacional", back_populates="periodo_vacacional", cascade="all, delete-orphan")

class Convenio(db.Model):
    __tablename__ = 'convenio'
    id = db.Column(db.Integer, primary_key=True)
    id_empleado = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)
    fecha_firma = db.Column(db.Date)
    fecha_solicitud = db.Column(db.Date)
    descripcion = db.Column(db.Text)
    dias_acumulados = db.Column(db.Integer)
    estado_firma = db.Column(db.String(20), default='Pendiente')
    # NUEVOS CAMPOS
    periodo1 = db.Column(db.String(50))
    periodo2 = db.Column(db.String(50))
    detalle_periodo1 = db.Column(db.String(200))
    detalle_periodo2 = db.Column(db.String(200))
    dias_segundo = db.Column(db.Integer)

    empleado = db.relationship("Empleado", back_populates="convenios")

class MovimientoVacacional(db.Model):
    __tablename__ = 'movimiento_vacacional'
    id = db.Column(db.Integer, primary_key=True)

    id_empleado = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)
    id_periodo  = db.Column(db.Integer, db.ForeignKey('periodo_vacacional.id'), nullable=False)

    tipo  = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    dias  = db.Column(db.Integer, nullable=False)
    saldo_resultante = db.Column(db.Integer, nullable=False)

    fecha_inicio = db.Column(db.Date)
    fecha_fin    = db.Column(db.Date)

    empleado = db.relationship("Empleado", backref="movimientos")
    periodo_vacacional = db.relationship("PeriodoVacacional", back_populates="movimientos")
    id_convenio = db.Column(db.Integer, db.ForeignKey('convenio.id'), nullable=True)  # Declarar primero
    convenio = db.relationship("Convenio", backref="movimientos", foreign_keys=[id_convenio])


# -------------------- UTILIDADES --------------------
#Normalizar prototipo

def normalize_db_url(url: str) -> str:
    if not url:
        return url
    url = url.replace("postgres://", "postgresql://", 1)
    if os.name == "nt" and "+psycopg" not in url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
    
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')

    raw_url = os.getenv("DATABASE_URL", "sqlite:///database.db")
    database_url = normalize_db_url(raw_url)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    @app.route("/generar_convenio/<int:id>")
    def generar_convenio(id):
        # 👇 Importa WeasyPrint SOLO aquí
        from weasyprint import HTML

        convenio = db.session.get(Convenio, id)
        html_content = render_template("convenio.html", convenio=convenio)
        pdf = HTML(string=html_content).write_pdf()
        return Response(pdf, mimetype="application/pdf")

    with app.app_context():
        db.create_all()

    return app


MESES_ES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

def fecha_literal(d: date):
    if not d:
        return ''
    return f"{d.day} de {MESES_ES[d.month-1]} de {d.year}"

def fecha_larga(d: date) -> str:
    # 14 de agosto de 2025
    return f"{d.day:02d} de {MESES_ES[d.month-1]} de {d.year}"

#! --- SOLO para la fecha de firma del convenio ---


MESES_ES_FIRMA = [
    "enero","febrero","marzo","abril","mayo","junio",
    "julio","agosto","septiembre","octubre","noviembre","diciembre"
]

def fecha_firma_literal(d: date) -> str:
    """Devuelve dd de <mes> de yyyy usando un mapeo 0..11 seguro."""
    if not d:
        return ""
    return f"{d.day:02d} de {MESES_ES_FIRMA[d.month-1]} de {d.year}"



def periodo_from_ingreso(fecha_ingreso: date, year_offset: int):
    """
    Devuelve (periodo_str, inicio, fin) para el año N a partir de la fecha de ingreso.
    year_offset=1 -> primer año completo luego del ingreso (22/08/2023-21/08/2024 en el ejemplo)
    """
    inicio = date(fecha_ingreso.year + year_offset, fecha_ingreso.month, fecha_ingreso.day)
    fin = inicio.replace(year=inicio.year + 1) - timedelta(days=1)
    periodo_str = f"{inicio.year}-{fin.year}"
    return periodo_str, inicio, fin

# Números 0-60 en estilo "veinte y siete" (no "veintisiete") para coincidir con el modelo
def numero_a_letras(n: int) -> str:
    unidades = ["cero","uno","dos","tres","cuatro","cinco","seis","siete","ocho","nueve"]
    especiales = {10:"diez",11:"once",12:"doce",13:"trece",14:"catorce",15:"quince"}
    dieci = {16:"dieciséis",17:"diecisiete",18:"dieciocho",19:"diecinueve"}
    decenas = {20:"veinte",30:"treinta",40:"cuarenta",50:"cincuenta",60:"sesenta"}

    if n < 10: return unidades[n]
    if n in especiales: return especiales[n]
    if 16 <= n <= 19: return dieci[n]
    if n in decenas: return decenas[n]
    if 21 <= n <= 29:
        return "veinte y " + unidades[n-20]
    if 31 <= n <= 39:
        return "treinta y " + unidades[n-30]
    if 41 <= n <= 49:
        return "cuarenta y " + unidades[n-40]
    if 51 <= n <= 59:
        return "cincuenta y " + unidades[n-50]
    return str(n)

# Registrar para que estén disponibles en el template
app.jinja_env.globals.update(fecha_literal=fecha_literal, numero_a_letras=numero_a_letras)

def verbo_por_bloque(inicio: date, fin: date, firma: date) -> str:
    if firma < inicio:
        return "serán gozados"
    elif firma >= fin:
        return "fueron gozados"
    else:
        return "se vienen gozando"

def sumar_dias(bloques) -> int:
    return sum(b["dias"] for b in bloques)

def safe_date(d, fallback=None):
    return d if isinstance(d, date) else fallback


def add_months(fecha, meses):
    year = fecha.year + (fecha.month + meses - 1) // 12
    month = (fecha.month + meses - 1) % 12 + 1
    day = min(
        fecha.day,
        [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    )
    return date(year, month, day)



def validar_solicitud(empleado, inicio_solicitud: date, fin_solicitud: date,periodo_forzado: 'PeriodoVacacional' = None):
    """
    Valida si la solicitud requiere convenio bajo la regla:
    - Cada periodo de generación tiene un periodo de goce (1 año después del inicio y fin del periodo).
    - Si las fechas solicitadas caen dentro del periodo de goce → no requiere convenio.
    - Si no, revisar si hay días pendientes/truncos acumulables para posible convenio.
    """
    if not empleado.periodos:
        return {'require_convenio': True, 'motivo': 'No hay periodos registrados', 'periodo_base': None}

# CAMBIO: si viene un periodo_forzado, usarlo como base
    if periodo_forzado is not None:
        periodo_base = periodo_forzado
        in_generacion = (periodo_base.fecha_inicio <= inicio_solicitud <= periodo_base.fecha_fin) and \
                        (periodo_base.fecha_inicio <= fin_solicitud <= periodo_base.fecha_fin)

        goce_inicio = periodo_base.fecha_inicio.replace(year=periodo_base.fecha_inicio.year + 1) if periodo_base.fecha_inicio else None
        goce_fin    = periodo_base.fecha_fin.replace(year=periodo_base.fecha_fin.year + 1) if periodo_base.fecha_fin else None
        in_goce     = (goce_inicio and goce_fin) and (goce_inicio <= inicio_solicitud <= goce_fin) and (goce_inicio <= fin_solicitud <= goce_fin)

        if in_generacion or in_goce:
            return {
                'require_convenio': False,  # CAMBIO
                'motivo': 'Fechas dentro del periodo seleccionado (generación/goce).',  # CAMBIO
                'periodo_base': periodo_base,
                'periodo_acumulado': None  # CAMBIO
            }
    else:
        periodo_base = None

    # Ordenar periodos por fecha de inicio
    periodos = sorted(empleado.periodos, key=lambda x: x.fecha_inicio or date.min)

    # Tomar el periodo más reciente con días pendientes o truncos
    if periodo_base is None:
        for p in reversed(periodos):
            if (p.dias_pendientes or 0) > 0 or (p.dias_truncos or 0) > 0:
                periodo_base = p
                break
        if not periodo_base:
            periodo_base = periodos[-1]

    # Calcular periodo de goce
    goce_inicio = periodo_base.fecha_inicio.replace(year=periodo_base.fecha_inicio.year + 1)
    goce_fin = periodo_base.fecha_fin.replace(year=periodo_base.fecha_fin.year + 1)

    # Caso: dentro del periodo de goce
    if goce_inicio <= inicio_solicitud <= goce_fin:
        return {
            'require_convenio': False,
            'motivo': f'Fechas solicitadas dentro del periodo de goce ({goce_inicio} - {goce_fin})',
            'periodo_base': periodo_base,
            'periodo_acumulado': None  # CAMBIO

        }

    # Caso: fuera del periodo de goce → evaluar días disponibles
    total_dias_disponibles = sum((p.dias_pendientes or 0) + (p.dias_truncos or 0) for p in empleado.periodos)
    dias_solicitados = (fin_solicitud - inicio_solicitud).days + 1

    periodo_acumulado = None
    for p in reversed(periodos):
        if p != periodo_base and ((p.dias_pendientes or 0) > 0 or (p.dias_truncos or 0) > 0):
            periodo_acumulado = p
            break
    if total_dias_disponibles >= dias_solicitados:
        return {
            'require_convenio': True,
            'motivo': f'Fuera del periodo de goce. Días disponibles: {total_dias_disponibles}',
            'periodo_base': periodo_base,
            'periodo_acumulado': periodo_acumulado  # CAMBIO

        }
    else:
        return {
            'require_convenio': True,
            'motivo': f'Fuera del periodo de goce y no hay suficientes días disponibles ({total_dias_disponibles} < {dias_solicitados})',
            'periodo_base': periodo_base,
            'periodo_acumulado': periodo_acumulado  # CAMBIO

        }

# Aplica goce dentro del periodo_base; asume que ya se validó que alcanza saldo y calendario
# Registra movimiento de GOCE y actualiza pendientes/tomados.

def aplicar_goce(periodo: PeriodoVacacional, empleado: Empleado, dias: int,):
    periodo.dias_tomados = (periodo.dias_tomados or 0) + dias
    periodo.dias_pendientes = max(0, (periodo.dias_pendientes or 0) - dias)
    mov = MovimientoVacacional(
        id_empleado=empleado.id,
        id_periodo=periodo.id,
        tipo='GOCE',
        fecha=date.today(),
        dias=-dias,
        saldo_resultante=periodo.dias_pendientes
    )
    db.session.add(mov)


# --- Cálculo de días truncos (acumulados a la fecha) ---
def calcular_dias_truncos(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo):
    MAX_DIAS = 30  # puedes ajustar según política

    # Ajustar inicio real si ingresó después del inicio de periodo
    inicio_real = max(inicio_periodo, fecha_ingreso) if fecha_ingreso else inicio_periodo

    # Caso: aún no empieza el periodo para el trabajador
    if fecha_actual < inicio_real:
        return 0

    # Caso: ya terminó el periodo -> devuelve días completos
    if fecha_actual >= fin_periodo:
        return MAX_DIAS

    # Calcular meses completos transcurridos
    meses_completos = (fecha_actual.year - inicio_real.year) * 12 + (fecha_actual.month - inicio_real.month)
    if fecha_actual.day < inicio_real.day:
        meses_completos -= 1
    meses_completos = max(meses_completos, 0)

    # Fecha base luego de meses completos
    fecha_referencia = add_months(inicio_real, meses_completos)

    # Días transcurridos en el mes actual
    dias_del_mes = (fecha_actual - fecha_referencia).days
    if dias_del_mes < 0:
        dias_del_mes = 0

    # Fórmula: 2.5 por mes + proporcional del mes en curso
    dias_ganados = (meses_completos * 2.5) + (dias_del_mes / 30.0 * 2.5)

    # Devolver truncado a entero (sin redondear)
    dias_truncos_int = int(dias_ganados)

    # No superar máximo permitido
    if dias_truncos_int > MAX_DIAS:
        dias_truncos_int = MAX_DIAS

    return dias_truncos_int

# --- Cálculo global de vacaciones ---
def calcular_vacaciones(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo):
    MAX_DIAS = 30
    truncos = calcular_dias_truncos(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo)

    # Si todavía no llega al fin del período: todo son truncos
    if fecha_actual < fin_periodo:
        return {
            "truncos": truncos,
            "pendientes": 0
        }

    # Si ya terminó el período: pasa a pendientes completos
    return {
        "truncos": 0,
        "pendientes": MAX_DIAS
    }

# CAMBIO: recalcula todos los periodos al iniciar la app
def reconciliar_acumulacion_global():
    hoy = date.today()
    for p in PeriodoVacacional.query.all():
        empleado = Empleado.query.get(p.id_empleado)
        dias_ganados = calcular_dias_truncos(empleado.fecha_ingreso, hoy, p.fecha_inicio, p.fecha_fin)
        if dias_ganados >= p.dias_periodo:
            p.dias_pendientes = p.dias_periodo
            p.dias_truncos = 0
        else:
            p.dias_pendientes = 0
            p.dias_truncos = dias_ganados
    db.session.commit()


# -------------------- RUTAS --------------------
@app.template_filter('num_es')
def num_es(n):
    n = int(n or 0)
    mapa = {
        0:'cero',1:'uno',2:'dos',3:'tres',4:'cuatro',5:'cinco',6:'seis',7:'siete',8:'ocho',9:'nueve',
        10:'diez',11:'once',12:'doce',13:'trece',14:'catorce',15:'quince',16:'dieciséis',17:'diecisiete',
        18:'dieciocho',19:'diecinueve',20:'veinte',21:'veintiuno',22:'veintidós',23:'veintitrés',
        24:'veinticuatro',25:'veinticinco',26:'veintiséis',27:'veintisiete',28:'veintiocho',29:'veintinueve',
        30:'treinta',31:'treinta y uno',32:'treinta y dos',33:'treinta y tres',34:'treinta y cuatro',
        35:'treinta y cinco',36:'treinta y seis',37:'treinta y siete',38:'treinta y ocho',39:'treinta y nueve',
        40:'cuarenta',41:'cuarenta y uno',42:'cuarenta y dos',43:'cuarenta y tres',44:'cuarenta y cuatro',
        45:'cuarenta y cinco',46:'cuarenta y seis',47:'cuarenta y siete',48:'cuarenta y ocho',49:'cuarenta y nueve',
        50:'cincuenta',51:'cincuenta y uno',52:'cincuenta y dos',53:'cincuenta y tres',54:'cincuenta y cuatro',
        55:'cincuenta y cinco',56:'cincuenta y seis',57:'cincuenta y siete',58:'cincuenta y ocho',
        59:'cincuenta y nueve',60:'sesenta'
    }
    return mapa.get(n, str(n))



# ========== API auxiliar para abrir modal (opcional) ==========
@app.route("/empleado/<int:empleado_id>/convenio/acumulacion/datos", methods=["GET"])
def convenio_datos(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    # Calcula periodos desde la fecha de ingreso, por si no existieran en BD
    p1_str, p1_inicio, p1_fin   = periodo_from_ingreso(e.fecha_ingreso, 1)
    p2_str, p2_inicio, p2_fin   = periodo_from_ingreso(e.fecha_ingreso, 2)

    return jsonify({
        "empleado": {"id": e.id, "nombre": f"{e.nombre}", "dni": e.dni,
                    "cargo": e.cargo, "direccion": e.direccion},
        "periodos": {
            "p1": {"periodo": p1_str, "inicio": p1_inicio.isoformat(), "fin": p1_fin.isoformat()},
            "p2": {"periodo": p2_str, "inicio": p2_inicio.isoformat(), "fin": p2_fin.isoformat()},
        }
    })


# ========== Generador de PDF ==========
@app.route("/empleado/<int:empleado_id>/convenio/acumulacion/pdf", methods=["POST"])
def generar_convenio_acumulacion_pdf(empleado_id: int):
    e = Empleado.query.get_or_404(empleado_id)

    # 1) Fecha de firma
    try:
        firma = datetime.strptime(request.form["fecha_firma"], "%Y-%m-%d").date()
    except Exception:
        abort(400, description="fecha_firma inválida")

    # 2) Periodos desde fecha de ingreso
    p1_str, p1_inicio, p1_fin = periodo_from_ingreso(e.fecha_ingreso, 1)
    p2_str, p2_inicio, p2_fin = periodo_from_ingreso(e.fecha_ingreso, 2)

    # --- Primer periodo: listar bloques desde historial (EXCLUYE CONVENIO) ---
    movs_p1 = (
        db.session.query(MovimientoVacacional)
        .join(PeriodoVacacional, MovimientoVacacional.id_periodo == PeriodoVacacional.id)
        .filter(
            MovimientoVacacional.id_empleado == e.id,
            PeriodoVacacional.periodo == p1_str,
            MovimientoVacacional.tipo != 'CONVENIO'
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
        bloques_p1.append({
            "dias": dias_bloque,
            "periodo": p1_str,
            "inicio": ini,
            "fin": fin,
            "verbo": verbo_por_bloque(ini, fin, firma)
        })

    total_p1_bloques = sumar_dias(bloques_p1)

    # --- Base de datos del 1er periodo ---
    p1_db = PeriodoVacacional.query.filter_by(id_empleado=e.id, periodo=p1_str).first()
    dias_periodo_p1 = p1_db.dias_periodo if (p1_db and p1_db.dias_periodo) else 30

    # === PRIORIDAD 1: usar lo registrado como CONVENIO en el 1er período ===
    remanentes_por_convenio = 0
    if p1_db:
        remanentes_por_convenio = (
            db.session.query(db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0))
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,   # ¡IMPORTANTE! Debe apuntar al P1
                MovimientoVacacional.tipo == 'CONVENIO'
            )
            .scalar()
        ) or 0

    # === PRIORIDAD 2 (fallback): 30 - gozados NO-CONVENIO ===
    remanentes_por_diferencia = 0
    if p1_db:
        tomados_no_convenio = (
            db.session.query(db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0))
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,
                MovimientoVacacional.tipo.in_(('GOCE', 'SOLICITUD_VACACIONES'))
            )
            .scalar()
        ) or 0

        if not tomados_no_convenio:
            # Respaldo: usa p1.dias_tomados o los bloques con rango
            tomados_no_convenio = int(abs(p1_db.dias_tomados or 0)) or total_p1_bloques

        remanentes_por_diferencia = max(0, min(30, dias_periodo_p1) - int(tomados_no_convenio))

    # === Selección final de remanentes del 1er periodo ===
    # Si hay CONVENIO registrado en P1, úsalo; si no, usa la diferencia.
    remanentes_p1 = int(remanentes_por_convenio) if remanentes_por_convenio else int(remanentes_por_diferencia)

    # --- Segundo periodo (30) y total acumulado ---
    dias_p2_completo = 30
    total_p2 = remanentes_p1 + dias_p2_completo

    # --- Ventanas de goce ---
    ventana_p1_hasta = p1_fin.replace(year=p1_fin.year + 2)
    ventana_p2_desde = p2_inicio.replace(year=p2_inicio.year + 1)
    ventana_p2_hasta = p2_fin.replace(year=p2_fin.year + 1)

    empresa = {
        "razon_social": "CONTRANS S.A.C.",
        "ruc": "20392952455",
        "rep_nombre": "FRANCISCO JOSE GONZALEZ HURTADO",
        "rep_dni": "40106879",
        "direccion": "Avenida A N.° 204 – Ex Fundo Oquendo (Alt. Km 8.5 de Av. Néstor Gambetta – Callao, Provincia Constitucional del Callao)",
        "lugar_firma": "Lima"
    }

    # Render
    html = render_template(
        "convenio_pdf.html",
        empresa=empresa,
        empleado=e,
        p1={
            "periodo": p1_str, "inicio": p1_inicio, "fin": p1_fin,
            "bloques": bloques_p1, "total": total_p1_bloques
        },
        p2={
            "periodo": p2_str, "inicio": p2_inicio, "fin": p2_fin,
            "remanentes_p1": remanentes_p1, "dias_p2": dias_p2_completo,
            "total": total_p2,
            "ventana_p1_hasta": ventana_p1_hasta,
            "ventana_p2_desde": ventana_p2_desde,
            "ventana_p2_hasta": ventana_p2_hasta
        },
        firma={"fecha": firma, "fecha_larga": fecha_firma_literal(firma)}
    )

    pdf_io = io.BytesIO()
    HTML(string=html, base_url=request.host_url).write_pdf(pdf_io)
    pdf_io.seek(0)

    safe_nombre = (e.nombre or "Empleado").replace(" ", "_")
    filename = f"Convenio_Acumulacion_{safe_nombre}_{firma.isoformat()}.pdf"
    return send_file(pdf_io, mimetype="application/pdf", as_attachment=True, download_name=filename)


@app.context_processor
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


@app.route('/')
def index():
    empleados = Empleado.query.order_by(Empleado.nombre).all()
    return render_template('index.html', empleados=empleados)

# Alta empleado
@app.route('/employee/new', methods=['GET', 'POST'])
def new_employee():
    if request.method == 'POST':
        dni = request.form['dni'].strip()
        if Empleado.query.filter_by(dni=dni).first():
            flash('DNI ya existe. Verifique.')
            return redirect(url_for('new_employee'))
        nombre = request.form['nombre'].strip()
        cargo = request.form.get('cargo')
        fecha_ingreso = request.form.get('fecha_ingreso')
        direccion = request.form.get('direccion')
        fecha_ingreso_dt = datetime.strptime(fecha_ingreso, '%Y-%m-%d').date() if fecha_ingreso else None
        e = Empleado(dni=dni, nombre=nombre, cargo=cargo, direccion=direccion, fecha_ingreso=fecha_ingreso_dt)
        db.session.add(e)
        db.session.commit()
        flash('Empleado creado.')
        return redirect(url_for('index'))
    return render_template('new_employee.html')




#Eliminar Empleado
@app.route('/employee/<int:empleado_id>/delete', methods=['POST'])
def delete_employee(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    db.session.delete(e)
    db.session.commit()
    flash('Colaborador eliminado correctamente.')
    return redirect(url_for('index'))

# Ver empleado

@app.route('/employee/<int:empleado_id>', methods=['GET'])
def view_employee(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    # Ordenamos periodos por fecha de inicio
    periodos = sorted(e.periodos, key=lambda x: (x.fecha_inicio or date.min), reverse=True)
    movimientos = (MovimientoVacacional.query
                    .filter_by(id_empleado=empleado_id)
                    .order_by(MovimientoVacacional.fecha.desc())
                    .all())
    return render_template('empleado.html', empleado=e, periodos=periodos, movimientos=movimientos)


# Editar empleado

@app.route('/period/<int:periodo_id>/edit', methods=['POST'])
def edit_period(periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    p.periodo = request.form['periodo'].strip()
    p.fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d').date()
    p.fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d').date()
    p.dias_periodo = int(request.form.get('dias_periodo', 30))
    p.dias_tomados = int(request.form.get('dias_tomados', 0))
    p.dias_pendientes = int(request.form.get('dias_pendientes', 0))
    p.dias_truncos = int(request.form.get('dias_truncos', 0))
    
    db.session.commit()
    flash('Periodo vacacional actualizado correctamente.')
    return redirect(url_for('view_employee', empleado_id=p.id_empleado))


# Alta de periodo
@app.route('/employee/<int:empleado_id>/period/new', methods=['POST'])
def new_period(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)

    periodo = request.form['periodo'].strip()  # Ejemplo: "2024-2025"
    dias = int(request.form.get('dias_periodo', 30))

    try:
        anio_inicio, anio_fin = map(int, periodo.split('-'))
    except ValueError:
        flash("Formato de periodo inválido. Debe ser AAAA-AAAA.")
        return redirect(url_for('view_employee', empleado_id=e.id))

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
        dias_truncos=0
    )

    db.session.add(p)
    db.session.flush()

    # CAMBIO: calcular truncos/pendientes en el backend usando fecha de ingreso del empleado y hoy
    hoy = date.today()
    dias_ganados = calcular_dias_truncos(e.fecha_ingreso, hoy, fecha_inicio, fecha_fin)  # CAMBIO

    # CAMBIO: asignar pendientes/truncos según lo calculado
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
        saldo_resultante=p.dias_pendientes
    )
    db.session.add(mov_alta)

    db.session.commit()
    flash('Periodo vacacional agregado y movimiento ALTA registrado.')
    return redirect(url_for('view_employee', empleado_id=e.id))


#Eliminar Periodo

@app.route('/period/<int:periodo_id>/delete', methods=['POST'])
def delete_period(periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    empleado_id = p.id_empleado
    db.session.delete(p)
    db.session.commit()
    flash('Periodo vacacional eliminado correctamente.')
    return redirect(url_for('view_employee', empleado_id=empleado_id))


#Solicitar Vacaciones
@app.route('/employee/<int:empleado_id>/vacaciones/solicitar', methods=['POST'])
def solicitar_vacaciones(empleado_id):
    e = Empleado.query.get_or_404(empleado_id)
    inicio = datetime.strptime(request.form['inicio'], '%Y-%m-%d').date()
    fin = datetime.strptime(request.form['fin'], '%Y-%m-%d').date()
    obs = request.form.get('obs', '')
    confirmar = request.form.get('confirmar', 'no')

    # 🔹 NUEVO: obtenemos el periodo elegido en el formulario
    periodo_id = int(request.form['periodo_id'])
    periodo = PeriodoVacacional.query.get_or_404(periodo_id)

    dias = (fin - inicio).days + 1
    
    # CAMBIO: Validar usando el periodo seleccionado
    decision = validar_solicitud(e, inicio, fin, periodo_forzado=periodo)  # CAMBIO

    # Caso: requiere convenio y aún no se ha confirmado → volver al template con aviso
    if decision['require_convenio'] and confirmar != 'si':
        return render_template(
            "empleado.html",
            empleado=e,
            periodos=sorted(e.periodos, key=lambda x: (x.fecha_inicio or date.min), reverse=True),  # ← aquí
            movimientos=(MovimientoVacacional.query
                        .filter_by(id_empleado=e.id)
                        .order_by(MovimientoVacacional.fecha.desc())
                        .all()),
            require_convenio=True,
            motivo_convenio=decision['motivo'],
            fecha_inicio=inicio,
            fecha_fin=fin,
            obs=obs
        )

    # Caso: convenio confirmado → registrar (PRORRATEO entre P1 y P2)
    if decision['require_convenio'] and confirmar == 'si':
        periodo_acumulado = decision.get('periodo_acumulado')  # Esto devuelve None si no existe

        conv = Convenio(
            id_empleado=e.id,
            fecha_solicitud=date.today(),
            descripcion=f'{decision["motivo"]} Obs: {obs}',
            dias_acumulados=dias,
            estado_firma='Pendiente',
            periodo1=decision['periodo_base'].periodo if decision['periodo_base'] else None,
            detalle_periodo1=f"{decision['periodo_base'].fecha_inicio} al {decision['periodo_base'].fecha_fin}" if decision['periodo_base'] else None,
            periodo2=periodo_acumulado.periodo if periodo_acumulado else None,
            detalle_periodo2=f"{periodo_acumulado.fecha_inicio} al {periodo_acumulado.fecha_fin}" if periodo_acumulado else None,
            dias_segundo=periodo_acumulado.dias_pendientes if periodo_acumulado else 0
        )
        db.session.add(conv)
        db.session.flush()

        # 🔸 Identifica P1 y P2 consecutivos desde la fecha de ingreso (para registrar correctamente el CONVENIO)
        p1_str, p1_inicio, p1_fin = periodo_from_ingreso(e.fecha_ingreso, 1)
        p2_str, p2_inicio, p2_fin = periodo_from_ingreso(e.fecha_ingreso, 2)
        p1_db = PeriodoVacacional.query.filter_by(id_empleado=e.id, periodo=p1_str).first()
        p2_db = PeriodoVacacional.query.filter_by(id_empleado=e.id, periodo=p2_str).first()

        # 🔸 Prorrateo: primero consume los pendientes del P1; el resto va contra P2
        p1_disponibles = max(0, (p1_db.dias_pendientes if p1_db and p1_db.dias_pendientes is not None else 0))
        dias_p1 = min(dias, p1_disponibles)
        dias_p2 = max(0, dias - dias_p1)

        # 🔸 Registrar movimiento CONVENIO en P1 (si corresponde) y actualizar saldos
        if p1_db and dias_p1 > 0:
            p1_db.dias_pendientes = max(0, (p1_db.dias_pendientes or 0) - dias_p1)
            p1_db.dias_tomados = (p1_db.dias_tomados or 0) + dias_p1
            db.session.add(MovimientoVacacional(
                id_empleado=e.id,
                id_periodo=p1_db.id,
                id_convenio=conv.id,
                tipo='CONVENIO',
                fecha=date.today(),
                dias=dias_p1,  # positivo
                saldo_resultante=p1_db.dias_pendientes,
                fecha_inicio=inicio,
                fecha_fin=fin
            ))

        # 🔸 Registrar movimiento CONVENIO en P2 (si corresponde) y actualizar saldos
        if p2_db and dias_p2 > 0:
            p2_db.dias_pendientes = max(0, (p2_db.dias_pendientes or 0) - dias_p2)
            p2_db.dias_tomados = (p2_db.dias_tomados or 0) + dias_p2
            db.session.add(MovimientoVacacional(
                id_empleado=e.id,
                id_periodo=p2_db.id,
                id_convenio=conv.id,
                tipo='CONVENIO',
                fecha=date.today(),
                dias=dias_p2,  # positivo
                saldo_resultante=p2_db.dias_pendientes,
                fecha_inicio=inicio,
                fecha_fin=fin
            ))

        db.session.commit()
        flash('Convenio creado, prorrateado entre P1 y P2, y movimientos registrados.')
        return redirect(url_for('view_employee', empleado_id=e.id))

    # Caso: no requiere convenio → solo registrar solicitud
    if not decision['require_convenio']:
        # 🔹 Validar si hay suficientes días pendientes
        if periodo.dias_pendientes < dias:
            flash(f"No hay suficientes días en el periodo {periodo.periodo}.", "danger")
            return redirect(url_for('view_employee', empleado_id=e.id))

        # 🔹 Descontamos del periodo
        periodo.dias_pendientes -= dias
        periodo.dias_tomados += dias

        mov_solicitud = MovimientoVacacional(
            id_empleado=e.id,
            id_periodo=periodo.id,  # 🔹 usamos el periodo seleccionado
            tipo='SOLICITUD_VACACIONES',
            fecha=date.today(),
            dias=dias,
            saldo_resultante=periodo.dias_pendientes,
            fecha_inicio=inicio,     # CAMBIO: guardar el rango solicitado
            fecha_fin=fin            # CAMBIO
        )
        db.session.add(mov_solicitud)
        db.session.commit()
        flash('Solicitud de vacaciones registrada y días descontados.')

    return redirect(url_for('view_employee', empleado_id=e.id))


# Ajuste manual de saldo del periodo (opcional)
@app.route('/employee/<int:empleado_id>/period/<int:periodo_id>/ajuste', methods=['POST'])
def ajustar_periodo(empleado_id, periodo_id):
    p = PeriodoVacacional.query.get_or_404(periodo_id)
    e = Empleado.query.get_or_404(empleado_id)
    delta = int(request.form.get('delta_dias', 0))  # puede ser negativo
    p.dias_pendientes = max(0, (p.dias_pendientes or 0) + delta)
    if delta < 0:
        p.dias_tomados = (p.dias_tomados or 0) + abs(delta)
    mov = MovimientoVacacional(
        id_empleado=e.id, id_periodo=p.id, tipo='AJUSTE', fecha=date.today(), dias=delta,
    )
    db.session.add(mov)
    db.session.commit()
    flash('Ajuste aplicado.')
    return redirect(url_for('view_employee', empleado_id=e.id))

# Eliminar movimiento
@app.route('/movimiento/<int:id>/delete', methods=['POST'])
def delete_movimiento(id):
    mov = MovimientoVacacional.query.get_or_404(id)
    periodo = PeriodoVacacional.query.get(mov.id_periodo)

    db.session.delete(mov)
    db.session.commit()

    if periodo:
        movimientos_restantes = MovimientoVacacional.query.filter_by(id_periodo=periodo.id).all()

        dias_tomados = 0
        dias_pendientes = periodo.dias_periodo
        dias_truncos = 0

        for m in movimientos_restantes:
            if m.tipo in ('GOCE', 'SOLICITUD_VACACIONES'):
                dias_tomados += abs(m.dias)
                dias_pendientes -= abs(m.dias)
            elif m.tipo == 'AJUSTE':
                dias_pendientes += m.dias
            elif m.tipo == 'TRUNCO':
                dias_truncos += abs(m.dias)
            elif m.tipo.startswith("Periodo vacacional"):
                dias_pendientes = m.dias  # Resetea a días iniciales del periodo

        periodo.dias_tomados = max(dias_tomados, 0)
        periodo.dias_pendientes = max(dias_pendientes, 0)
        periodo.dias_truncos = max(dias_truncos, 0)
        db.session.commit()

    flash('Movimiento eliminado y totales recalculados correctamente.')
    return redirect(url_for('view_employee', empleado_id=mov.id_empleado))

# Editar movimiento
@app.route('/movimiento/<int:id>/edit', methods=['POST'])
def edit_movimiento(id):
    mov = MovimientoVacacional.query.get_or_404(id)
    inicio = request.form.get('fecha_inicio')
    fin = request.form.get('fecha_fin')
    if inicio:
        mov.fecha_inicio = datetime.strptime(inicio, '%Y-%m-%d').date()
    if fin:
        mov.fecha_fin = datetime.strptime(fin, '%Y-%m-%d').date()
    db.session.commit()
    flash('Movimiento actualizado correctamente.')
    return redirect(url_for('view_employee', empleado_id=mov.id_empleado))


# PDF del convenio
@app.route('/convenio/<int:convenio_id>/pdf')
def convenio_pdf(convenio_id):
    conv = Convenio.query.get_or_404(convenio_id)
    emp = conv.empleado

    # Preparar datos para la plantilla (toma 2 últimos periodos si existen)
    periodo1 = ''
    periodo2 = ''
    detalle1 = ''
    detalle2 = ''
    dias_acumulados = 0
    dias_segundo = 0

    per = sorted(emp.periodos, key=lambda x: x.fecha_inicio or date.min)
    if len(per) >= 1:
        periodo1 = per[-2].periodo if len(per) >= 2 else per[-1].periodo
    if len(per) >= 2:
        periodo2 = per[-1].periodo

    if len(per) >= 2:
        p1 = per[-2]
        p2 = per[-1]
        detalle1 = f"{p1.dias_tomados} DIAS, correspondientes al periodo vacacional {p1.periodo}; fueron gozados en las fechas registradas."
        detalle2 = f"{p2.dias_pendientes} DIAS: correspondientes al periodo vacacional {p2.periodo}."
        dias_acumulados = (p1.dias_pendientes or 0) + (p2.dias_pendientes or 0)
        dias_segundo = p2.dias_pendientes or 0
    else:
        detalle1 = 'Detalle no disponible.'
        detalle2 = 'Detalle no disponible.'
        dias_acumulados = conv.dias_acumulados or 0
        dias_segundo = 0

    rendered = render_template(
        'convenio_pdf.html',
        empleado=emp,
        convenio=conv,
        fecha_ingreso_literal=fecha_literal(emp.fecha_ingreso),
        periodo1=periodo1,
        periodo2=periodo2,
        detalle_periodo1=detalle1,
        detalle_periodo2=detalle2,
        dias_acumulados=dias_acumulados,
        dias_segundo=dias_segundo,
        fecha_firma_literal=fecha_literal(conv.fecha_firma if conv.fecha_firma else date.today())
    )

    pdf = HTML(string=rendered).write_pdf()
    return send_file(BytesIO(pdf), download_name=f'convenio_{conv.id}.pdf', as_attachment=True, mimetype='application/pdf')

#!Descargar convenio

@app.route('/descargar_convenio_pdf/<int:convenio_id>', methods=['GET', 'POST'])
def descargar_convenio_pdf(convenio_id):
    conv = Convenio.query.get_or_404(convenio_id)
    e = conv.empleado

    # Lee fecha del form o querystring
    raw_ff = request.values.get('fecha_firma')
    if raw_ff:
        try:
            firma = datetime.strptime(raw_ff, '%Y-%m-%d').date()
        except ValueError:
            abort(400, description="fecha_firma inválida")
        # OPCIONAL: persiste la fecha de firma elegida para ese convenio
        conv.fecha_firma = firma
        db.session.add(conv)
        db.session.commit()
    else:
        firma = conv.fecha_firma or date.today()

    # 2) Periodos consecutivos desde la fecha de ingreso
    p1_str, p1_inicio, p1_fin = periodo_from_ingreso(e.fecha_ingreso, 1)
    p2_str, p2_inicio, p2_fin = periodo_from_ingreso(e.fecha_ingreso, 2)

    # 3) Bloques del P1 EXCLUYENDO 'CONVENIO' (viñetas del primer periodo)
    movs_p1 = (
        db.session.query(MovimientoVacacional)
        .join(PeriodoVacacional, MovimientoVacacional.id_periodo == PeriodoVacacional.id)
        .filter(
            MovimientoVacacional.id_empleado == e.id,
            PeriodoVacacional.periodo == p1_str,
            MovimientoVacacional.tipo != 'CONVENIO'
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
        bloques_p1.append({
            "dias": dias_bloque,
            "periodo": p1_str,
            "inicio": ini,
            "fin": fin,
            "verbo": verbo_por_bloque(ini, fin, firma)
        })
    total_p1_bloques = sumar_dias(bloques_p1)

    # 4) Periodo P1 en BD
    p1_db = PeriodoVacacional.query.filter_by(id_empleado=e.id, periodo=p1_str).first()
    dias_periodo_p1 = p1_db.dias_periodo if (p1_db and p1_db.dias_periodo) else 30

    # 5) PRIORIZA lo registrado en ESTE convenio para P1
    remanentes_de_este_convenio_p1 = 0
    if p1_db:
        remanentes_de_este_convenio_p1 = sum(
            abs(m.dias or 0)
            for m in conv.movimientos
            if m.tipo == 'CONVENIO' and m.id_periodo == p1_db.id
        )

    # 6) Si no hay registro explícito en este convenio, cae a:
    #    6.1) suma global de CONVENIO en P1 del empleado
    remanentes_por_convenio = 0
    if p1_db and remanentes_de_este_convenio_p1 == 0:
        remanentes_por_convenio = (
            db.session.query(db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0))
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,
                MovimientoVacacional.tipo == 'CONVENIO'
            )
            .scalar()
        ) or 0

    #    6.2) diferencia: 30 - gozados NO-CONVENIO
    remanentes_por_diferencia = 0
    if p1_db and remanentes_de_este_convenio_p1 == 0 and remanentes_por_convenio == 0:
        tomados_no_convenio = (
            db.session.query(db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0))
            .filter(
                MovimientoVacacional.id_empleado == e.id,
                MovimientoVacacional.id_periodo == p1_db.id,
                MovimientoVacacional.tipo.in_(('GOCE', 'SOLICITUD_VACACIONES'))
            )
            .scalar()
        ) or 0

        if not tomados_no_convenio:
            tomados_no_convenio = int(abs(p1_db.dias_tomados or 0)) or total_p1_bloques

        remanentes_por_diferencia = max(0, min(30, dias_periodo_p1) - int(tomados_no_convenio))

    # 7) Selección final
    if remanentes_de_este_convenio_p1:
        remanentes_p1 = int(remanentes_de_este_convenio_p1)
    elif remanentes_por_convenio:
        remanentes_p1 = int(remanentes_por_convenio)
    else:
        remanentes_p1 = int(remanentes_por_diferencia)

    # 8) Segundo periodo (fijo 30) y ventanas
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
        "lugar_firma": "Lima"
    }

    html = render_template(
        "convenio_pdf.html",
        empresa=empresa, empleado=e,
        p1={"periodo": p1_str, "inicio": p1_inicio, "fin": p1_fin,
            "bloques": bloques_p1, "total": total_p1_bloques},
        p2={"periodo": p2_str, "inicio": p2_inicio, "fin": p2_fin,
            "remanentes_p1": remanentes_p1, "dias_p2": dias_p2_completo, "total": total_p2,
            "ventana_p1_hasta": ventana_p1_hasta,
            "ventana_p2_desde": ventana_p2_desde,
            "ventana_p2_hasta": ventana_p2_hasta},
        firma={"fecha": firma, "fecha_larga": fecha_firma_literal(firma)}
    )
# ... (tu código tal cual para p1/p2/bloques/render_template) ...

    pdf = HTML(string=html, base_url=request.host_url).write_pdf()
    response = send_file(
        BytesIO(pdf),
        as_attachment=True,
        # <<< Clave: nombre único por fecha para evitar abrir un PDF viejo
        download_name=f'convenio_{conv.id}_{firma.isoformat()}.pdf',
        mimetype='application/pdf'
    )
    # Evita cache en navegador
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response



@app.template_filter('fecha_pe')
def fecha_pe(value):
    """Devuelve dd/mm/aaaa. Soporta date, datetime o string ISO."""
    if not value:
        return ''
    if isinstance(value, (date, datetime)):
        return value.strftime('%d/%m/%Y')
    try:
        return datetime.fromisoformat(str(value)).strftime('%d/%m/%Y')
    except Exception:
        return str(value)



# -------------------- INICIALIZACIÓN CON DATOS DE EJEMPLO --------------------

def seed_data():
    if Empleado.query.count() == 0:
        e = Empleado(
            dni='09672476', nombre='Augusto Alberto Reaño Wong',
            cargo='JEFE DE OPERACIONES E INFRAESTRUCTURA TI',
            direccion='AV. JOSE LEGUIA Y MELENDEZ 1575, URB. SURA - PUEBLO LIBRE',
            fecha_ingreso=datetime.strptime('2007-12-01', '%Y-%m-%d').date()
        )
        db.session.add(e)
        db.session.flush()
        datos_periodos = [
            ('2023-2024','2023-12-01','2024-11-30',30,23,7,0),
            ('2024-2025','2024-12-01','2025-11-30',30,0,30,21),
        ]
        for periodo, fi, ff, dias, tomados, pendientes, truncos in datos_periodos:
            p = PeriodoVacacional(
                id_empleado=e.id, periodo=periodo,
                fecha_inicio=datetime.strptime(fi,'%Y-%m-%d').date(),
                fecha_fin=datetime.strptime(ff,'%Y-%m-%d').date(),
                dias_periodo=dias, dias_tomados=tomados,
                dias_pendientes=pendientes, dias_truncos=truncos
            )
            db.session.add(p)
            db.session.flush()
            # Movimiento de ALTA por cada periodo
            db.session.add(MovimientoVacacional(
                id_empleado=e.id,
                id_periodo=p.id,
                tipo=f'{periodo}',
                fecha=date.today(),  # 🔹 Antes estaba None
                dias=dias,
                saldo_resultante=p.dias_pendientes,
                fecha_inicio=None,
                fecha_fin=None
            ))
        db.session.commit()
        print('Seed: empleado de ejemplo creado.')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
        reconciliar_acumulacion_global()  # CAMBIO: actualizar periodos existentes al iniciar
    app.run(debug=True)
