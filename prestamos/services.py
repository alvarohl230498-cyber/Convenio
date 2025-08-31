from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Iterable

from models import db
from .models import Prestamo, Cuota, Amortizacion


MESES_ES = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

# Abreviaturas para cabeceras (septiembre -> set)
MESES_ABBR = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "set",
    10: "oct",
    11: "nov",
    12: "dic",
}

# Para parseo defensivo si hiciera falta
MESES_MATCH = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "setiembre": 9,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def nombre_mes(m: int) -> str:
    return MESES_ES[m].capitalize()


def siguiente_mes(m: int, a: int) -> Tuple[int, int]:
    return (1, a + 1) if m == 12 else (m + 1, a)


def dec(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def generar_cronograma(
    monto_total: Decimal,
    n_cuotas: int,
    mes_inicio: int,
    anio_inicio: int,
    incluir_grati: bool = False,
    anio_grati_desde: Optional[int] = None,
) -> List[Dict]:
    """Crea N líneas; si toca julio/diciembre y aplica, inserta primero 'Gratificación mes AAAA'.
    La última cuota ajusta para cuadrar total exacto (2 decimales).
    """
    M = dec(monto_total)
    N = int(n_cuotas)
    if N <= 0:
        raise ValueError("n_cuotas debe ser > 0")
    base = (M / N).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    out: List[Dict] = []
    mes, anio = mes_inicio, anio_inicio
    orden = 1
    while len(out) < N:
        if (
            incluir_grati
            and anio_grati_desde
            and anio >= anio_grati_desde
            and mes in (7, 12)
        ):
            if len(out) < N:
                out.append(
                    {
                        "orden": orden,
                        "etiqueta": f"Gratificación {nombre_mes(mes).lower()} {anio}",
                        "anio": anio,
                        "mes": mes,
                        "es_grati": True,
                        "monto": base,
                    }
                )
                orden += 1
        if len(out) < N:
            out.append(
                {
                    "orden": orden,
                    "etiqueta": f"{nombre_mes(mes)} {anio}",
                    "anio": anio,
                    "mes": mes,
                    "es_grati": False,
                    "monto": base,
                }
            )
            orden += 1
        mes, anio = siguiente_mes(mes, anio)

    # Ajuste final
    suma = sum(dec(c["monto"]) for c in out)
    diff = (M - suma).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    out[-1]["monto"] = (dec(out[-1]["monto"]) + diff).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert sum(dec(c["monto"]) for c in out) == M
    return out


def cuotas_pendientes(prestamo: Prestamo) -> List[Cuota]:
    return [c for c in prestamo.cuotas if c.estado == "Pendiente"]


def amortizar(
    prestamo: Prestamo,
    monto: Decimal,
    fecha: date,
    obs: Optional[str],
    usuario: Optional[str] = None,
):
    """
    Consume el monto contra cuotas Pendientes, en el orden natural del arreglo.
    - Si cubre totalmente la cuota => estado = 'Amortizada' (NO 'Descontada').
    - Si es parcial => reduce c.monto y mantiene 'Pendiente'.
    Nota: 'Descontada' la usa el cierre de mes (planilla), aquí no se debe tocar.
    """
    rem = dec(monto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    for c in cuotas_pendientes(prestamo):
        if rem <= 0:
            break
        cm = dec(c.monto)
        if rem >= cm:
            # Amortización total de la cuota: marcar como 'Amortizada'
            c.estado = "Amortizada"
            # NO colocamos fecha_descuento_real (esto es para planilla real)
            rem = (rem - cm).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            # Amortización parcial: bajar el monto y seguir 'Pendiente'
            c.monto = (cm - rem).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rem = Decimal("0.00")
            break

    prestamo.estado = (
        "Cancelado" if not cuotas_pendientes(prestamo) else "Amortizado Parcial"
    )
    db.session.add(
        Amortizacion(
            prestamo_id=prestamo.id,
            monto=monto,
            fecha=fecha,
            observacion=obs or "",
            usuario=usuario or "web",
        )
    )


def nombre_empleado(emp) -> str:
    """Obtiene el nombre para mostrar, compatible con ambos esquemas."""
    val = getattr(emp, "nombre", None) or getattr(emp, "nombre_completo", None)
    if val:
        return val.strip()
    n = getattr(emp, "nombres", None)
    a = getattr(emp, "apellidos", None)
    if n or a:
        return f"{(n or '').strip()} {(a or '').strip()}".strip()
    return str(getattr(emp, "dni", "")).strip()


PDF_CSS = """
@page { size: A4; margin: 18mm 18mm; }
body { font-family: 'Inter', Arial, sans-serif; font-size: 11pt; color: #111; }
h1 { font-size: 14pt; margin: 0 0 8px 0; text-transform: uppercase; }
small { color: #444; }
.table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.table th, .table td { border: 1px solid #333; padding: 6px 8px; font-size: 10pt; }
.head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.firmas { display: flex; gap: 24px; margin-top: 40px; }
.firma { flex: 1; text-align: center; }
.firma .linea { margin-top: 48px; border-top: 1px solid #000; padding-top: 6px; }
.meta { font-size: 9pt; color: #333; margin-top: 4px; }
.badge { font-size: 9pt; padding: 2px 6px; border: 1px solid #999; border-radius: 4px; }
"""

# ======================================================================
# =============  EXCEL: CRONOGRAMA EN COLUMNAS (post 'AÑO')  ===========
# =============  ORDEN: DESDE EL MES PRESENTE HACIA FUTURO  ===========
# ======================================================================


def _info_cuota(c: Cuota) -> Tuple[Optional[datetime], bool]:
    """Devuelve (fecha primer día del mes, es_grati). Robusto ante datos faltantes."""
    y = getattr(c, "anio", None)
    m = getattr(c, "mes", None)
    es_grati = bool(getattr(c, "es_grati", False))
    if y and m:
        return datetime(int(y), int(m), 1), es_grati

    # Fallback: parsear etiqueta, ej. 'Gratificación julio 2025' o 'Agosto 2025'
    s = (getattr(c, "etiqueta", "") or "").strip().lower()
    if "grat" in s:
        es_grati = True
    y2 = None
    for token in s.split():
        if token.isdigit() and len(token) == 4:
            try:
                y2 = int(token)
                break
            except Exception:
                pass
    m2 = None
    for nombre, idx in MESES_MATCH.items():
        if f" {nombre} " in f" {s} ":
            m2 = idx
            break
    if y2 and m2:
        return datetime(y2, m2, 1), es_grati
    return None, es_grati


def _label_mes(fecha: datetime) -> str:
    """Etiqueta de mes: 'abr 25'."""
    return f"{MESES_ABBR[fecha.month]} {str(fecha.year)[-2:]}"


def _label_grati(fecha: datetime) -> str:
    """Etiqueta de gratificación, siempre con mes para evitar duplicados: 'grati jul 25'."""
    return f"grati {MESES_ABBR[fecha.month]} {str(fecha.year)[-2:]}"


def _months_diff(start: datetime, target: datetime) -> int:
    """Diferencia en meses entre start y target (target - start)."""
    return (target.year - start.year) * 12 + (target.month - start.month)


def preparar_columnas_cronograma_desde_hoy(
    prestamos: Iterable[Prestamo], hoy: Optional[date] = None
) -> Tuple[List[str], Dict[int, Dict[str, Decimal]]]:
    """
    Crea:
    - lista de columnas ordenadas desde 'hoy' hacia futuro (mes actual -> adelante),
    - mapping por préstamo: {prestamo_id: {columna: monto}}.

    Las columnas se crean solo para los meses/cuotas existentes, ordenadas
    a partir del mes actual. La gratificación del mes (jul/dic) se coloca
    antes del propio mes.
    """
    start = datetime.combine(hoy or date.today(), datetime.min.time())

    # Recolectar todas las cuotas de todos los préstamos
    items: List[Tuple[int, datetime, bool, Decimal]] = (
        []
    )  # (pid, fecha, es_grati, monto)
    for p in prestamos:
        for c in p.cuotas or []:
            fecha, es_grati = _info_cuota(c)
            if not fecha:
                continue
            items.append((int(p.id), fecha, es_grati, dec(getattr(c, "monto", 0))))

    if not items:
        return [], {}

    # Determinar etiquetas y llaves de orden (desde hoy hacia futuro)
    cols_order_key: Dict[str, float] = {}
    valores: Dict[int, Dict[str, Decimal]] = {}

    for pid, fecha, es_grati, monto in items:
        # etiqueta
        col = _label_grati(fecha) if es_grati else _label_mes(fecha)
        # orden: meses desde 'hoy' + (-0.5) si grati para ir antes del mes
        key = _months_diff(start, fecha) + (-0.5 if es_grati else 0.0)

        if col not in cols_order_key or key < cols_order_key[col]:
            cols_order_key[col] = key

        valores.setdefault(pid, {})
        valores[pid][col] = valores[pid].get(col, dec(0)) + monto

    # Ordenar columnas por esa llave (de presente hacia futuro)
    columnas_ordenadas = [
        c for c, _ in sorted(cols_order_key.items(), key=lambda kv: kv[1])
    ]

    return columnas_ordenadas, valores


def anexar_cronograma_a_dataframe(
    df,
    prestamos: Iterable[Prestamo],
    llave_col: str = "id",
    col_ano: str = "AÑO",
    hoy: Optional[date] = None,
):
    """
    Inserta las columnas del cronograma **después** de 'AÑO' en la MISMA hoja,
    ordenadas desde el mes presente hacia el futuro:
        abr 25, may 25, jun 25, ... (y 'grati jul 25' antes de 'jul 25', etc.)
    Requiere pandas; import local para no afectar el resto del módulo.

    Retorna un NUEVO DataFrame (no muta el original).
    """
    import pandas as pd  # import local

    cols, valores = preparar_columnas_cronograma_desde_hoy(prestamos, hoy=hoy)
    if not cols:
        return df.copy()

    if col_ano not in df.columns:
        raise ValueError(f"No se encontró la columna '{col_ano}' en el DataFrame")

    pos = df.columns.get_loc(col_ano) + 1

    base = df.set_index(llave_col, drop=False)
    cron = pd.DataFrame(0, index=base.index, columns=cols)

    # Volcar montos en sus columnas
    for pid, mapping in valores.items():
        if pid in cron.index:
            for col, monto in mapping.items():
                if col in cron.columns:
                    cron.at[pid, col] = float(
                        monto
                    )  # usar Decimal si tu writer lo soporta

    # Reconstruir pegando justo después de 'AÑO'
    left = base.iloc[:, :pos]
    right = base.iloc[:, pos:]
    out = pd.concat([left, cron, right], axis=1).reset_index(drop=True)
    return out
