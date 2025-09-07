from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False, index=True)
    # Si tu columna en BD se llama EXACTAMENTE 'password_hash', deja así:
    password_hash = db.Column(db.String(255), nullable=False)

    # Si en tu BD la columna se llama 'password' y NO 'password_hash',
    # usa esta línea en su lugar y comenta la de arriba:
    # password_hash = db.Column('password', db.String(255), nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # helpers
    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Empleado(db.Model):
    __tablename__ = 'empleado'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(8), nullable=False, unique=True)
    cargo = db.Column(db.String(100))
    fecha_ingreso = db.Column(db.Date)
    direccion = db.Column(db.String(200))

    periodos = db.relationship(
        "PeriodoVacacional",
        back_populates="empleado",
        cascade="all, delete-orphan"
    )
    convenios = db.relationship(
        "Convenio",
        back_populates="empleado",
        cascade="all, delete-orphan"
    )


class PeriodoVacacional(db.Model):
    __tablename__ = 'periodo_vacacional'
    id = db.Column(db.Integer, primary_key=True)
    id_empleado = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)
    periodo = db.Column(db.String(9), nullable=False)          # "2024-2025"
    dias_periodo = db.Column(db.Integer, nullable=False)       # normalmente 30
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)

    dias_pendientes = db.Column(db.Integer, default=0)
    dias_tomados = db.Column(db.Integer, default=0)
    dias_truncos = db.Column(db.Integer, default=0)

    empleado = db.relationship("Empleado", back_populates="periodos")
    movimientos = db.relationship(
        "MovimientoVacacional",
        back_populates="periodo_vacacional",
        cascade="all, delete-orphan"
    )


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
    # La relación inversa con movimientos se define en MovimientoVacacional (backref)


class MovimientoVacacional(db.Model):
    __tablename__ = 'movimiento_vacacional'
    id = db.Column(db.Integer, primary_key=True)

    id_empleado = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)
    id_periodo  = db.Column(db.Integer, db.ForeignKey('periodo_vacacional.id'), nullable=False)

    tipo  = db.Column(db.String(50), nullable=False)       # GOCE / AJUSTE / CONVENIO / etc.
    fecha = db.Column(db.Date, nullable=False)
    dias  = db.Column(db.Integer, nullable=False)          # usar valor positivo
    saldo_resultante = db.Column(db.Integer, nullable=False)

    # rango cuando aplica
    fecha_inicio = db.Column(db.Date)
    fecha_fin    = db.Column(db.Date)

    # vínculo opcional al convenio que originó el movimiento
    id_convenio = db.Column(db.Integer, db.ForeignKey('convenio.id'), nullable=True)

    empleado = db.relationship("Empleado", backref="movimientos")
    periodo_vacacional = db.relationship("PeriodoVacacional", back_populates="movimientos")
    convenio = db.relationship("Convenio", backref="movimientos", foreign_keys=[id_convenio])
