from __future__ import annotations
from datetime import datetime
from sqlalchemy import Numeric


# Importa tu db y Empleado desde el models.py de tu app plana
from models import db, Empleado


class Prestamo(db.Model):
    __tablename__ = "prestamos"
    id = db.Column(db.Integer, primary_key=True)
    # antes: db.ForeignKey("empleados.id")
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{Empleado.__tablename__}.id"),  # ← usa el nombre real de la tabla
        nullable=False
    )
    tipo = db.Column(db.String(80), nullable=False)
    motivo_especifico = db.Column(db.String(200))
    fecha_solicitud = db.Column(db.Date, nullable=False)
    monto_total = db.Column(Numeric(10, 2), nullable=False)
    n_cuotas = db.Column(db.Integer, nullable=False)
    incluir_grati = db.Column(db.Boolean, default=False)
    anio_grati_desde = db.Column(db.Integer)
    fecha_firma = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(30), default="Emitido")
    version_formato = db.Column(db.String(30), default="GP-R-004 v06")
    creado_por = db.Column(db.String(80))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    empleado = db.relationship("Empleado")
    cuotas = db.relationship("Cuota", cascade="all, delete-orphan", order_by="Cuota.orden")
    amortizaciones = db.relationship("Amortizacion", cascade="all, delete-orphan")

class Cuota(db.Model):
    __tablename__ = "prestamo_cuotas"
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey("prestamos.id"), nullable=False, index=True)
    orden = db.Column(db.Integer, nullable=False, index=True)
    etiqueta = db.Column(db.String(40), nullable=False) # "Agosto 2025" o "Gratificación diciembre 2025"
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    es_grati = db.Column(db.Boolean, default=False)
    monto = db.Column(Numeric(10, 2), nullable=False)
    estado = db.Column(db.String(20), default="Pendiente") # Pendiente/Descontada/Anulada
    fecha_cobro_teorica = db.Column(db.Date) # 1ro del mes
    fecha_descuento_real = db.Column(db.Date)


class Amortizacion(db.Model):
    __tablename__ = "prestamo_amortizaciones"
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey("prestamos.id"), nullable=False, index=True)
    monto = db.Column(Numeric(10, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    observacion = db.Column(db.String(200))
    usuario = db.Column(db.String(80))


class Documento(db.Model):
    __tablename__ = "prestamo_documentos"
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey("prestamos.id"), nullable=False, index=True)
    ruta_pdf = db.Column(db.String(300), nullable=False)
    hash = db.Column(db.String(64))
    version_formato = db.Column(db.String(30), default="GP-R-004 v06")
    emitido_en = db.Column(db.DateTime, default=datetime.utcnow)