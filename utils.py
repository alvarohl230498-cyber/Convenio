import os
import io
from datetime import date, datetime, timedelta

# -------------------- NORMALIZACIÓN DB URL --------------------
def normalize_db_url(url: str) -> str:
    """
    Render/Heroku entregan DATABASE_URL con 'postgres://'
    pero SQLAlchemy espera 'postgresql://'.
    En Windows, si usas psycopg v3, la URL puede requerir '+psycopg'.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if os.name == "nt" and "+psycopg" not in url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# -------------------- FECHAS / FORMATEO --------------------
MESES_ES = [
    "enero","febrero","marzo","abril","mayo","junio",
    "julio","agosto","septiembre","octubre","noviembre","diciembre"
]

MESES_ES_FIRMA = [
    "enero","febrero","marzo","abril","mayo","junio",
    "julio","agosto","septiembre","octubre","noviembre","diciembre"
]

def fecha_literal(d: date) -> str:
    if not d:
        return ''
    return f"{d.day} de {MESES_ES[d.month-1]} de {d.year}"

def fecha_firma_literal(d: date) -> str:
    if not d:
        return ""
    return f"{d.day:02d} de {MESES_ES_FIRMA[d.month-1]} de {d.year}"

def numero_a_letras(n: int) -> str:
    unidades = ["cero","uno","dos","tres","cuatro","cinco","seis","siete","ocho","nueve"]
    especiales = {10:"diez",11:"once",12:"doce",13:"trece",14:"catorce",15:"quince"}
    dieci = {16:"dieciséis",17:"diecisiete",18:"dieciocho",19:"diecinueve"}
    decenas = {20:"veinte",30:"treinta",40:"cuarenta",50:"cincuenta",60:"sesenta"}
    if n < 10: return unidades[n]
    if n in especiales: return especiales[n]
    if 16 <= n <= 19: return dieci[n]
    if n in decenas: return decenas[n]
    if 21 <= n <= 29: return "veinte y " + unidades[n-20]
    if 31 <= n <= 39: return "treinta y " + unidades[n-30]
    if 41 <= n <= 49: return "cuarenta y " + unidades[n-40]
    if 51 <= n <= 59: return "cincuenta y " + unidades[n-50]
    return str(n)


# -------------------- FECHAS DE NEGOCIO --------------------
def add_months(fecha: date, meses: int) -> date:
    year = fecha.year + (fecha.month + meses - 1) // 12
    month = (fecha.month + meses - 1) % 12 + 1
    day = min(
        fecha.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    )
    return date(year, month, day)

def periodo_from_ingreso(fecha_ingreso: date, year_offset: int):
    """
    Devuelve (periodo_str, inicio, fin) para el año N a partir de la fecha de ingreso.
    year_offset=1 -> primer año completo luego del ingreso.
    """
    inicio = date(fecha_ingreso.year + year_offset, fecha_ingreso.month, fecha_ingreso.day)
    fin = inicio.replace(year=inicio.year + 1) - timedelta(days=1)
    periodo_str = f"{inicio.year}-{fin.year}"
    return periodo_str, inicio, fin

def verbo_por_bloque(inicio: date, fin: date, firma: date) -> str:
    if firma < inicio:
        return "serán gozados"
    elif firma >= fin:
        return "fueron gozados"
    else:
        return "se vienen gozando"

def sumar_dias(bloques) -> int:
    return sum(b.get("dias", 0) for b in bloques)

def safe_date(d, fallback=None):
    return d if isinstance(d, date) else fallback


# -------------------- CÁLCULO DE VACACIONES --------------------
def calcular_dias_truncos(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo):
    MAX_DIAS = 30  # puedes ajustar según política
    inicio_real = max(inicio_periodo, fecha_ingreso) if fecha_ingreso else inicio_periodo

    if fecha_actual < inicio_real:
        return 0
    if fecha_actual >= fin_periodo:
        return MAX_DIAS

    meses_completos = (fecha_actual.year - inicio_real.year) * 12 + (fecha_actual.month - inicio_real.month)
    if fecha_actual.day < inicio_real.day:
        meses_completos -= 1
    meses_completos = max(meses_completos, 0)

    fecha_referencia = add_months(inicio_real, meses_completos)
    dias_del_mes = (fecha_actual - fecha_referencia).days
    if dias_del_mes < 0:
        dias_del_mes = 0

    dias_ganados = (meses_completos * 2.5) + (dias_del_mes / 30.0 * 2.5)
    dias_truncos_int = int(dias_ganados)
    if dias_truncos_int > MAX_DIAS:
        dias_truncos_int = MAX_DIAS
    return dias_truncos_int

def calcular_vacaciones(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo):
    MAX_DIAS = 30
    truncos = calcular_dias_truncos(fecha_ingreso, fecha_actual, inicio_periodo, fin_periodo)
    if fecha_actual < fin_periodo:
        return {"truncos": truncos, "pendientes": 0}
    return {"truncos": 0, "pendientes": MAX_DIAS}


# -------------------- LÓGICA DE NEGOCIO (usa modelos/db) --------------------
def validar_solicitud(empleado, inicio_solicitud: date, fin_solicitud: date, periodo_forzado=None):
    """Reglas para decidir si requiere convenio; devuelve dict con periodo_base/acumulado."""
    from models import PeriodoVacacional  # import local para evitar ciclo

    if not empleado.periodos:
        return {'require_convenio': True, 'motivo': 'No hay periodos registrados', 'periodo_base': None}

    if periodo_forzado is not None:
        periodo_base = periodo_forzado
        in_generacion = (periodo_base.fecha_inicio <= inicio_solicitud <= periodo_base.fecha_fin) and \
                        (periodo_base.fecha_inicio <= fin_solicitud <= periodo_base.fecha_fin)

        goce_inicio = periodo_base.fecha_inicio.replace(year=periodo_base.fecha_inicio.year + 1) if periodo_base.fecha_inicio else None
        goce_fin    = periodo_base.fecha_fin.replace(year=periodo_base.fecha_fin.year + 1) if periodo_base.fecha_fin else None
        in_goce     = (goce_inicio and goce_fin) and (goce_inicio <= inicio_solicitud <= goce_fin) and (goce_inicio <= fin_solicitud <= goce_fin)

        if in_generacion or in_goce:
            return {
                'require_convenio': False,
                'motivo': 'Fechas dentro del periodo seleccionado (generación/goce).',
                'periodo_base': periodo_base,
                'periodo_acumulado': None
            }
    else:
        periodo_base = None

    # Ordenar periodos por fecha
    periodos = sorted(empleado.periodos, key=lambda x: x.fecha_inicio or date.min)

    # Periodo base por defecto (último con saldo o el más reciente)
    if periodo_base is None:
        for p in reversed(periodos):
            if (p.dias_pendientes or 0) > 0 or (p.dias_truncos or 0) > 0:
                periodo_base = p
                break
        if not periodo_base:
            periodo_base = periodos[-1]

    # Ventana de goce
    goce_inicio = periodo_base.fecha_inicio.replace(year=periodo_base.fecha_inicio.year + 1)
    goce_fin = periodo_base.fecha_fin.replace(year=periodo_base.fecha_fin.year + 1)

    if goce_inicio <= inicio_solicitud <= goce_fin:
        return {
            'require_convenio': False,
            'motivo': f'Fechas solicitadas dentro del periodo de goce ({goce_inicio} - {goce_fin})',
            'periodo_base': periodo_base,
            'periodo_acumulado': None
        }

    # Fuera de goce → evaluar acumulación
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
            'periodo_acumulado': periodo_acumulado
        }
    else:
        return {
            'require_convenio': True,
            'motivo': f'Fuera del periodo de goce y no hay suficientes días disponibles ({total_dias_disponibles} < {dias_solicitados})',
            'periodo_base': periodo_base,
            'periodo_acumulado': periodo_acumulado
        }

def aplicar_goce(periodo, empleado, dias: int):
    """Actualiza saldos del periodo y registra movimiento GOCE."""
    from models import db, MovimientoVacacional
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

def reconciliar_acumulacion_global():
    """Recalcula truncos/pendientes para todos los periodos al iniciar."""
    from models import db, Empleado, PeriodoVacacional
    hoy = date.today()
    for p in PeriodoVacacional.query.all():
        empleado = Empleado.query.get(p.id_empleado)
        dias_ganados = calcular_dias_truncos(empleado.fecha_ingreso, hoy, p.fecha_inicio, p.fecha_fin)
        if dias_ganados >= (p.dias_periodo or 30):
            p.dias_pendientes = (p.dias_periodo or 30)
            p.dias_truncos = 0
        else:
            p.dias_pendientes = 0
            p.dias_truncos = dias_ganados
    db.session.commit()


# -------------------- SEED DE EJEMPLO --------------------
def seed_data():
    """Carga un empleado y 2 periodos + movimiento de ALTA (para demo)."""
    from models import db, Empleado, PeriodoVacacional, MovimientoVacacional
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
            db.session.add(MovimientoVacacional(
                id_empleado=e.id,
                id_periodo=p.id,
                tipo=f'{periodo}',
                fecha=date.today(),
                dias=dias,
                saldo_resultante=p.dias_pendientes,
                fecha_inicio=None,
                fecha_fin=None
            ))
        db.session.commit()
