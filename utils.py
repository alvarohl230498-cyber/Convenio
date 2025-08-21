# utils.py
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


# -------------------- UTILIDADES DE PERÍODOS (NUEVO) --------------------
def rango_solapado(a_ini: date, a_fin: date, b_ini: date, b_fin: date):
    """
    Intersección inclusiva entre [a_ini, a_fin] y [b_ini, b_fin].
    Devuelve (ini, fin, dias) o (None, None, 0) si no hay solapamiento.
    """
    if a_ini is None or a_fin is None or b_ini is None or b_fin is None:
        return (None, None, 0)
    ini = max(a_ini, b_ini)
    fin = min(a_fin, b_fin)
    if ini > fin:
        return (None, None, 0)
    dias = (fin - ini).days + 1  # inclusivo
    return (ini, fin, max(dias, 0))

def periodo_label(fecha_inicio: date, fecha_fin: date) -> str:
    """ 'AAAA-AAAA' desde las fechas reales del periodo. """
    if not fecha_inicio or not fecha_fin:
        return ""
    return f"{fecha_inicio.year}-{fecha_fin.year}"

def ventana_max_goce(fecha_fin_periodo: date) -> date:
    """ Política usual: hasta un año después del fin del periodo. Ajusta si tu empresa usa otra. """
    if not fecha_fin_periodo:
        return None
    return fecha_fin_periodo.replace(year=fecha_fin_periodo.year + 1)

def partir_rango_por_bolsas(inicio: date, dias_p1: int, dias_p2: int):
    """
    Parte un rango continuo empezando en 'inicio' en dos tramos consecutivos:
    - tramo P1: primeros 'dias_p1' días
    - tramo P2: siguientes 'dias_p2' días
    Devuelve: ((p1_ini, p1_fin), (p2_ini, p2_fin)) con None si días = 0
    """
    p1_ini = p1_fin = p2_ini = p2_fin = None

    if dias_p1 and dias_p1 > 0:
        p1_ini = inicio
        p1_fin = inicio + timedelta(days=dias_p1 - 1)

    if dias_p2 and dias_p2 > 0:
        p2_ini = (p1_fin + timedelta(days=1)) if p1_fin else inicio
        p2_fin = p2_ini + timedelta(days=dias_p2 - 1)

    return (p1_ini, p1_fin), (p2_ini, p2_fin)


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
    """Recalcula truncos/pendientes para TODOS los periodos en base a movimientos reales."""
    from models import db, Empleado, PeriodoVacacional, MovimientoVacacional
    from datetime import date

    hoy = date.today()

    for p in PeriodoVacacional.query.all():
        e = Empleado.query.get(p.id_empleado)
        if not e:
            continue

        dias_periodo = int(p.dias_periodo or 30)

        # 1) Días consumidos por este periodo (GOCE, SOLICITUD_VACACIONES, CONVENIO)
        consumidos = (
            db.session.query(db.func.coalesce(db.func.sum(db.func.abs(MovimientoVacacional.dias)), 0))
            .filter(
                MovimientoVacacional.id_periodo == p.id,
                MovimientoVacacional.tipo.in_(('GOCE', 'SOLICITUD_VACACIONES', 'CONVENIO'))
            )
            .scalar()
        ) or 0
        consumidos = int(consumidos)

        # 2) Estado del periodo
        if hoy < p.fecha_fin:
            # Periodo en generación → acumula truncos
            ganados = int(calcular_dias_truncos(e.fecha_ingreso, hoy, p.fecha_inicio, p.fecha_fin))
            p.dias_truncos = max(0, ganados - consumidos)
            p.dias_pendientes = 0
            p.dias_tomados = min(dias_periodo, consumidos)
        else:
            # Periodo cerrado → no truncos, pendientes = capacidad - consumidos
            p.dias_truncos = 0
            p.dias_pendientes = max(0, dias_periodo - consumidos)
            p.dias_tomados = min(dias_periodo, consumidos)

        db.session.add(p)

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
